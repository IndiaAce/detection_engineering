import os
import yaml
import csv
import logging
from pathlib import Path
import argparse

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

# Define the base directory path and Docker environment base path
default_directory = '/workspaces/goldenanchor/Content_Search/Splunk'
base_path = '/workspaces/goldenanchor/'  # Base path inside Docker container

# Directories to exclude
EXCLUDE_DIRECTORIES = {'WrenchSearche'}  # Modular exclusion list

# Load MITRE attack patterns from file
def load_mitre_attack_patterns(file_path):
    mitre_patterns = {}
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines[1:]:  # Skip the first line
            name, external_id = line.strip().split(', External ID: ')
            external_id = external_id.replace('External ID: ', '')
            mitre_patterns[external_id] = name.replace('Name: ', '')
    return mitre_patterns

# Load MITRE IDs from CSV in ThreatFeeds
def load_mitre_from_csv(file_path):
    mitre_ids = []
    try:
        with open(file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                mitre_id = row.get('mitre_technique_id')
                if mitre_id and mitre_id != 'T0000':  # Exclude 'Unknown' TTPs
                    mitre_ids.append(mitre_id)
    except Exception as e:
        logging.error(f"Error reading MITRE IDs from CSV file {file_path}: {e}")
    return mitre_ids

# Initialize the script with command-line arguments
def init_argparse():
    parser = argparse.ArgumentParser(description="YAML to CSV parser with exclusions")
    parser.add_argument('directory', nargs='?', default=default_directory, help="Directory to scan for YAML files")
    parser.add_argument('--mitre', default='mitre_attack_patterns.txt', help="Path to the MITRE attack patterns file")
    return parser

# Deduplication function
def is_duplicate(entry, seen_entries):
    """Check if an entry is already in the seen entries set."""
    entry_key = (entry[0], entry[1])  # (id_value, mitre_id)
    if entry_key in seen_entries:
        return True
    seen_entries.add(entry_key)
    return False

# Main function
def main():
    parser = init_argparse()
    args = parser.parse_args()
    directory = Path(args.directory)
    mitre_file = args.mitre

    # Load MITRE attack patterns
    mitre_patterns = load_mitre_attack_patterns(mitre_file)

    # Initialize a list to store the rows for the CSV
    rows = []
    seen_entries = set()  # Set to track unique (id, TTP) pairs

    # Walk through the directory and its subdirectories
    for root, dirs, files in os.walk(directory):
        # Remove excluded folders from the list of directories to traverse
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRECTORIES]
        for file in files:
            if file.endswith('.yml'):
                file_path = Path(root) / file
                try:
                    with open(file_path, 'r') as ymlfile:
                        content = yaml.safe_load(ymlfile)
                        if 'id' in content and 'mitre_attack_id' in content and 'description' in content:
                            id_value = content['id']
                            description_value = content['description']
                            mitre_attack_ids = content['mitre_attack_id']

                            if 'resource_dependencies' in content:
                                # Check for resource dependencies pointing to ThreatFeeds CSV
                                for dependency in content['resource_dependencies']:
                                    if dependency['resource_type'] == 'csv' and 'resource_key' in dependency:
                                        # Construct the correct file path for the Docker container
                                        csv_file_path = Path(base_path) / dependency['resource_key']
                                        if csv_file_path.exists():
                                            # Extract MITRE IDs from the CSV
                                            extracted_mitre_ids = load_mitre_from_csv(csv_file_path)
                                            for mitre_id in extracted_mitre_ids:
                                                attack_name = mitre_patterns.get(mitre_id, "Unknown")
                                                row = [id_value, mitre_id, attack_name, description_value, str(root)]
                                                if not is_duplicate(row, seen_entries):
                                                    rows.append(row)
                                            # Skip further processing for this file as it is handled
                                            continue

                            # Process regular mitre_attack_ids
                            if isinstance(mitre_attack_ids, list):
                                for mitre_id in mitre_attack_ids:
                                    attack_name = mitre_patterns.get(mitre_id, "Unknown")
                                    row = [id_value, mitre_id, attack_name, description_value, str(root)]
                                    if not is_duplicate(row, seen_entries):
                                        rows.append(row)
                            else:
                                attack_name = mitre_patterns.get(mitre_attack_ids, "Unknown")
                                row = [id_value, mitre_attack_ids, attack_name, description_value, str(root)]
                                if not is_duplicate(row, seen_entries):
                                    rows.append(row)

                except yaml.YAMLError as exc:
                    logging.error(f"Error parsing YAML file {file_path}: {exc}")
                except Exception as e:
                    logging.error(f"Unexpected error processing file {file_path}: {e}")

    # Define the CSV file name
    csv_file = 'TTP_Coverage.csv'

    # Write the rows to the CSV file
    try:
        with open(csv_file, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            # Write the header
            csvwriter.writerow(['ID', 'MITRE ATT&CK ID', 'Attack Name', 'Description', 'Directory'])
            # Write the rows
            csvwriter.writerows(rows)
        logging.info(f"CSV file {csv_file} created successfully.")
    except Exception as e:
        logging.error(f"Error writing to CSV file {csv_file}: {e}")

if __name__ == "__main__":
    main()
