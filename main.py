import os
import subprocess
import configparser
import mutagen.flac
import re
from PIL import Image
import io
import shlex
import shutil
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define encoders for different output formats
encoders = {
    'V0': {'enc': 'lame', 'ext': '.mp3', 'opts': '-V 0 --vbr-new --ignore-tag-errors'},
}

def run_command(command):
    logging.info(f"Executing command: {' '.join(command)}")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logging.error(f"Command failed with error: {result.stderr}")
        raise Exception(f"Command failed: {' '.join(command)}")

def locate_files(directory, extensions):
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in extensions):
                yield os.path.join(root, filename)

def resize_image(image_path, max_size=(800, 600)):
    with Image.open(image_path) as img:
        img.thumbnail(max_size, Image.ANTIALIAS)
        img.save(image_path)
        logging.info(f"Resized image: {image_path}")

def transcode_and_copy(album_path, output_dir, format, config):
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    for flac_file in locate_files(album_path, ['.flac']):
        flac_info = mutagen.flac.FLAC(flac_file)
        sample_rate = flac_info.info.sample_rate
        bits_per_sample = flac_info.info.bits_per_sample

        # Determine target sample rate for downsampling if necessary
        target_sample_rate = sample_rate
        if sample_rate > 48000:
            target_sample_rate = 48000
        elif sample_rate > 44100:
            target_sample_rate = 44100

        # Determine output file path
        output_path = os.path.join(output_dir, os.path.basename(flac_file).replace('.flac', encoders[format]['ext']))

        if bits_per_sample > 16:
            # Use sox for downsampling and bit depth conversion for 24-bit FLACs
            sox_command = ['sox', flac_file, '-G', '-b', '16', output_path, 'rate', '-v', str(target_sample_rate), 'dither']
            run_command(sox_command)
        else:
            # Use lame for transcoding without downsampling for 16-bit FLACs
            if format != 'FLAC':  # Skip transcoding if target format is FLAC and no downsampling is needed
                lame_command = ['lame', *shlex.split(encoders[format]['opts']), flac_file, output_path]
                run_command(lame_command)

    # Copy non-FLAC files (e.g., cover art, logs) to maintain album integrity
    for file in locate_files(album_path, ['.jpg', '.jpeg', '.png', '.log', '.cue', '.nfo']):
        shutil.copy(file, output_dir)
        logging.info(f"Copied {file} to {output_dir}")


def create_torrent(album_path, config):
    torrent_file = os.path.basename(album_path) + ".torrent"
    torrent_path = os.path.join(config['torrent_dir'], torrent_file)
    command = ['mktorrent', '-l', '21', '-p', '-a', config['announce_url'], '-o', torrent_path, album_path]
    run_command(command)
    if 'torrent_copy_dir' in config:
        shutil.copy(torrent_path, config['torrent_copy_dir'])
    logging.info(f"Created torrent for album: {torrent_file}")

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    ab_config = config['AB']
    torrent_config = config['torrent']

    for album_path in locate_files(ab_config['data_dir'], ['.flac']):
        album_dir = os.path.dirname(album_path)
        output_album_dir = os.path.join(ab_config['output_dir'], "V0", os.path.basename(album_dir).replace(" [FLAC]", ""))

        transcode_and_copy(album_dir, output_album_dir, 'V0', ab_config)
        create_torrent(output_album_dir, torrent_config)

if __name__ == "__main__":
    main()
