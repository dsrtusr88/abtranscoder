import os
import subprocess
import argparse
import mutagen.flac
import re
import pipes
import shlex
import shutil
import errno
import configparser
from PIL import Image
import io

# Define encoders for different output formats
encoders = {
    '320': {'enc': 'lame', 'ext': '.mp3', 'opts': '-h -b 320 --ignore-tag-errors'},
    'V0': {'enc': 'lame', 'ext': '.mp3', 'opts': '-V 0 --vbr-new --ignore-tag-errors'},
    'V2': {'enc': 'lame', 'ext': '.mp3', 'opts': '-V 2 --vbr-new --ignore-tag-errors'},
    'FLAC': {'enc': 'flac', 'ext': '.flac', 'opts': '--best'}
}

class TranscodeException(Exception):
    pass

class TranscodeDownmixException(TranscodeException):
    pass

class UnknownSampleRateException(TranscodeException):
    pass

def run_pipeline(cmds):
    """
    Run a pipeline of commands and return the results.
    """
    stdin = None
    last_proc = None
    procs = []

    try:
        for cmd in cmds:
            try:
                proc = subprocess.Popen(shlex.split(cmd), stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if last_proc:
                    last_proc.stdout.close()
                procs.append(proc)
                stdin = proc.stdout
                last_proc = proc
            except Exception as e:
                print(f"Error running command '{cmd}': {e}")
    finally:
        last_stderr = last_proc.communicate()[1]

    results = []
    for (cmd, proc) in zip(cmds[:-1], procs[:-1]):
        proc.wait()
        stderr_output = proc.stderr.read()
        results.append((proc.returncode, stderr_output))
    results.append((last_proc.returncode, last_stderr))
    return results

def locate(root, match_function, ignore_dotfiles=True):
    """
    Locate files within the root directory based on the match function.
    """
    for path, dirs, files in os.walk(root):
        for filename in (os.path.abspath(os.path.join(path, filename)) for filename in files if match_function(filename)):
            if ignore_dotfiles and os.path.basename(filename).startswith('.'):
                pass
            else:
                yield filename

def ext_matcher(*extensions):
    """
    Return a function to check if a filename has one of the specified extensions.
    """
    return lambda f: os.path.splitext(f)[-1].lower() in extensions

def needs_resampling(flac_dir):
    """
    Check if any FLAC files within flac_dir need resampling when transcoded.
    """
    flacs = (mutagen.flac.FLAC(flac_file) for flac_file in locate(flac_dir, ext_matcher('.flac')))
    return any(flac.info.bits_per_sample > 16 for flac in flacs)

def transcode_commands(output_format, resample, needed_sample_rate, flac_file, transcode_file):
    """
    Return a list of transcode steps (one command per list element).
    """
    if resample:
        flac_decoder = 'sox %(FLAC)s -G -b 16 -t wav - rate -v -L %(SAMPLERATE)s dither'
    else:
        flac_decoder = 'flac -dcs -- %(FLAC)s'

    lame_encoder = 'lame -S %(OPTS)s - %(FILE)s'
    flac_encoder = 'flac %(OPTS)s -o %(FILE)s -'

    transcoding_steps = [flac_decoder]

    if encoders[output_format]['enc'] == 'lame':
        transcoding_steps.append(lame_encoder)
    elif encoders[output_format]['enc'] == 'flac':
        transcoding_steps.append(flac_encoder)

    transcode_args = {
        'FLAC' : pipes.quote(flac_file),
        'FILE' : pipes.quote(transcode_file),
        'OPTS' : encoders[output_format]['opts'],
        'SAMPLERATE' : needed_sample_rate,
    }

    if output_format == 'FLAC' and resample:
        commands = ['sox %(FLAC)s -G -b 16 %(FILE)s rate -v -L %(SAMPLERATE)s dither' % transcode_args]
    else:
        commands = list(map(lambda cmd: cmd % transcode_args, transcoding_steps))
    return commands

def transcode(flac_file, output_dir, output_format, config):
    """
    Transcode a FLAC file into another format.
    """
    # Gather metadata from the flac file
    flac_info = mutagen.flac.FLAC(flac_file)
    sample_rate = flac_info.info.sample_rate
    bits_per_sample = flac_info.info.bits_per_sample
    resample = sample_rate > 48000 or bits_per_sample > 16

    # If resampling isn't needed then needed_sample_rate will not be used.
    needed_sample_rate = None

    if resample:
        if sample_rate % 44100 == 0:
            needed_sample_rate = '44100'
        elif sample_rate % 48000 == 0:
            needed_sample_rate = '48000'
        else:
            raise UnknownSampleRateException('FLAC file "{0}" has a sample rate {1}, which is not 88.2 , 176.4 or 96kHz but needs resampling, this is unsupported'.format(flac_file, sample_rate))

    if flac_info.info.channels > 2:
        raise TranscodeDownmixException('FLAC file "%s" has more than 2 channels, unsupported' % flac_file)

    # Determine the new filename
    transcode_basename = os.path.splitext(os.path.basename(flac_file))[0]
    transcode_basename = re.sub(r'[\?<>\\*\|"]', '_', transcode_basename)
    transcode_file = os.path.join(output_dir, transcode_basename)
    transcode_file += encoders[output_format]['ext']

    if not os.path.exists(os.path.dirname(transcode_file)):
        try:
            os.makedirs(os.path.dirname(transcode_file))
        except OSError as e:
            if e.errno == errno.EEXIST:
                # Harmless race condition -- another transcode process
                # beat us here.
                pass
            else:
                raise e

    commands = transcode_commands(output_format, resample, needed_sample_rate, flac_file, transcode_file)
    results = run_pipeline(commands)

    # Check for problems
    for (cmd, (code, stderr)) in zip(commands, results):
        if code:
            raise TranscodeException('Error running command "%s" (return code %d):\n%s' % (cmd, code, stderr.decode('utf-8')))

    # Resize embedded images
    for embedded in flac_info.pictures:
        image_data = embedded.data
        image = Image.open(io.BytesIO(image_data))

        # Check image size
        max_size = 2 * 1024 * 1024  # 2 MiB
        if len(image_data) > max_size:
            image.thumbnail((800, 600), Image.ANTIALIAS)
            resized_image_data = io.BytesIO()
            image.save(resized_image_data, format=image.format)
            embedded.data = resized_image_data.getvalue()

    # Resize cover image if needed
    cover_image = flac_info.pictures[0] if flac_info.pictures else None
    if cover_image:
        image_data = cover_image.data
        image = Image.open(io.BytesIO(image_data))

        # Check image size
        max_size = 2 * 1024 * 1024  # 2 MiB
        if len(image_data) > max_size:
            image.thumbnail((800, 600), Image.ANTIALIAS)
            resized_image_data = io.BytesIO()
            image.save(resized_image_data, format=image.format)
            cover_image.data = resized_image_data.getvalue()

    return transcode_file

def make_torrent(input_file, config):
    """
    Create a torrent file for the input file using specifications from the config file.
    """
    # Load parameters from the config file
    torrent_dir = config.get('AB', 'torrent_dir')
    announce_url = config.get('torrent', 'announce_url')
    enable_dht = config.getboolean('torrent', 'enable_dht')
    enable_pex = config.getboolean('torrent', 'enable_pex')
    enable_lsd = config.getboolean('torrent', 'enable_lsd')
    private = config.getboolean('torrent', 'private')
    piece_size = config.getint('torrent', 'piece_size')
    source = config.get('torrent', 'source')

    # Construct the mktorrent command
    cmd = 'mktorrent -l {piece_size} -p -a {announce_url} -o "{torrent_dir}/{input_file}.torrent" "{input_file}"'.format(
        piece_size=piece_size,
        announce_url=announce_url,
        torrent_dir=torrent_dir,
        input_file=input_file
    )

    # Run the mktorrent command
    subprocess.run(shlex.split(cmd))

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Load transcode parameters from the config file
    output_format = config.get('transcode', 'output_format')
    max_threads = config.getint('transcode', 'max_threads')

    # Other parts of your main function...
    flac_files = locate(config.get('AB', 'data_dir'), ext_matcher('.flac'))
    for flac_file in flac_files:
        try:
            transcode_file = transcode(flac_file, config.get('AB', 'output_dir'), output_format, config)
            print(f"Transcoded {flac_file} to {transcode_file}")

            # Call make_torrent function
            make_torrent(transcode_file, config)
            print(f"Torrent created for {transcode_file}")
        except TranscodeException as e:
            print(f"Error transcoding {flac_file}: {e}")
        except Exception as e:
            print(f"Unexpected error transcoding {flac_file}: {e}")

if __name__ == "__main__":
    main()
