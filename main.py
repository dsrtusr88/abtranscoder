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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define encoders for different output formats
encoders = {
    'V0': {'enc': 'lame', 'ext': '.mp3', 'opts': '-V 0 --vbr-new --ignore-tag-errors'},
    'FLAC': {'enc': 'sox', 'ext': '.flac', 'opts': '--best'}
}

def run_command(command):
    try:
        logging.info(f"Executing command: {command}")
        subprocess.run(shlex.split(command), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e}")
        raise

def locate_files(directory, extensions):
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in extensions):
                yield os.path.join(root, filename)

def resize_image(image_path, max_size=(800, 600), max_bytes=2*1024*1024):
    with Image.open(image_path) as img:
        if img.size > max_size or os.path.getsize(image_path) > max_bytes:
            img.thumbnail(max_size, Image.ANTIALIAS)
            img.save(image_path)
            logging.info(f"Resized image: {image_path}")

def resize_images_in_album(album_path):
    for image_path in locate_files(album_path, ['.jpg', '.jpeg', '.png']):
        resize_image(image_path)

def transcode_album(album_path, output_dir, format, config):
    for flac_file in locate_files(album_path, ['.flac']):
        flac_info = mutagen.flac.FLAC(flac_file)
        # Assuming 48kHz for 96kHz sources, and 44.1kHz for 88.2kHz sources
        target_rate = '48000' if flac_info.info.sample_rate > 48000 else '44100'
        output_path = os.path.join(output_dir, os.path.basename(flac_file).replace('.flac', encoders[format]['ext']))
        if format == 'FLAC':
            command = f"sox \"{flac_file}\" -G -b 16 -r {target_rate} \"{output_path}\" dither"
        else:  # V0
            command = f"lame --resample {target_rate} {encoders[format]['opts']} \"{flac_file}\" \"{output_path}\""
        run_command(command)
        logging.info(f"Transcoded {flac_file} to {output_path}")
    resize_images_in_album(album_path)

def create_torrent_for_album(album_path, config):
    torrent_name = f"{os.path.basename(album_path)}.torrent"
    torrent_path = os.path.join(config['torrent_dir'], torrent_name)
    command = f"mktorrent -l 21 -p -a \"{config['announce_url']}\" -o \"{torrent_path}\" \"{album_path}\""
    run_command(command)
    # Copy the .torrent file if needed
    if config['torrent_copy_dir']:
        shutil.copy(torrent_path, config['torrent_copy_dir'])
    logging.info(f"Created torrent for album: {torrent_name}")

def main():
    # Load configuration
    config = configparser.ConfigParser()
    config.read('config.ini')
    config_dict = {section: dict(config.items(section)) for section in config.sections()}
    
    for album_path in locate_files(config_dict['AB']['data_dir'], ['.flac']):
        album_dir = os.path.dirname(album_path)
        for format in ['FLAC', 'V0']:
            output_album_dir = os.path.join(config_dict['AB']['output_dir'], format, os.path.basename(album_dir))
            os.makedirs(output_album_dir, exist_ok=True)
            transcode_album(album_dir, output_album_dir, format, config_dict['torrent'])
            create_torrent_for_album(output_album_dir, config_dict['torrent'])
            logging.info(f"Processed album: {album_dir}")

if __name__ == "__main__":
    main()
