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
    'FLAC': {'enc': 'sox', 'ext': '.flac', 'opts': '--best'}
}

class TranscodeException(Exception):
    pass

def run_command(command):
    try:
        subprocess.check_call(shlex.split(command), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e.output}")
        raise

def locate_files(root_dir, extensions):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in extensions):
                yield os.path.join(dirpath, filename)

def resize_image(image_path, max_size=(800, 600)):
    with Image.open(image_path) as img:
        img.thumbnail(max_size, Image.ANTIALIAS)
        img.save(image_path)

def resize_images(directory):
    for image_path in locate_files(directory, ['.jpg', '.jpeg', '.png']):
        resize_image(image_path)

def transcode(flac_file, output_dir, output_format, config):
    flac_info = mutagen.flac.FLAC(flac_file)
    sample_rate = flac_info.info.sample_rate
    bits_per_sample = flac_info.info.bits_per_sample
    channels = flac_info.info.channels

    resample_needed = sample_rate > 48000 or bits_per_sample > 16
    target_sample_rate = '48000' if sample_rate >= 88200 else '44100'

    transcode_basename = re.sub(r'[\?<>\\*\|"]', '_', os.path.splitext(os.path.basename(flac_file))[0])
    output_path = os.path.join(output_dir, transcode_basename + encoders[output_format]['ext'])

    if output_format == 'FLAC' and resample_needed:
        cmd = f"sox {flac_file} -G -b 16 {output_path} rate -v -L {target_sample_rate} dither"
    elif output_format in ['320', 'V0']:
        lame_opts = encoders[output_format]['opts']
        cmd = f"ffmpeg -i {flac_file} -vn -ar {target_sample_rate if resample_needed else sample_rate} {lame_opts} {output_path}"
    else:
        raise ValueError("Unsupported format specified")

    run_command(cmd)

def make_torrent(input_dir, config):
    torrent_dir = config.get('Paths', 'torrent_dir')
    announce_url = config.get('Torrent', 'announce_url')
    piece_size = config.get('Torrent', 'piece_size')
    torrent_file_name = f"{os.path.basename(input_dir)}.torrent"
    torrent_file_path = os.path.join(torrent_dir, torrent_file_name)

    cmd = f"mktorrent -l {piece_size} -p -a \"{announce_url}\" -o \"{torrent_file_path}\" \"{input_dir}\""
    run_command(cmd)

def process_album(album_path, config):
    for output_format in ['FLAC', '320', 'V0']:
        output_dir = os.path.join(config.get('Paths', 'output_dir'), output_format)
        os.makedirs(output_dir, exist_ok=True)

        for flac_file in locate_files(album_path, ['.flac']):
            try:
                transcode(flac_file, output_dir, output_format, config)
            except Exception as e:
                print(f"Error during processing {flac_file}: {e}")

        resize_images(album_path)
        make_torrent(output_dir, config)

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    album_dir = config.get('Paths', 'data_dir')

    for root, dirs, _ in os.walk(album_dir):
        for dir in dirs:
            album_path = os.path.join(root, dir)
            process_album(album_path, config)

if __name__ == "__main__":
    main()
