import os
import subprocess
import configparser
import mutagen.flac
from PIL import Image
import io
import shlex
import shutil
import logging

# Setup logging
logging.basicConfig(filename='/app/transcode.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Define encoders for different output formats
encoders = {
    'V0': {'enc': 'lame', 'ext': '.mp3', 'opts': '-V 0 --vbr-new --ignore-tag-errors'},
    'FLAC': {'enc': 'flac', 'ext': '.flac', 'opts': '--best'}
}

class TranscodeException(Exception):
    pass

def run_command(command):
    """
    Execute a shell command and return the output.
    """
    logging.info(f"Executing command: {command}")
    try:
        subprocess.check_output(shlex.split(command), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e.output.decode()}")
        raise TranscodeException(f"Command failed: {command}")

def resize_image(image_path, max_size=(800, 600), max_bytes=2*1024*1024):
    """
    Resize the image to fit within the specified size and dimensions.
    """
    try:
        with Image.open(image_path) as img:
            if os.path.getsize(image_path) > max_bytes:
                img.thumbnail(max_size, Image.ANTIALIAS)
                img.save(image_path)
                logging.info(f"Resized image: {image_path}")
    except Exception as e:
        logging.error(f"Failed to resize image {image_path}: {e}")

def transcode_album(album_path, config):
    """
    Transcode all FLAC files in an album to specified formats.
    """
    album_name = os.path.basename(album_path)
    for format, settings in encoders.items():
        output_album_path = os.path.join(config['output_dir'], f"{album_name} [{format}]")
        os.makedirs(output_album_path, exist_ok=True)
        for root, _, files in os.walk(album_path):
            for file in files:
                if file.lower().endswith('.flac'):
                    flac_path = os.path.join(root, file)
                    output_path = os.path.join(output_album_path, file.replace('.flac', settings['ext']))
                    try:
                        if settings['enc'] == 'flac':
                            # Example: sox input.flac -r 44100 output.flac
                            command = f"sox {shlex.quote(flac_path)} {shlex.quote(output_path)} rate -v -L 44100"  # Adjust rate as needed
                        else:  # LAME for V0
                            lame_opts = settings['opts']
                            command = f"ffmpeg -i {shlex.quote(flac_path)} -vn {lame_opts} {shlex.quote(output_path)}"
                        run_command(command)
                        logging.info(f"Transcoded {flac_path} to {output_path}")
                    except TranscodeException as e:
                        logging.error(f"Failed to transcode {flac_path}: {e}")
                        # Consider continuing with next file or handling the error as needed
                elif file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    resize_image(os.path.join(root, file))
        # Create torrent for the album
        make_torrent(output_album_path, config)

def make_torrent(album_path, config):
    """
    Create a torrent file for the transcoded album.
    """
    torrent_name = f"{os.path.basename(album_path)}.torrent"
    torrent_path = os.path.join(config['torrent_dir'], torrent_name)
    torrent_copy_path = os.path.join(config['torrent_copy_dir'], torrent_name)
    command = f"mktorrent -l 21 -p -a {config['announce_url']} -o {shlex.quote(torrent_path)} {shlex.quote(album_path)}"
    run_command(command)
    shutil.copy(torrent_path, torrent_copy_path)
    logging.info(f"Created torrent: {torrent_path} and copied to {torrent_copy_path}")

def main():
    # Load configuration
    config = configparser.ConfigParser()
    config.read('config.ini')
    config = {section: dict(config.items(section)) for section in config.sections()}

    # Transcode each album
    for album_path in os.listdir(config['AB']['data_dir']):
        full_album_path = os.path.join(config['AB']['data_dir'], album_path)
        if os.path.isdir(full_album_path):
            transcode_album(full_album_path, config['AB'])

if __name__ == "__main__":
    main()
