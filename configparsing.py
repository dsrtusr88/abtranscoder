import configparser

def parse_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    data_dir = config.get('AB', 'data_dir')
    output_dir = config.get('AB', 'output_dir')
    announce_url = config.get('torrent', 'announce_url')
    # Add parsing for other config parameters
    return data_dir, output_dir, announce_url

data_dir, output_dir, announce_url = parse_config('config.ini')
