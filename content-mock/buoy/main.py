#!/Users/luke/anaconda3/bin/python
import os
import yaml
import subprocess
from datetime import datetime, timedelta
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import FoldedScalarString, PlainScalarString
from ruamel.yaml.comments import CommentedMap
from PySide6.QtWidgets import QApplication, QMainWindow, QComboBox, QListWidget, QVBoxLayout, QWidget, QMessageBox, QPushButton, QFormLayout, QLineEdit, QDialog, QDialogButtonBox, QComboBox
import re

def run_git_command(command, cwd=None):
    try:
        result = subprocess.run(command, cwd=cwd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode().strip()
    except subprocess.CalledProcessError as e:
        QMessageBox.critical(None, "Git Error", f"Command '{command}' failed:\n{e.stderr.decode().strip()}")
        return None

def checkout_main_and_create_branch(branch_name):
    if not run_git_command('git checkout main'):
        return False
    if not run_git_command('git pull'):
        return False
    if not run_git_command(f'git checkout -b {branch_name}'):
        return False
    return True

def commit_and_push_changes(client_name, nms_number, reason, branch_name):
    if not run_git_command(f'git add client/{client_name}/.'):
        return False
    commit_message = f'{nms_number}: {reason}'
    if not run_git_command(f'git commit -m "{commit_message}"'):
        return False
    if not run_git_command(f'git push -u origin {branch_name}'):
        return False
    return True

def handle_existing_branch_operations(branch_name, client_name, nms_number, reason):
    if not run_git_command(f'git checkout {branch_name}'):
        QMessageBox.critical(None, "Git Error", f"Branch '{branch_name}' does not exist.")
        return False
    if not run_git_command('git pull'):
        return False
    if not run_git_command(f'git add client/{client_name}/.'):
        return False
    commit_message = f'{nms_number}: {reason}'
    if not run_git_command(f'git commit -m "{commit_message}"'):
        return False
    if not run_git_command(f'git push'):
        return False
    return True

def format_yaml_string(yaml_string):
    # Remove single quotes from '# Creator of suppression' key
    yaml_string = re.sub(r"'# Creator of suppression':", "# Creator of suppression:", yaml_string)

    # Replace `>-` with `>`
    yaml_string = re.sub(r">-\n", ">\n", yaml_string)
    
    return yaml_string

# GUI Elements

class SuppressionFormDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add New Suppression")
        self.layout = QFormLayout()

        self.ticket_input = QLineEdit(self)
        self.reason_input = QLineEdit(self)
        self.spl_input = QLineEdit(self)

        self.layout.addRow("NMS Ticket Number:", self.ticket_input)
        self.layout.addRow("Reason:", self.reason_input)
        self.layout.addRow("SPL Query:", self.spl_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.setLayout(self.layout)

    def get_inputs(self):
        return self.ticket_input.text(), self.reason_input.text(), self.spl_input.text()

class SimpleTuneDialog(QDialog):
    def __init__(self, alert_ids):
        super().__init__()
        self.setWindowTitle("Simple Tune Suppression")
        self.layout = QFormLayout()

        self.alert_id_selector = QComboBox(self)
        self.alert_id_selector.addItems(alert_ids)

        self.field_selector = QComboBox(self)
        self.field_selector.addItems(["dest", "host", "user"])

        self.value_input = QLineEdit(self)

        self.layout.addRow("Select Alert ID:", self.alert_id_selector)
        self.layout.addRow("Select Field:", self.field_selector)
        self.layout.addRow("Enter Value:", self.value_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.setLayout(self.layout)

    def get_inputs(self):
        return self.alert_id_selector.currentText(), self.field_selector.currentText(), self.value_input.text()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Client Alerts Viewer")
        
        self.layout = QVBoxLayout()
        self.client_selector = QComboBox(self)
        self.client_selector.setEditable(True)
        self.populate_clients()
        self.alert_list = QListWidget(self)

        self.clear_button = QPushButton("Clear Selection", self)
        self.clear_button.clicked.connect(self.clear_selection)
        self.layout.addWidget(self.clear_button)

        self.add_suppression_button = QPushButton("Add Suppression", self)
        self.add_suppression_button.clicked.connect(self.add_suppression)
        self.layout.addWidget(self.add_suppression_button)

        self.simple_tune_button = QPushButton("Simple Tune", self)
        self.simple_tune_button.clicked.connect(self.simple_tune)
        self.layout.addWidget(self.simple_tune_button)

        self.client_selector.currentTextChanged.connect(self.on_client_selected)
        self.layout.addWidget(self.client_selector)
        self.layout.addWidget(self.alert_list)
        
        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

    def clear_selection(self):
        self.client_selector.setCurrentIndex(-1)
        self.alert_list.clear()

    def populate_clients(self):
        client_base_path = '/Users/luke/Documents/dev_link/detection_engineering/content-mock/client/'
        client_dirs = [d for d in os.listdir(client_base_path) if os.path.isdir(os.path.join(client_base_path, d))]
        self.client_selector.addItems(client_dirs)

    def on_client_selected(self, client_name):
        client_base_path = '/Users/luke/Documents/dev_link/detection_engineering/content-mock/client/'
        client_dir = os.path.join(client_base_path, client_name)
        
        if not os.path.exists(client_dir) or not os.path.isdir(client_dir):
            QMessageBox.critical(self, "Error", f"Client '{client_name}' does not exist in the specified path.")
            return 
        
        ids = read_alerts_file(client_dir)
        if not ids:
            QMessageBox.warning(self, "No Alerts", f"No valid alerts found for client '{client_name}'.")
        
        self.alert_list.clear()
        self.alert_list.addItems(ids)
    
    def add_suppression(self):
        client_name = self.client_selector.currentText()
        alert_name = self.alert_list.currentItem().text() if self.alert_list.currentItem() else None
        
        if not client_name or not alert_name:
            QMessageBox.warning(self, "Selection Required", "Please select a client and an alert.")
            return

        form_dialog = SuppressionFormDialog()
        if form_dialog.exec() == QDialog.Accepted:
            nms_ticket, reason, spl = form_dialog.get_inputs()
            
            if not nms_ticket or not reason or not spl:
                QMessageBox.warning(self, "Input Required", "All fields are required.")
                return

            suppression_id = f"{nms_ticket}_{client_name}_{alert_name.replace(' ', '_').lower()}"
            current_user = subprocess.check_output('whoami', shell=True).decode().strip()

            new_suppression = CommentedMap({
                'id': suppression_id,
                'properties': CommentedMap({
                    PlainScalarString('# Creator of suppression'): current_user,
                    'owner': 'nobody',
                    'search': FoldedScalarString(spl.strip())
                })
            })

            self.update_suppressions_file(client_name, new_suppression)

            branch_name = f"suppression_{nms_ticket}"
            if checkout_main_and_create_branch(branch_name):
                if commit_and_push_changes(client_name, nms_ticket, reason, branch_name):
                    QMessageBox.information(self, "Success", f"Suppression added and pushed to branch '{branch_name}'!")

    def simple_tune(self):
        client_name = self.client_selector.currentText()
        if not client_name:
            QMessageBox.warning(self, "Selection Required", "Please select a client.")
            return
        
        alert_ids = [self.alert_list.item(i).text() for i in range(self.alert_list.count())]
        if not alert_ids:
            QMessageBox.warning(self, "No Alerts", "No alerts available to tune.")
            return

        simple_tune_dialog = SimpleTuneDialog(alert_ids)
        if simple_tune_dialog.exec() == QDialog.Accepted:
            alert_id, field, value = simple_tune_dialog.get_inputs()

            if not alert_id or not field or not value:
                QMessageBox.warning(self, "Input Required", "All fields are required.")
                return

            # Calculate Unix time for one week from now
            one_week_from_now = datetime.now() + timedelta(weeks=1)
            unix_time = int(one_week_from_now.timestamp())

            # Create SPL query for simple tune suppression with dynamic Unix time
            spl = f'`notable_index` source={alert_id} {field}="{value}" _time > {unix_time}'.strip()

            # Generate Suppression ID and owner
            suppression_id = f"simple_tune_{alert_id.replace(' ', '_').lower()}_{field}_{value}"
            current_user = subprocess.check_output('whoami', shell=True).decode().strip()

            # Create the suppression data structure
            new_suppression = CommentedMap({
                'id': suppression_id,
                'properties': CommentedMap({
                    PlainScalarString('# Creator of suppression'): current_user,
                    'owner': 'nobody',
                    'search': FoldedScalarString(spl.strip())
                })
            })

            self.update_suppressions_file(client_name, new_suppression)

            QMessageBox.information(self, "Success", f"Simple tune suppression added for '{alert_id}' on field '{field}'!")

    def update_suppressions_file(self, client_name, new_suppression):
        client_base_path = '/Users/luke/Documents/dev_link/detection_engineering/content-mock/client/'
        suppressions_file = os.path.join(client_base_path, client_name, 'suppressions.yml')
        
        yaml = YAML()
        yaml.preserve_quotes = True  
        
        # Load existing suppressions or initialize new structure
        if os.path.exists(suppressions_file):
            with open(suppressions_file, 'r') as file:
                data = yaml.load(file) or {'suppression': {'include': []}}
        else:
            data = {'suppression': {'include': []}}

        # Add the new suppression to the list
        data['suppression']['include'].append(new_suppression)

        # Serialize the YAML to a string
        yaml_string = yaml.dump(data)

        # Format the YAML string to remove single quotes and change >- to >
        formatted_yaml = format_yaml_string(yaml_string)

        # Write back to the file using the absolute path
        with open(suppressions_file, 'w') as file:
            file.write(formatted_yaml)

        QMessageBox.information(self, "Success", f"Suppression added successfully for client '{client_name}'!")

    def simple_tune(self):
        client_name = self.client_selector.currentText()
        if not client_name:
            QMessageBox.warning(self, "Selection Required", "Please select a client.")
            return
        
        alert_ids = [self.alert_list.item(i).text() for i in range(self.alert_list.count())]
        if not alert_ids:
            QMessageBox.warning(self, "No Alerts", "No alerts available to tune.")
            return

        simple_tune_dialog = SimpleTuneDialog(alert_ids)
        if simple_tune_dialog.exec() == QDialog.Accepted:
            alert_id, field, value = simple_tune_dialog.get_inputs()

            if not alert_id or not field or not value:
                QMessageBox.warning(self, "Input Required", "All fields are required.")
                return

            # Calculate Unix time for one week from now
            one_week_from_now = datetime.now() + timedelta(weeks=1)
            unix_time = int(one_week_from_now.timestamp())

            # Create SPL query for simple tune suppression with dynamic Unix time
            spl = f"`notable_index` source={alert_id.replace(' ', '_').lower()} {field}=\"{value}\" _time > {unix_time}".strip()

            # Generate Suppression ID and owner
            suppression_id = f"simple_tune_{alert_id.replace(' ', '_').lower()}_{field}_{value}"
            current_user = subprocess.check_output('whoami', shell=True).decode().strip()

            # Create the suppression data structure
            new_suppression = CommentedMap({
                'id': suppression_id,
                'properties': CommentedMap({
                    PlainScalarString('# Creator of suppression'): current_user,
                    'owner': 'nobody',
                    'search': FoldedScalarString(spl.strip())
                })
            })

            self.update_suppressions_file(client_name, new_suppression)

            QMessageBox.information(self, "Success", f"Simple tune suppression added for '{alert_id}' on field '{field}'!")

    def update_suppressions_file(self, client_name, new_suppression):
        suppressions_file = os.path.join('client', client_name, 'suppressions.yml')
        
        yaml = YAML()
        yaml.preserve_quotes = True  
        
        # Load existing suppressions or initialize new structure
        if os.path.exists(suppressions_file):
            with open(suppressions_file, 'r') as file:
                data = yaml.load(file) or {'suppression': {'include': []}}
        else:
            data = {'suppression': {'include': []}}

        # Add the new suppression to the list
        data['suppression']['include'].append(new_suppression)

        # Serialize the YAML to a string
        yaml_string = yaml.dump(data)

        # Format the YAML string to remove single quotes and change >- to >
        formatted_yaml = format_yaml_string(yaml_string)

        # Write back to the file
        with open(suppressions_file, 'w') as file:
            file.write(formatted_yaml)

        QMessageBox.information(self, "Success", f"Suppression added successfully for client '{client_name}'!")

    def simple_tune(self):
        client_name = self.client_selector.currentText()
        if not client_name:
            QMessageBox.warning(self, "Selection Required", "Please select a client.")
            return
        
        alert_ids = [self.alert_list.item(i).text() for i in range(self.alert_list.count())]
        if not alert_ids:
            QMessageBox.warning(self, "No Alerts", "No alerts available to tune.")
            return

        simple_tune_dialog = SimpleTuneDialog(alert_ids)
        if simple_tune_dialog.exec() == QDialog.Accepted:
            alert_id, field, value = simple_tune_dialog.get_inputs()

            if not alert_id or not field or not value:
                QMessageBox.warning(self, "Input Required", "All fields are required.")
                return

            # Calculate Unix time for one week from now
            one_week_from_now = datetime.now() + timedelta(weeks=1)
            unix_time = int(one_week_from_now.timestamp())

            # Create SPL query for simple tune suppression with dynamic Unix time
            spl = f'`notable_index` source={alert_id} {field}="{value}" _time > {unix_time}'.strip()

            # Generate Suppression ID and owner
            suppression_id = f"simple_tune_{alert_id.replace(' ', '_').lower()}_{field}_{value}"
            current_user = subprocess.check_output('whoami', shell=True).decode().strip()

            # Create the suppression data structure
            new_suppression = CommentedMap({
                'id': suppression_id,
                'properties': CommentedMap({
                    PlainScalarString('# Creator of suppression'): current_user,
                    'owner': 'nobody',
                    'search': FoldedScalarString(spl.strip())  # Strip any trailing spaces or newlines
                })
            })

            self.update_suppressions_file(client_name, new_suppression)

            QMessageBox.information(self, "Success", f"Simple tune suppression added for '{alert_id}' on field '{field}'!")

    def update_suppressions_file(self, client_name, new_suppression):
        client_base_path = '/Users/luke/Documents/dev_link/detection_engineering/content-mock/client/'
        client_dir = os.path.join(client_base_path, client_name)
        suppressions_file = os.path.join(client_dir, 'suppressions.yml')
        
        yaml = YAML()
        yaml.preserve_quotes = True  

        # Ensure the client directory exists; if not, create it
        if not os.path.exists(client_dir):
            os.makedirs(client_dir)

        # Load existing suppressions or initialize new structure
        if os.path.exists(suppressions_file):
            with open(suppressions_file, 'r') as file:
                data = yaml.load(file) or {'suppression': {'include': []}}
        else:
            data = {'suppression': {'include': []}}

        # Add the new suppression to the list
        data['suppression']['include'].append(new_suppression)

        # Serialize the YAML to a string
        yaml_string = yaml.dump(data)

        # Format the YAML string to remove single quotes and change >- to >
        formatted_yaml = format_yaml_string(yaml_string)

        # Write back to the file using the absolute path
        with open(suppressions_file, 'w') as file:
            file.write(formatted_yaml)

        QMessageBox.information(self, "Success", f"Suppression added successfully for client '{client_name}'!")

    def handle_existing_branch(self):
        client_name = self.client_selector.currentText()
        alert_name = self.alert_list.currentItem().text() if self.alert_list.currentItem() else None
        
        if not client_name or not alert_name:
            QMessageBox.warning(self, "Selection Required", "Please select a client and an alert.")
            return

        branch_dialog = BranchNameDialog()
        if branch_dialog.exec() == QDialog.Accepted:
            branch_name = branch_dialog.get_branch_name()
            if not branch_name:
                QMessageBox.warning(self, "Input Required", "Branch name is required.")
                return

            form_dialog = SuppressionFormDialog()
            if form_dialog.exec() == QDialog.Accepted:
                nms_ticket, reason, spl = form_dialog.get_inputs()

                if not nms_ticket or not reason or not spl:
                    QMessageBox.warning(self, "Input Required", "All fields are required.")
                    return

                suppression_id = f"{nms_ticket}_{client_name}_{alert_name.replace(' ', '_').lower()}"
                current_user = subprocess.check_output('whoami', shell=True).decode().strip()

                new_suppression = CommentedMap({
                    'id': suppression_id,
                    'properties': CommentedMap({
                        PlainScalarString('# Creator of suppression'): PlainScalarString(current_user),
                        'owner': 'nobody',
                        'search': FoldedScalarString(spl)
                    })
                })

                self.update_suppressions_file(client_name, new_suppression)

                if handle_existing_branch_operations(branch_name, client_name, nms_ticket, reason):
                    QMessageBox.information(self, "Success", f"Suppression modified and changes pushed to branch '{branch_name}'!")

# Remaining App Code and Initialization

def read_alerts_file(client_dir):
    alerts_file = os.path.join(client_dir, 'alerts.yml')
    if not os.path.exists(alerts_file):
        return []
    try:
        with open(alerts_file, 'r') as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError:
        return []

    alerts = data.get('alert', {}).get('include', [])
    return [alert['id'].replace('_', ' ').title() for alert in alerts if alert.get('remove_shadow', False)]


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()