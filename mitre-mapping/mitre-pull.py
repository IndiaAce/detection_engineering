import os
import yaml
import csv
import logging
from pathlib import Path
import argparse
# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
# Define the directory path
default_directory = '/workspaces/goldenanchor/Content_Search/Splunk'
# Load blacklist configuration
def load_blacklist(config_file):
   with open(config_file, 'r') as file:
       config = yaml.safe_load(file)
   return config.get('blacklist_folders', []), config.get('blacklist_files', [])
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
# Initialize the script with command-line arguments
def init_argparse():
   parser = argparse.ArgumentParser(description="YAML to CSV parser with blacklists")
   parser.add_argument('directory', nargs='?', default=default_directory, help="Directory to scan for YAML files")
   parser.add_argument('--config', default='blacklist_config.yml', help="Path to the blacklist configuration file")
   parser.add_argument('--mitre', default='mitre_attack_patterns.txt', help="Path to the MITRE attack patterns file")
   return parser
# Main function
def main():
   parser = init_argparse()
   args = parser.parse_args()
   directory = Path(args.directory)
   config_file = args.config
   mitre_file = args.mitre
   # Load blacklists
   blacklist_folders, blacklist_files = load_blacklist(config_file)
   # Load MITRE attack patterns
   mitre_patterns = load_mitre_attack_patterns(mitre_file)
   # Initialize a list to store the rows for the CSV
   rows = []
   # Walk through the directory and its subdirectories
   for root, dirs, files in os.walk(directory):
       # Remove blacklisted folders from the list of directories to traverse
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
                               for mitre_id in mitre_attack_ids:
                                   attack_name = mitre_patterns.get(mitre_id, "Unknown")
                                   rows.append([id_value, mitre_id, attack_name, description_value])
                           else:
                               attack_name = mitre_patterns.get(mitre_attack_ids, "Unknown")
                               rows.append([id_value, mitre_attack_ids, attack_name, description_value])
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
           csvwriter.writerow(['ID', 'MITRE ATT&CK ID', 'Attack Name', 'Description'])
           # Write the rows
           csvwriter.writerows(rows)
       logging.info(f"CSV file {csv_file} created successfully.")
   except Exception as e:
       logging.error(f"Error writing to CSV file {csv_file}: {e}")
if __name__ == "__main__":
   main()

'''
Please add a way to do the following:

If a search in the catalog has these fields in the yaml: 
resource_dependencies:
    - resource_type: csv
    resource_key: Content_Resources/ThreatFeeds/<nameoffile>.csv

It will have the following style in the CSV, please ONLY pull out the mitre_technique_id and use that as the populated Mitre id in the output CSV. There will be some alert IDs with close to 40+ ttps, just treat them just like any other ID that has multiple ttps
"description","process_string","severity","mitre_technique_id","mitre_tactic","mitre_technique","tickets"
"Creates BITS transfer jobs","Start-BitsTransfer","low","T1197","Persistence","BITS Jobs","Ticket-123"
'''