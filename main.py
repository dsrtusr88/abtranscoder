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
        results.append((proc.returncode, stderr_output.decode()))
    results.append((last_proc.returncode, last_stderr.decode()))
    return results

def locate(root, match_function, ignore_dotfiles=True):
    for path, dirs, files in os.walk(root):
        for filename in files:
            if match_function(filename):
                if ignore_dotfiles and filename.startswith('.'):
                    continue
                yield os.path.join(path, filename)

def ext_matcher(*extensions):
    return lambda f: os.path.splitext(f)[-1].lower() in extensions

def resize_embedded_images(flac_info, max_size=2 * 1024 * 1024):
    for index, picture in enumerate(flac_info.pictures):
        image_data = picture.data
        if len(image_data) > max_size:
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail((800, 600), Image.ANTIALIAS)
            output = io.BytesIO()
            image.save(output, format=image.format)
            picture.data = output.getvalue()

def resize_jpg_images(directory, max_size=2 * 1024 * 1024):
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

def make_torrent(input_dir, config):
    torrent_dir = config.get('AB', 'torrent_dir')
    announce_url = config.get('torrent', 'announce_url')
    piece_size = config.get('torrent', 'piece_size')

    torrent_file_name = os.path.basename(input_dir) + ".torrent"
    torrent_file_path = os.path.join(torrent_dir, torrent_file_name)

    cmd = f'mktorrent -l {piece_size} -p -a "{announce_url}" -o "{torrent_file_path}" "{input_dir}"'
    
    try:
        subprocess.run(shlex.split(cmd), check=True)
        print(f"Torrent created for directory: {input_dir}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to create torrent for {input_dir}: {e}")

def transcode(flac_file, output_dir, output_format, config):
    flac_info = mutagen.flac.FLAC(flac_file)
    resize_embedded_images(flac_info)
    resize_jpg_images(os.path.dirname(flac_file))

    transcode_basename = re.sub(r'[\?<>\\*\|"]', '_', os.path.splitext(os.path.basename(flac_file))[0])
    transcode_file = os.path.join(output_dir, transcode_basename + encoders[output_format]['ext'])

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(transcode_file), exist_ok=True)

    # Constructing the transcoding command
    command = f"ffmpeg -i \"{flac_file}\" {encoders[output_format]['opts']} \"{transcode_file}\""
    result = run_pipeline([command])
    if result[-1][0] != 0:
        raise TranscodeException(f"Transcoding failed for {flac_file}")

def process_albums(config):
    output_formats = config.get('transcode', 'output_format').split(',')
    albums = set(os.path.dirname(flac_path) for flac_path in locate(config.get('AB', 'data_dir'), ext_matcher('.flac')))

    for album_path in albums:
        album_success = True
        for output_format in output_formats:
            album_files = list(locate(album_path, ext_matcher('.flac')))
            for flac_file in album_files:
                try:
                    output_album_dir = os.path.join(config.get('AB', 'output_dir'), os.path.relpath(album_path, config.get('AB', 'data_dir')), output_format)
                    transcode(flac_file, output_album_dir, output_format, config)
                except Exception as e:
                    print(f"Error during processing {flac_file}: {e}")
                    album_success = False
                    break  # Stop processing this album on the first error
            if not album_success:
                break  # Skip to the next album if there was an error

        if album_success:
            try:
                make_torrent(output_album_dir, config)
            except Exception as e:
                print(f"Error creating torrent for album {album_path}: {e}")

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    process_albums(config)

if __name__ == "__main__":
    main()
