import os
import re

def process_file(filepath):
    with open(filepath, 'r') as file:
        lines = file.readlines()

    id_value = ''
    title_value = ''
    in_content = False
    new_lines = []
    content_lines = []
    for line in lines:
        # Check for id
        id_match = re.match(r'^id:\s*(.*)', line)
        if id_match:
            id_value = id_match.group(1).strip()
        # Check for title
        title_match = re.match(r'^title:\s*(.*)', line)
        if title_match:
            title_value = title_match.group(1).strip()
        # Check for content start
        content_start_match = re.match(r'^content:\s*>\s*', line)
        if content_start_match:
            in_content = True
            new_lines.append(line)
            continue

        # Process content lines
        if in_content:
            # Check if line is indented (part of content)
            if line.startswith('  ') or line.strip() == '':
                # Process content line
                line_stripped = line.strip()
                macro_line = re.match(r'^\| `([^`]+)`$', line_stripped)
                if macro_line:
                    macro_name = macro_line.group(1)
                    # Determine if this macro should be removed
                    if should_remove_macro(macro_name, id_value, title_value):
                        continue  # Skip this line
                content_lines.append(line)
            else:
                # End of content section
                in_content = False
                # Append processed content lines
                new_lines.extend(content_lines)
                content_lines = []
                new_lines.append(line)
        else:
            new_lines.append(line)

    # If we were still in content section at the end
    if in_content:
        new_lines.extend(content_lines)

    # Write back the updated content to the file
    with open(filepath, 'w') as file:
        file.writelines(new_lines)

def should_remove_macro(macro_name, id_value, title_value):
    # Remove 'nh-aw_escu_' prefix from id and title to get base names
    base_id = id_value.replace('nh-aw_escu_', '')
    base_title = title_value.replace('nh-aw_escu_', '')

    # Construct macro names to remove
    macro_names_to_remove = set()
    macro_names_to_remove.add(base_id + '_filter')
    macro_names_to_remove.add(base_title + '_filter')

    # Exclude macro names that contain 'nh-aw_escu', '_input_filter', or '_output_filter'
    macro_names_to_remove = {name for name in macro_names_to_remove if
                             'nh-aw_escu' not in name and
                             '_input_filter' not in name and
                             '_output_filter' not in name}

    # Check if the macro_name matches any of the macro_names_to_remove
    return macro_name in macro_names_to_remove

def process_directory(directory):
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.yaml') or filename.endswith('.yml'):
                filepath = os.path.join(root, filename)
                process_file(filepath)

if __name__ == '__main__':
    directory = "# Replace this with your directory path"
    process_directory(directory)
