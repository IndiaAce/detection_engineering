import os
import yaml
import csv
import logging
from pathlib import Path
import argparse

# Setup logging - can make more verbose depending on how long the script stays in
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

default_directory = 'specify/file/path/here'

# There is a blacklist file named blacklist_config.yml - edit that to have the script pass over files/directories
def load_blacklist(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config.get('blacklist_folders', []), config.get('blacklist_files', [])

def init_argparse():
    parser = argparse.ArgumentParser(description="YAML to CSV parser with blacklists")
    parser.add_argument('directory', nargs='?', default=default_directory, help="Directory to scan for YAML files")
    parser.add_argument('--config', default='blacklist_config.yml', help="Path to the blacklist configuration file")
    return parser

def main():
    parser = init_argparse()
    args = parser.parse_args()

    directory = Path(args.directory)
    config_file = args.config

    blacklist_folders, blacklist_files = load_blacklist(config_file)

    rows = []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in blacklist_folders]

        for file in files:
            if file.endswith('.yml') and file not in blacklist_files:
                file_path = Path(root) / file
                try:
                    with open(file_path, 'r') as ymlfile:
                        content = yaml.safe_load(ymlfile)
                        if 'id' in content and 'mitre_attack_id' in content and 'description' in content:
                            id_value = content['id']
                            description_value = content['description']
                            mitre_attack_ids = content['mitre_attack_id']
                            if isinstance(mitre_attack_ids, list):
                                mitre_attack_ids = ', '.join(mitre_attack_ids)
                            rows.append([id_value, mitre_attack_ids, description_value])
                except yaml.YAMLError as exc:
                    logging.error(f"Error parsing YAML file {file_path}: {exc}")
                except Exception as e:
                    logging.error(f"Unexpected error processing file {file_path}: {e}")
    csv_file = 'TTP_Coverage.csv'
    try:
        with open(csv_file, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(['ID', 'MITRE ATT&CK ID', 'Description'])
            csvwriter.writerows(rows)
        logging.info(f"CSV file {csv_file} created successfully.")
    except Exception as e:
        logging.error(f"Error writing to CSV file {csv_file}: {e}")

if __name__ == "__main__":
    main()
