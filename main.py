import os
import subprocess
import configparser
import mutagen.flac
import re
from PIL import Image
import io
import shlex
import shutil

# Define encoders for different output formats
encoders = {
    '320': {'enc': 'lame', 'ext': '.mp3', 'opts': '-h -b 320 --ignore-tag-errors'},
    'V0': {'enc': 'lame', 'ext': '.mp3', 'opts': '-V 0 --vbr-new --ignore-tag-errors'},
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
            proc = subprocess.Popen(shlex.split(cmd), stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if last_proc:
                last_proc.stdout.close()
            procs.append(proc)
            stdin = proc.stdout
            last_proc = proc
    finally:
        if last_proc is not None:
            last_stderr = last_proc.communicate()[1]
        else:
            last_stderr = b''
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
        for filename in files:
            if match_function(filename):
                if ignore_dotfiles and filename.startswith('.'):
                    continue
                yield os.path.join(path, filename)

def ext_matcher(*extensions):
    """
    Return a function to check if a filename has one of the specified extensions.
    """
    return lambda f: os.path.splitext(f)[-1].lower() in extensions

def resize_embedded_images(flac_info, max_size=2 * 1024 * 1024):
    """
    Resize embedded images in FLAC file if they exceed a certain size.
    """
    for index, picture in enumerate(flac_info.pictures):
        image_data = picture.data
        if len(image_data) > max_size:
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail((800, 600), Image.ANTIALIAS)
            output = io.BytesIO()
            image.save(output, format=image.format)
            picture.data = output.getvalue()

def resize_jpg_images(directory, max_size=2 * 1024 * 1024):
    """
    Resize .jpg images in the specified directory if they exceed a certain size.
    """
    jpg_files = locate(directory, ext_matcher('.jpg', '.jpeg'))
    for jpg_file in jpg_files:
        try:
            with Image.open(jpg_file) as img:
                if os.path.getsize(jpg_file) > max_size:
                    img.thumbnail((800, 600), Image.ANTIALIAS)
                    img.save(jpg_file, "JPEG")
                    print(f"Resized {jpg_file} to fit within {max_size} bytes")
        except IOError as e:
            print(f"Error resizing image {jpg_file}: {e}")

def make_torrent(input_file, config):
    """
    Create a torrent file for the input file using specifications from the config file
    and copy it to the torrent_copy_dir.
    """
    torrent_dir = config.get('AB', 'torrent_dir')
    torrent_copy_dir = config.get('AB', 'torrent_copy_dir')
    announce_url = config.get('torrent', 'announce_url')
    piece_size = config.get('torrent', 'piece_size')

    if not os.path.exists(torrent_dir):
        os.makedirs(torrent_dir, exist_ok=True)
    if not os.path.exists(torrent_copy_dir):
        os.makedirs(torrent_copy_dir, exist_ok=True)
    
    torrent_file_name = os.path.basename(input_file) + ".torrent"
    torrent_file_path = os.path.join(torrent_dir, torrent_file_name)
    torrent_copy_path = os.path.join(torrent_copy_dir, torrent_file_name)

    cmd = f'mktorrent -l {piece_size} -p -a "{announce_url}" -o "{torrent_file_path}" "{input_file}"'
    
    try:
        subprocess.run(shlex.split(cmd), check=True)
        print(f"Torrent file created for {input_file} at {torrent_file_path}")
        shutil.copy(torrent_file_path, torrent_copy_path)
        print(f"Copied {torrent_file_name} to {torrent_copy_dir}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to create torrent for {input_file}: {e}")

def transcode(flac_file, output_dir, output_format, config):
    """
    Transcode a FLAC file into another format, resize images, and create a torrent.
    """
    flac_info = mutagen.flac.FLAC(flac_file)
    resize_embedded_images(flac_info)
    resize_jpg_images(os.path.dirname(flac_file))

    transcode_basename = re.sub(r'[\?<>\\*\|"]', '_', os.path.splitext(os.path.basename(flac_file))[0])
    transcode_file = os.path.join(output_dir, transcode_basename + encoders[output_format]['ext'])

    if not os.path.exists(os.path.dirname(transcode_file)):
        os.makedirs(os.path.dirname(transcode_file), exist_ok=True)

    # Constructing the transcoding command
    command = [
        f"ffmpeg -i {shlex.quote(flac_file)}"  # Source file
    ]

    # Apply additional commands based on output format and whether resampling is needed
    if output_format != 'FLAC' or (flac_info.info.sample_rate > 48000 or flac_info.info.bits_per_sample > 16):
        command.append(encoders[output_format]['opts'])

    command.append(shlex.quote(transcode_file))  # Output file

    # Execute the transcoding process
    result = run_pipeline([' '.join(command)])
    if result[-1][0] != 0:  # Check the last command's return code
        raise TranscodeException(f"Transcoding failed for {flac_file}")

    make_torrent(transcode_file, config)

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    output_formats = config.get('transcode', 'output_format').split(',')

    for output_format in output_formats:
        flac_files = list(locate(config.get('AB', 'data_dir'), ext_matcher('.flac')))
        for flac_file in flac_files:
            try:
                transcode(flac_file, config.get('AB', 'output_dir'), output_format, config)
            except Exception as e:
                print(f"Error during processing {flac_file}: {e}")

if __name__ == "__main__":
    main()
