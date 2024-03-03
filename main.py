import os
import subprocess
import configparser
import mutagen.flac
import shutil
from multiprocessing import Pool
from PIL import Image

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Define global variables from config
DATA_DIR = config.get('AB', 'data_dir')
OUTPUT_DIR = config.get('AB', 'output_dir')
TORRENT_DIR = config.get('AB', 'torrent_dir')
TORRENT_COPY_DIR = config.get('AB', 'torrent_copy_dir')
ANNOUNCE_URL = config.get('torrent', 'announce_url')
PIECE_SIZE = config.get('torrent', 'piece_size')
OUTPUT_FORMATS = config.get('transcode', 'output_format').split(',')
MAX_THREADS = config.getint('transcode', 'max_threads')

# Encoders and options
encoders = {
    'V0': {'enc': 'lame', 'ext': '.mp3', 'opts': '-V 0 --vbr-new --ignore-tag-errors'},
    'FLAC': {'enc': 'flac', 'ext': '.flac', 'opts': '--best'}
}

def run_command(command):
    try:
        subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e.output.decode()}")
        raise

def is_24bit(flac_file):
    flac_info = mutagen.flac.FLAC(flac_file)
    return flac_info.info.bits_per_sample > 16

def transcode(flac_file, output_format):
    base_name = os.path.splitext(os.path.basename(flac_file))[0]
    output_ext = encoders[output_format]['ext']
    output_file = os.path.join(OUTPUT_DIR, output_format, base_name + output_ext)

    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))

    if output_format == 'FLAC' and is_24bit(flac_file):
        # Resample and downmix if necessary
        command = f"sox {flac_file} -G -b 16 {output_file} rate -v -L 44100 dither"
    else:
        # Transcode to specified format
        command = f"ffmpeg -i {flac_file} {encoders[output_format]['opts']} {output_file}"

    run_command(command)

def create_torrent(album_path):
    album_name = os.path.basename(album_path)
    torrent_name = f"{album_name}.torrent"
    torrent_path = os.path.join(TORRENT_DIR, torrent_name)
    command = f"mktorrent -l {PIECE_SIZE} -p -a {ANNOUNCE_URL} -o {torrent_path} {album_path}"
    run_command(command)
    if TORRENT_COPY_DIR:
        shutil.copy(torrent_path, os.path.join(TORRENT_COPY_DIR, torrent_name))

def process_album(album_path):
    for output_format in OUTPUT_FORMATS:
        flac_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(album_path) for f in filenames if f.endswith('.flac')]
        with Pool(processes=MAX_THREADS) as pool:
            pool.starmap(transcode, [(flac_file, output_format) for flac_file in flac_files])
    create_torrent(album_path)

def main():
    for root, dirs, files in os.walk(DATA_DIR):
        for dir in dirs:
            album_path = os.path.join(root, dir)
            process_album(album_path)

if __name__ == "__main__":
    main()
