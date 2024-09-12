#!/usr/bin/env python3
import os
import yaml
import subprocess
import configparser
import logging
from datetime import datetime, timedelta
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import FoldedScalarString, PlainScalarString
from ruamel.yaml.comments import CommentedMap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QComboBox, QListWidget, QVBoxLayout, QWidget,
    QMessageBox, QPushButton, QFormLayout, QLineEdit, QDialog,
    QDialogButtonBox, QTextEdit, QLabel, QProgressDialog, QAction, QFileDialog
)
from PySide6.QtCore import Qt
import re
from io import StringIO

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

CLIENT_BASE_PATH = config.get('Paths', 'ClientBasePath', fallback='./clients/')
GIT_REPO_PATH = config.get('Paths', 'GitRepoPath', fallback='.')
CURRENT_USER = subprocess.getoutput('whoami')

# Initialize YAML object
yaml_ruamel = YAML()
yaml_ruamel.preserve_quotes = True  # Ensure quotes are preserved

def run_git_command(command, cwd=None):
    """Runs a git command in the specified directory."""
    if cwd is None:
        cwd = GIT_REPO_PATH
    logging.info(f"Running git command: {command}")
    try:
        result = subprocess.run(
            command, cwd=cwd, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.stdout.decode().strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Git command failed: {e.stderr.decode().strip()}")
        QMessageBox.critical(
            None, "Git Error",
            f"Command '{command}' failed:\n{e.stderr.decode().strip()}"
        )
        return None

def format_yaml_string(yaml_string):
    """Formats the YAML string to correct style issues."""
    yaml_string = re.sub(r"'# Creator of suppression':", "# Creator of suppression:", yaml_string)
    yaml_string = yaml_string.replace(">-\n", ">\n")
    return yaml_string

def show_suppression_preview(suppression_yaml):
    """Displays a dialog to preview the suppression YAML."""
    dialog = QDialog()
    dialog.setWindowTitle("Preview Suppression")
    layout = QVBoxLayout(dialog)

    text_edit = QTextEdit(dialog)
    text_edit.setText(suppression_yaml)
    text_edit.setReadOnly(True)
    layout.addWidget(text_edit)

    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    dialog.setLayout(layout)
    return dialog.exec() == QDialog.Accepted

class SuppressionFormDialog(QDialog):
    """Dialog to collect suppression details from the user."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Suppression")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.ticket_input = QLineEdit(self)
        self.reason_input = QLineEdit(self)
        self.spl_input = QTextEdit(self)

        layout.addRow("NMS Ticket Number:", self.ticket_input)
        layout.addRow("Reason:", self.reason_input)
        layout.addRow("SPL Query:", self.spl_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.validate_inputs)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def validate_inputs(self):
        if not self.ticket_input.text().strip() or not self.reason_input.text().strip() or not self.spl_input.toPlainText().strip():
            QMessageBox.warning(self, "Input Required", "All fields are required.")
            return
        self.accept()

    def get_inputs(self):
        return (
            self.ticket_input.text().strip(),
            self.reason_input.text().strip(),
            self.spl_input.toPlainText().strip()
        )

class SimpleTuneDialog(QDialog):
    """Dialog to collect simple tune details from the user."""
    def __init__(self, alert_ids, parent=None):
        super().__init__(parent)
        self.alert_ids = alert_ids
        self.setWindowTitle("Simple Tune Suppression")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.alert_id_selector = QComboBox(self)
        self.alert_id_selector.addItems(self.alert_ids)

        self.field_selector = QComboBox(self)
        self.field_selector.addItems(["dest", "host", "user"])

        self.value_input = QLineEdit(self)

        layout.addRow("Select Alert ID:", self.alert_id_selector)
        layout.addRow("Select Field:", self.field_selector)
        layout.addRow("Enter Value:", self.value_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.validate_inputs)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def validate_inputs(self):
        if not self.value_input.text().strip():
            QMessageBox.warning(self, "Input Required", "Value field cannot be empty.")
            return
        self.accept()

    def get_inputs(self):
        return (
            self.alert_id_selector.currentText(),
            self.field_selector.currentText(),
            self.value_input.text().strip()
        )

class MainWindow(QMainWindow):
    """Main window of the application."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Client Alerts Viewer")
        self.setup_ui()
        self.populate_clients()

    def setup_ui(self):
        self.layout = QVBoxLayout()

        self.client_selector = QComboBox(self)
        self.client_selector.setEditable(True)
        self.client_selector.currentTextChanged.connect(self.on_client_selected)
        self.layout.addWidget(QLabel("Select Client:", self))
        self.layout.addWidget(self.client_selector)

        self.alert_list = QListWidget(self)
        self.layout.addWidget(QLabel("Alerts:", self))
        self.layout.addWidget(self.alert_list)

        self.clear_button = QPushButton("Clear Selection", self)
        self.clear_button.clicked.connect(self.clear_selection)
        self.layout.addWidget(self.clear_button)

        self.add_suppression_button = QPushButton("Add Suppression", self)
        self.add_suppression_button.clicked.connect(self.add_suppression)
        self.add_suppression_button.setEnabled(False)
        self.layout.addWidget(self.add_suppression_button)

        self.simple_tune_button = QPushButton("Simple Tune", self)
        self.simple_tune_button.clicked.connect(self.simple_tune)
        self.simple_tune_button.setEnabled(False)
        self.layout.addWidget(self.simple_tune_button)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        # Menu bar for settings
        menubar = self.menuBar()
        settings_menu = menubar.addMenu('Settings')

        export_action = QAction('Export Suppressions', self)
        export_action.triggered.connect(self.export_suppressions)
        settings_menu.addAction(export_action)

    def clear_selection(self):
        self.client_selector.setCurrentIndex(-1)
        self.alert_list.clear()
        self.add_suppression_button.setEnabled(False)
        self.simple_tune_button.setEnabled(False)

    def populate_clients(self):
        if not os.path.exists(CLIENT_BASE_PATH):
            QMessageBox.critical(self, "Error", f"Client base path '{CLIENT_BASE_PATH}' does not exist.")
            return
        client_dirs = [
            d for d in os.listdir(CLIENT_BASE_PATH)
            if os.path.isdir(os.path.join(CLIENT_BASE_PATH, d))
        ]
        self.client_selector.clear()
        self.client_selector.addItems(client_dirs)

    def on_client_selected(self, client_name):
        self.alert_list.clear()
        self.add_suppression_button.setEnabled(False)
        self.simple_tune_button.setEnabled(False)
        if not client_name:
            return

        client_dir = os.path.join(CLIENT_BASE_PATH, client_name)
        if not os.path.exists(client_dir):
            QMessageBox.critical(self, "Error", f"Client '{client_name}' does not exist.")
            return

        ids = self.read_alerts_file(client_dir)
        if not ids:
            QMessageBox.warning(self, "No Alerts", f"No valid alerts found for client '{client_name}'.")
        else:
            self.alert_list.addItems(ids)
            self.add_suppression_button.setEnabled(True)
            self.simple_tune_button.setEnabled(True)

    def add_suppression(self):
        client_name = self.client_selector.currentText()
        alert_item = self.alert_list.currentItem()
        alert_name = alert_item.text() if alert_item else None

        if not client_name or not alert_name:
            QMessageBox.warning(self, "Selection Required", "Please select a client and an alert.")
            return

        form_dialog = SuppressionFormDialog(self)
        if form_dialog.exec() == QDialog.Accepted:
            nms_ticket, reason, spl = form_dialog.get_inputs()
            suppression_id = f"{nms_ticket}_{client_name}_{alert_name.replace(' ', '_').lower()}"

            new_suppression = CommentedMap({
                'id': suppression_id,
                'properties': CommentedMap({
                    PlainScalarString('# Creator of suppression'): CURRENT_USER,
                    'owner': 'nobody',
                    'search': FoldedScalarString(spl)
                })
            })

            # Use StringIO to capture the YAML output
            stream = StringIO()
            yaml_ruamel.dump(new_suppression, stream)
            formatted_yaml = format_yaml_string(stream.getvalue())

            # Preview suppression YAML
            if show_suppression_preview(formatted_yaml):
                # Proceed with adding suppression to file
                if self.update_suppressions_file(client_name, new_suppression):
                    # Git operations and push changes
                    branch_name = f"suppression_{nms_ticket}"
                    if self.git_operations(client_name, nms_ticket, reason, branch_name):
                        QMessageBox.information(
                            self, "Success",
                            f"Suppression added and pushed to branch '{branch_name}'!"
                        )
            else:
                QMessageBox.information(self, "Cancelled", "Suppression creation cancelled.")

    def simple_tune(self):
        client_name = self.client_selector.currentText()
        if not client_name:
            QMessageBox.warning(self, "Selection Required", "Please select a client.")
            return

        alert_ids = [self.alert_list.item(i).text() for i in range(self.alert_list.count())]
        if not alert_ids:
            QMessageBox.warning(self, "No Alerts", "No alerts available to tune.")
            return

        simple_tune_dialog = SimpleTuneDialog(alert_ids, self)
        if simple_tune_dialog.exec() == QDialog.Accepted:
            alert_id, field, value = simple_tune_dialog.get_inputs()
            alert_id_snake_case = self.to_snake_case(alert_id)
            unix_time = int((datetime.now() + timedelta(weeks=1)).timestamp())
            spl = f'`notable_index` source={alert_id_snake_case} {field}="{value}" _time > {unix_time}'

            suppression_id = f"simple_tune_{alert_id_snake_case}_{field}_{value}"

            new_suppression = CommentedMap({
                'id': suppression_id,
                'properties': CommentedMap({
                    PlainScalarString('# Creator of suppression'): CURRENT_USER,
                    'owner': 'nobody',
                    'search': FoldedScalarString(spl)
                })
            })

            # Use StringIO to capture the YAML output
            stream = StringIO()
            yaml_ruamel.dump(new_suppression, stream)
            formatted_yaml = format_yaml_string(stream.getvalue())

            # Preview suppression YAML
            if show_suppression_preview(formatted_yaml):
                # Proceed with adding suppression to file
                if self.update_suppressions_file(client_name, new_suppression):
                    QMessageBox.information(
                        self, "Success",
                        f"Simple tune suppression added for '{alert_id}' on field '{field}'!"
                    )
            else:
                QMessageBox.information(self, "Cancelled", "Suppression creation cancelled.")

    def git_operations(self, client_name, nms_number, reason, branch_name):
        progress = QProgressDialog("Performing Git operations...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        try:
            if not run_git_command('git checkout main'):
                return False
            if not run_git_command('git pull'):
                return False
            if not run_git_command(f'git checkout -b {branch_name}'):
                return False

            if not run_git_command(f'git add {os.path.join(CLIENT_BASE_PATH, client_name)}'):
                return False

            commit_message = f'{nms_number}: {reason}'
            if not run_git_command(f'git commit -m "{commit_message}"'):
                return False

            if not run_git_command(f'git push -u origin {branch_name}'):
                return False

            return True
        finally:
            progress.close()

    def to_snake_case(self, text):
        return text.lower().replace(' ', '_')

    def update_suppressions_file(self, client_name, new_suppression):
        client_dir = os.path.join(CLIENT_BASE_PATH, client_name)
        suppressions_file = os.path.join(client_dir, 'suppressions.yml')

        # Ensure the client directory exists
        if not os.path.exists(client_dir):
            os.makedirs(client_dir)

        # Load existing suppressions or initialize a new structure
        if os.path.exists(suppressions_file):
            with open(suppressions_file, 'r') as file:
                data = yaml_ruamel.load(file) or {'suppression': {'include': []}}
        else:
            data = {'suppression': {'include': []}}

        # Add the new suppression to the list
        data['suppression']['include'].append(new_suppression)

        # Serialize the YAML to a string using a temporary stream
        stream = StringIO()
        yaml_ruamel.dump(data, stream)
        yaml_string = stream.getvalue()

        # Format the YAML string
        formatted_yaml = format_yaml_string(yaml_string)

        # Write back to the file
        with open(suppressions_file, 'w') as file:
            file.write(formatted_yaml)

        return True

    def read_alerts_file(self, client_dir):
        alerts_file = os.path.join(client_dir, 'alerts.yml')
        if not os.path.exists(alerts_file):
            return []
        try:
            with open(alerts_file, 'r') as file:
                data = yaml.safe_load(file) or {}
        except yaml.YAMLError as e:
            logging.error(f"Error reading alerts file: {e}")
            return []

        alerts = data.get('alert', {}).get('include', [])
        return [
            alert['id'].replace('_', ' ').title()
            for alert in alerts if alert.get('remove_shadow', False)
        ]

    def export_suppressions(self):
        client_name = self.client_selector.currentText()
        if not client_name:
            QMessageBox.warning(self, "Selection Required", "Please select a client to export suppressions.")
            return

        client_dir = os.path.join(CLIENT_BASE_PATH, client_name)
        suppressions_file = os.path.join(client_dir, 'suppressions.yml')
        if not os.path.exists(suppressions_file):
            QMessageBox.warning(self, "No Suppressions", f"No suppressions found for client '{client_name}'.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Suppressions As", f"{client_name}_suppressions.yml", "YAML Files (*.yml *.yaml)")
        if save_path:
            try:
                with open(suppressions_file, 'r') as src, open(save_path, 'w') as dst:
                    dst.write(src.read())
                QMessageBox.information(self, "Export Successful", f"Suppressions exported to '{save_path}'.")
            except Exception as e:
                logging.error(f"Error exporting suppressions: {e}")
                QMessageBox.critical(self, "Export Failed", "An error occurred while exporting suppressions.")

def main():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()

if __name__ == '__main__':
    main()
