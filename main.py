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

logging.basicConfig(filename='/app/main.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')
logging.info("Starting main.py...")

# Configuration for different output formats
encoders = {
    '320': {'enc': 'lame', 'ext': '.mp3', 'opts': '-h -b 320 --ignore-tag-errors'},
    'V0': {'enc': 'lame', 'ext': '.mp3', 'opts': '-V 0 --vbr-new --ignore-tag-errors'},
    'FLAC': {'enc': 'sox', 'ext': '.flac', 'opts': '--best'}  # Using sox for FLAC to handle resampling
}

# Custom exception for handling transcoding errors
class TranscodeException(Exception):
    pass

# Function to execute a command in the shell
def run_command(command):
    print(f"Executing command: {command}")  # Debugging: print command being executed
    try:
        subprocess.check_call(shlex.split(command), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e.output}")  # Debugging: print error if command fails
        raise

# Locate files within a directory matching specified extensions
def locate_files(root_dir, extensions):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in extensions):
                yield os.path.join(dirpath, filename)

# Resize images to specified dimensions
def resize_image(image_path, max_size=(800, 600)):
    try:
        with Image.open(image_path) as img:
            img.thumbnail(max_size, Image.ANTIALIAS)
            img.save(image_path)
            print(f"Resized image: {image_path}")  # Debugging: indicate image has been resized
    except Exception as e:
        print(f"Error resizing image {image_path}: {e}")  # Debugging: print error if resizing fails

# Resize all images in a directory
def resize_images(directory):
    for image_path in locate_files(directory, ['.jpg', '.jpeg', '.png']):
        resize_image(image_path)

# Transcode FLAC files to specified format
def transcode(flac_file, output_dir, output_format, config):
    print(f"Transcoding: {flac_file} to {output_format}")  # Debugging: indicate file being transcoded
    flac_info = mutagen.flac.FLAC(flac_file)
    sample_rate = flac_info.info.sample_rate
    bits_per_sample = flac_info.info.bits_per_sample
    channels = flac_info.info.channels

    # Determine if resampling is needed based on sample rate and bit depth
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

# Create a torrent file for the directory
def make_torrent(input_dir, config):
    torrent_dir = config.get('Paths', 'torrent_dir')
    announce_url = config.get('Torrent', 'announce_url')
    piece_size = config.get('Torrent', 'piece_size')
    torrent_file_name = f"{os.path.basename(input_dir)}.torrent"
    torrent_file_path = os.path.join(torrent_dir, torrent_file_name)

    print(f"Creating torrent for directory: {input_dir}")  # Debugging: indicate torrent creation
    cmd = f"mktorrent -l {piece_size} -p -a \"{announce_url}\" -o \"{torrent_file_path}\" \"{input_dir}\""
    run_command(cmd)

# Process each album in the data directory
def process_album(album_path, config):
    for output_format in ['FLAC', '320', 'V0']:
        output_dir = os.path.join(config.get('Paths', 'output_dir'), output_format)
        os.makedirs(output_dir, exist_ok=True)

        for flac_file in locate_files(album_path, ['.flac']):
            try:
                transcode(flac_file, output_dir, output_format, config)
            except Exception as e:
                print(f"Error during processing {flac_file}: {e}")  # Debugging: print error during transcoding

        resize_images(album_path)  # Resize images after transcoding
        make_torrent(output_dir, config)  # Create a torrent for the processed album

# Main function to read configuration and process albums
def main():
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Accessing the config using the actual section names and keys from your provided config.ini
    data_dir = config.get('AB', 'data_dir')
    output_dir = config.get('AB', 'output_dir')
    torrent_dir = config.get('AB', 'torrent_dir')
    torrent_copy_dir = config.get('AB', 'torrent_copy_dir')

    announce_url = config.get('torrent', 'announce_url')
    piece_size = config.get('torrent', 'piece_size')

    output_formats = config.get('transcode', 'output_format').split(',')
    max_threads = config.getint('transcode', 'max_threads')

    # Proceed with the rest of your script using these variables as needed

if __name__ == "__main__":
    main()
