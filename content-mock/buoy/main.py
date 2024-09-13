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
    QDialogButtonBox, QTextEdit, QLabel, QProgressDialog, QFileDialog,
    QStackedWidget, QHBoxLayout
)
from PySide6.QtGui import QAction, QFont
from PySide6.QtCore import Qt
import re
from io import StringIO

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

CLIENT_BASE_PATH = config.get('Paths', 'ClientBasePath', fallback='./client/')
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

class MainWindow(QMainWindow):
    """Main window of the application with navigation."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Buoy - Detection Tuning Tool")
        self.selected_client = None
        self.selected_action = None
        self.selected_alert = None
        self.scratch_pad_content = ""
        self.setup_ui()
        self.populate_clients()

    def setup_ui(self):
        # Create a QStackedWidget to hold different pages
        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)

        # Create pages
        self.page1 = QWidget()
        self.page2 = QWidget()
        self.page3 = QWidget()
        self.page4 = QWidget()

        self.setup_page1()
        self.setup_page2()
        self.setup_page3()
        self.setup_page4()

        # Add pages to stacked widget
        self.stacked_widget.addWidget(self.page1)
        self.stacked_widget.addWidget(self.page2)
        self.stacked_widget.addWidget(self.page3)
        self.stacked_widget.addWidget(self.page4)

        # Menu bar for settings
        menubar = self.menuBar()
        settings_menu = menubar.addMenu('Settings')

        export_action = QAction('Export Suppressions', self)
        export_action.triggered.connect(self.export_suppressions)
        settings_menu.addAction(export_action)

    def setup_page1(self):
        """Setup for Page 1: Client Selection."""
        layout = QVBoxLayout()

        label = QLabel("Select Client:", self)
        layout.addWidget(label)

        self.client_selector = QComboBox(self)
        self.client_selector.setEditable(True)
        layout.addWidget(self.client_selector)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        next_button = QPushButton("Next", self)
        next_button.clicked.connect(self.go_to_page2)
        nav_layout.addStretch()
        nav_layout.addWidget(next_button)
        layout.addLayout(nav_layout)

        self.page1.setLayout(layout)

    def setup_page2(self):
        """Setup for Page 2: Action Selection."""
        layout = QVBoxLayout()

        label = QLabel("Choose Action:", self)
        layout.addWidget(label)

        self.add_suppression_button = QPushButton("Add Suppression", self)
        self.add_suppression_button.clicked.connect(self.select_add_suppression)
        layout.addWidget(self.add_suppression_button)

        self.simple_tune_button = QPushButton("Simple Tune", self)
        self.simple_tune_button.clicked.connect(self.select_simple_tune)
        layout.addWidget(self.simple_tune_button)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        back_button = QPushButton("Back", self)
        back_button.clicked.connect(self.go_to_page1)
        nav_layout.addWidget(back_button)
        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        self.page2.setLayout(layout)

    def setup_page3(self):
        """Setup for Page 3: Alert Selection and Action Input."""
        layout = QVBoxLayout()

        self.alert_list = QListWidget(self)
        layout.addWidget(QLabel("Select Alert:", self))
        layout.addWidget(self.alert_list)

        # For Add Suppression action
        self.spl_input = QTextEdit(self)
        self.spl_input.setPlaceholderText("Enter SPL Query here...")
        self.spl_input.hide()
        layout.addWidget(self.spl_input)

        # For Simple Tune action
        self.field_selector = QComboBox(self)
        self.field_selector.addItems(["dest", "host", "user"])
        self.field_selector.hide()
        layout.addWidget(QLabel("Select Field:", self))
        layout.addWidget(self.field_selector)

        self.value_input = QLineEdit(self)
        self.value_input.setPlaceholderText("Enter Value")
        self.value_input.hide()
        layout.addWidget(self.value_input)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        back_button = QPushButton("Back", self)
        back_button.clicked.connect(self.go_to_page2)
        nav_layout.addWidget(back_button)

        next_button = QPushButton("Next", self)
        next_button.clicked.connect(self.go_to_page4)
        nav_layout.addStretch()
        nav_layout.addWidget(next_button)
        layout.addLayout(nav_layout)

        self.page3.setLayout(layout)

    def setup_page4(self):
        """Setup for Page 4: Scratch Pad and Confirmation."""
        layout = QVBoxLayout()

        self.scratch_pad = QTextEdit(self)
        self.scratch_pad.setPlaceholderText("Scratch Pad...")
        monospace_font = QFont("Courier New")
        self.scratch_pad.setFont(monospace_font)
        layout.addWidget(QLabel("Scratch Pad:", self))
        layout.addWidget(self.scratch_pad)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        back_button = QPushButton("Back", self)
        back_button.clicked.connect(self.go_to_page3)
        nav_layout.addWidget(back_button)

        finish_button = QPushButton("Finish", self)
        finish_button.clicked.connect(self.finish_process)
        nav_layout.addStretch()
        nav_layout.addWidget(finish_button)
        layout.addLayout(nav_layout)

        self.page4.setLayout(layout)

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

    def go_to_page1(self):
        self.stacked_widget.setCurrentWidget(self.page1)

    def go_to_page2(self):
        self.selected_client = self.client_selector.currentText()
        if not self.selected_client:
            QMessageBox.warning(self, "Selection Required", "Please select a client.")
            return
        self.stacked_widget.setCurrentWidget(self.page2)

    def go_to_page3(self):
        # Load alerts for the selected client
        client_dir = os.path.join(CLIENT_BASE_PATH, self.selected_client)
        if not os.path.exists(client_dir):
            QMessageBox.critical(self, "Error", f"Client '{self.selected_client}' does not exist.")
            return

        ids = self.read_alerts_file(client_dir)
        if not ids:
            QMessageBox.warning(self, "No Alerts", f"No valid alerts found for client '{self.selected_client}'.")
            return

        self.alert_list.clear()
        self.alert_list.addItems(ids)

        # Show/hide input fields based on action
        if self.selected_action == "Add Suppression":
            self.spl_input.show()
            self.field_selector.hide()
            self.value_input.hide()
        elif self.selected_action == "Simple Tune":
            self.spl_input.hide()
            self.field_selector.show()
            self.value_input.show()

        self.stacked_widget.setCurrentWidget(self.page3)

    def go_to_page4(self):
        alert_item = self.alert_list.currentItem()
        self.selected_alert = alert_item.text() if alert_item else None

        if not self.selected_alert:
            QMessageBox.warning(self, "Selection Required", "Please select an alert.")
            return

        if self.selected_action == "Add Suppression":
            spl = self.spl_input.toPlainText().strip()
            if not spl:
                QMessageBox.warning(self, "Input Required", "Please enter an SPL query.")
                return
            self.scratch_pad.setPlainText(spl)
        elif self.selected_action == "Simple Tune":
            field = self.field_selector.currentText()
            value = self.value_input.text().strip()
            if not value:
                QMessageBox.warning(self, "Input Required", "Please enter a value.")
                return
            # Generate SPL for simple tune
            alert_id_snake_case = self.to_snake_case(self.selected_alert)
            unix_time = int((datetime.now() + timedelta(weeks=1)).timestamp())
            spl = f'`notable_index` source={alert_id_snake_case} {field}="{value}" _time > {unix_time}'
            self.scratch_pad.setPlainText(spl)

        self.stacked_widget.setCurrentWidget(self.page4)

    def finish_process(self):
        # Use the content from scratch pad as the SPL
        spl = self.scratch_pad.toPlainText().strip()
        if not spl:
            QMessageBox.warning(self, "Input Required", "Scratch pad cannot be empty.")
            return

        if self.selected_action == "Add Suppression":
            nms_ticket, ok = QInputDialog.getText(self, "NMS Ticket Number", "Enter NMS Ticket Number:")
            if not ok or not nms_ticket.strip():
                QMessageBox.warning(self, "Input Required", "NMS Ticket Number is required.")
                return
            reason, ok = QInputDialog.getText(self, "Reason", "Enter Reason:")
            if not ok or not reason.strip():
                QMessageBox.warning(self, "Input Required", "Reason is required.")
                return

            suppression_id = f"{nms_ticket}_{self.selected_client}_{self.selected_alert.replace(' ', '_').lower()}"

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
                if self.update_suppressions_file(self.selected_client, new_suppression):
                    # Git operations and push changes
                    branch_name = f"suppression_{nms_ticket}"
                    if self.git_operations(self.selected_client, nms_ticket, reason, branch_name):
                        QMessageBox.information(
                            self, "Success",
                            f"Suppression added and pushed to branch '{branch_name}'!"
                        )
        elif self.selected_action == "Simple Tune":
            # For simple tune, proceed with existing process
            suppression_id = f"simple_tune_{self.to_snake_case(self.selected_alert)}_{self.field_selector.currentText()}_{self.value_input.text().strip()}"

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
                if self.update_suppressions_file(self.selected_client, new_suppression):
                    QMessageBox.information(
                        self, "Success",
                        f"Simple tune suppression added for '{self.selected_alert}'!"
                    )

        # Reset the application
        self.reset_app()

    def reset_app(self):
        """Reset the application to initial state."""
        self.selected_client = None
        self.selected_action = None
        self.selected_alert = None
        self.scratch_pad.clear()
        self.spl_input.clear()
        self.field_selector.setCurrentIndex(0)
        self.value_input.clear()
        self.go_to_page1()

    def select_add_suppression(self):
        self.selected_action = "Add Suppression"
        self.go_to_page3()

    def select_simple_tune(self):
        self.selected_action = "Simple Tune"
        self.go_to_page3()

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