import os
import yaml
import re

EXCLUDED_MACROS = [
    r"nh-aw_shadow_package",
    r"nh-aw_macro_placeholder",
    r"security_content_summariesonly",
    r"security_content_ctime\(firstTime\)",
    r"security_content_ctime\(lastTime\)",
    r"drop_dm_object_name\(.+\)"
]

def snake_case(string):
    return re.sub(r'\W|^(?=\d)', "_", string).lower()

def validate_mitre_id(mitre_id):
    """Validate the MITRE ID format."""
    return bool(re.match(r'^T\d{4}(\.\d{3})?$', mitre_id))

def load_detections(repo_path, mitre_id):
    detections = []
    subdirectories = ['application', 'cloud', 'endpoint', 'network', 'web']
    for subdir in subdirectories:
        subdir_path = os.path.join(repo_path, 'detections', subdir)
        for root, _, files in os.walk(subdir_path):
            for file in files:
                if file.endswith('.yml'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        try:
                            detection = yaml.safe_load(f)
                        except yaml.YAMLError as exc:
                            print(f"Error parsing YAML file {file_path}: {exc}")
                            continue
                        if 'tags' in detection and 'mitre_attack_id' in detection['tags']:
                            mitre_ids = detection['tags']['mitre_attack_id']
                            if mitre_id in mitre_ids:
                                detections.append(detection)
    return detections

def create_macro_file(macro_name, macro_dir, content="```empty macro for tuning```"):
    sanitized_macro_name = re.sub(r'[\\/*?:"<>|]', "_", macro_name)
    macro_file_path = os.path.join(macro_dir, f"{sanitized_macro_name}.yml")
    os.makedirs(macro_dir, exist_ok=True)
    macro_content = {
        'id': f"{sanitized_macro_name}",
        'catalog_type': "macro",
        'content': content
    }
    with open(macro_file_path, 'w') as f:
        f.write(f"id: {macro_content['id']}\n")
        f.write(f"catalog_type: {macro_content['catalog_type']}\n")
        f.write(f"content: >\n")
        f.write(f"  {macro_content['content']}\n")
    print(f"Created macro YML file: {macro_file_path}")

def create_correlation_search_file(escu_id, title, description, mitre_attack_ids, tuning_macros, content, required_fields, output_dir):
    file_path = os.path.join(output_dir, f"{escu_id}.yml")
    correlation_search_content = {
        'id': escu_id,
        'title': escu_id,
        'catalog_type': "correlation_search",
        'description': description,
        'mitre_attack_id': mitre_attack_ids,
        'authorization_scope': "detection",
        'throttle_timeframe': "14400s",
        'tuning_macros': tuning_macros,
        'content': content,
        'required_fields': required_fields
    }
    with open(file_path, 'w') as f:
        f.write(f"id: {correlation_search_content['id']}\n")
        f.write(f"title: {correlation_search_content['title']}\n")
        f.write(f"catalog_type: {correlation_search_content['catalog_type']}\n")
        f.write(f"description: >\n  {correlation_search_content['description']}\n")
        f.write(f"mitre_attack_id:\n")
        for mitre_id in correlation_search_content['mitre_attack_id']:
            f.write(f"  - {mitre_id}\n")
        f.write(f"authorization_scope: {correlation_search_content['authorization_scope']}\n")
        f.write(f"throttle_timeframe: {correlation_search_content['throttle_timeframe']}\n")
        f.write(f"tuning_macros:\n")
        for macro in correlation_search_content['tuning_macros']:
            f.write(f"  - {macro}\n")
        if correlation_search_content['required_fields']:
            f.write(f"required_fields: {{\n")
            for field in correlation_search_content['required_fields']:
                f.write(f"  {field}: ~,\n")
            f.write(f"}}\n")
        f.write(f"content: >\n")
        parts = re.split(r'(\|)', correlation_search_content['content'])
        current_line = ''
        for part in parts:
            if part == '|':
                if current_line.strip():
                    f.write(f"  {current_line.strip()}\n")
                current_line = '|'
            else:
                current_line += part
        if current_line.strip():
            f.write(f"  {current_line.strip()}\n")
    print(f"Created correlation search YML file: {file_path}")

def load_macro_definitions(macro_dir):
    macro_definitions = {}
    for root, _, files in os.walk(macro_dir):
        for file in files:
            if file.endswith('.yml'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    try:
                        macro_content = yaml.safe_load(f)
                        if macro_content:
                            if 'name' in macro_content and 'definition' in macro_content:
                                macro_definitions[macro_content['name']] = macro_content['definition']
                            else:
                                print(f"Unexpected structure in file: {file_path}")
                    except yaml.YAMLError as exc:
                        print(f"Error parsing YAML file {file_path}: {exc}")
                        continue
    print(f"Loaded Macros: {macro_definitions.keys()}")
    return macro_definitions

def expand_macros_in_spl(spl_content, macro_definitions, excluded_macros):
    def replace_macro(match):
        macro_name = match.group(1)
        if any(re.match(excluded_macro, macro_name) for excluded_macro in EXCLUDED_MACROS):
            print(f"Excluding macro: `{macro_name}`")
            return f'`{macro_name}`'
        if macro_name in macro_definitions:
            print(f"Expanding macro: `{macro_name}` -> ({macro_definitions[macro_name]})")
            return f"({macro_definitions[macro_name]})"
        print(f"Macro not found for expansion: `{macro_name}`")
        return f'`{macro_name}`'
    return re.sub(r'`([^`]+)`', replace_macro, spl_content)

def process_filters_in_spl(spl_content, detection_id, macro_definitions):
    lines = spl_content.strip().split('\n')
    new_lines = []
    base_macro_names = set()
    input_filter_pattern = re.compile(r'^\s*\|\s*`nh-aw_escu_(.+?)_input_filter`')
    for line in lines:
        match = input_filter_pattern.match(line)
        if match:
            base_name = match.group(1)
            base_macro_names.add(base_name)
    filter_pattern = re.compile(r'^\s*\|\s*`(.+?)_filter`')
    for line in lines:
        match = filter_pattern.match(line)
        if match:
            filter_name = match.group(1)
            if filter_name in base_macro_names:
                continue
        new_lines.append(line)
    expanded_spl = expand_macros_in_spl('\n'.join(new_lines), macro_definitions, EXCLUDED_MACROS)
    expanded_spl += f'\n| `{detection_id}_input_filter`'
    expanded_spl += f'\n| `{detection_id}_output_filter`'
    return expanded_spl

def should_exclude_detection(detection):
    search_content = detection.get('search', {})
    if isinstance(search_content, dict):
        original_search = search_content.get('search', '')
    else:
        original_search = search_content
    if '| tstats' not in original_search:
        print(f"Excluding detection {detection['name']} as it does not contain '| tstats'")
        return True
    return False

def organize_detections_by_id(detections, global_macro_dir, macro_dir_base, output_dir_base, user_entered_ttp, macro_definitions):
    for detection in detections:
        if should_exclude_detection(detection):
            continue
        name_snake_case = snake_case(detection['name'])
        detection_id = f"nh-aw_escu_{name_snake_case}"
        ttp_name = user_entered_ttp
        macro_dir_ttp = os.path.join(macro_dir_base, ttp_name)
        output_dir_ttp = os.path.join(output_dir_base, ttp_name)
        os.makedirs(macro_dir_ttp, exist_ok=True)
        os.makedirs(output_dir_ttp, exist_ok=True)
        print(f"Processing detection: {detection['name']}")
        search_content = detection.get('search', {})
        if isinstance(search_content, dict):
            original_search = search_content.get('search', '')
        else:
            original_search = search_content
        if not original_search:
            print(f"Warning: No search content found for detection {detection['name']}")
            continue
        expanded_search = expand_macros_in_spl(original_search, macro_definitions, EXCLUDED_MACROS)
        modified_search = process_filters_in_spl(expanded_search, detection_id, macro_definitions)
        tuning_macros = [f"{detection_id}_input_filter", f"{detection_id}_output_filter"]
        create_macro_file(f"{detection_id}_input_filter", macro_dir_ttp)
        create_macro_file(f"{detection_id}_output_filter", macro_dir_ttp)
        required_fields = detection.get('required_fields', [])
        required_fields = [field for field in required_fields if field != '_time']
        create_correlation_search_file(
            escu_id=detection_id,
            title=detection['name'],
            description=detection.get('description', ''),
            mitre_attack_ids=detection['tags'].get('mitre_attack_id', []),
            tuning_macros=tuning_macros,
            content=modified_search,
            required_fields=required_fields,
            output_dir=output_dir_ttp
        )

def main():
    repo_path = r"# path to \escu-baseline\security_content"
    global_macro_dir = os.path.join(repo_path, 'macros')
    macro_dir_base = r"#path to \escu-baseline\ESCU_Macros"
    output_dir_base = r"#path to escu-baseline\ESCU_Detections"
    macro_definitions = load_macro_definitions(global_macro_dir)
    mitre_id = input("Enter the MITRE TTP ID (e.g., T1003 or T1003.001): ").strip()
    if not validate_mitre_id(mitre_id):
        print("Error: Invalid MITRE TTP ID format. Please use TXXXX or TXXXX.XXX format.")
        return
    detections = load_detections(repo_path, mitre_id)
    if not detections:
        print(f"No detections found for MITRE TTP ID: {mitre_id}")
        return
    organize_detections_by_id(detections, global_macro_dir, macro_dir_base, output_dir_base, mitre_id, macro_definitions)
    print("\nAll matched detections processed and saved successfully.")

if __name__ == "__main__":
    main()
