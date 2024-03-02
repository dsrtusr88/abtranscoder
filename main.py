import os
import subprocess
import shutil
import configparser

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')

    source_folder = config.get('AB', 'data_dir')
    output_folder = config.get('AB', 'output_dir')
    torrent_folder = config.get('AB', 'torrent_dir')
    torrent_copy_folder = config.get('AB', 'torrent_copy_dir')

    # Your logic here...

if __name__ == "__main__":
    main()
