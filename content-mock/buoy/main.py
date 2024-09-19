import os
import yaml
import subprocess
import configparser
import logging
from datetime import datetime, timedelta
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import FoldedScalarString, PlainScalarString
from ruamel.yaml.comments import CommentedMap
import re
from io import StringIO
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

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
        messagebox.showerror("Git Error", f"Command '{command}' failed:\n{e.stderr.decode().strip()}")
        return None

def format_yaml_string(yaml_string):
    """Formats the YAML string to correct style issues."""
    yaml_string = re.sub(r"'# Creator of suppression':", "# Creator of suppression:", yaml_string)
    yaml_string = yaml_string.replace(">-\n", ">\n")
    return yaml_string

def show_suppression_preview(suppression_yaml):
    """Displays a dialog to preview the suppression YAML."""
    dialog = tk.Toplevel()
    dialog.title("Preview Suppression")
    dialog.geometry("600x400")

    text_edit = tk.Text(dialog)
    text_edit.insert("1.0", suppression_yaml)
    text_edit.config(state=tk.DISABLED)
    text_edit.pack(fill=tk.BOTH, expand=True)

    def on_ok():
        dialog.destroy()
        dialog.result = True

    def on_cancel():
        dialog.destroy()
        dialog.result = False

    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=5)

    ok_button = tk.Button(button_frame, text="OK", command=on_ok)
    cancel_button = tk.Button(button_frame, text="Cancel", command=on_cancel)
    ok_button.pack(side=tk.LEFT, padx=5)
    cancel_button.pack(side=tk.RIGHT, padx=5)

    dialog.transient()
    dialog.grab_set()
    dialog.wait_window()
    return getattr(dialog, 'result', False)

class MainWindow(tk.Tk):
    """Main window of the application with navigation."""
    def __init__(self):
        super().__init__()
        self.title("Buoy - Detection Tuning Tool")
        self.selected_client = None
        self.selected_action = None
        self.selected_alert = None
        self.scratch_pad_content = ""
        self.setup_ui()
        self.populate_clients()

    def setup_ui(self):
        # Create frames for each page
        self.pages = {}
        self.current_page = None

        self.page1 = tk.Frame(self)
        self.page2 = tk.Frame(self)
        self.page3 = tk.Frame(self)
        self.page4 = tk.Frame(self)

        self.pages[1] = self.page1
        self.pages[2] = self.page2
        self.pages[3] = self.page3
        self.pages[4] = self.page4

        self.setup_page1()
        self.setup_page2()
        self.setup_page3()
        self.setup_page4()

        self.go_to_page(1)

        # Menu bar for settings
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        settings_menu.add_command(label="Export Suppressions", command=self.export_suppressions)

    def setup_page1(self):
        """Setup for Page 1: Client Selection."""
        frame = self.page1
        label = tk.Label(frame, text="Select Client:")
        label.pack(pady=10)

        self.client_selector = ttk.Combobox(frame)
        self.client_selector.pack(pady=5)

        # Navigation buttons
        nav_frame = tk.Frame(frame)
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        next_button = tk.Button(nav_frame, text="Next", command=self.go_to_page2)
        next_button.pack(side=tk.RIGHT, padx=5)

    def setup_page2(self):
        """Setup for Page 2: Action Selection."""
        frame = self.page2
        label = tk.Label(frame, text="Choose Action:")
        label.pack(pady=10)

        self.add_suppression_button = tk.Button(frame, text="Add Suppression", command=self.select_add_suppression)
        self.add_suppression_button.pack(pady=5)

        self.simple_tune_button = tk.Button(frame, text="Simple Tune", command=self.select_simple_tune)
        self.simple_tune_button.pack(pady=5)

        # Navigation buttons
        nav_frame = tk.Frame(frame)
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        back_button = tk.Button(nav_frame, text="Back", command=self.go_to_page1)
        back_button.pack(side=tk.LEFT, padx=5)

    def setup_page3(self):
        """Setup for Page 3: Alert Selection and Action Input."""
        frame = self.page3
        label = tk.Label(frame, text="Select Alert:")
        label.pack(pady=10)

        self.alert_list = tk.Listbox(frame, height=10)
        self.alert_list.pack(pady=5, fill=tk.BOTH, expand=True)

        # For Add Suppression action
        self.spl_input = tk.Text(frame, height=5)
        self.spl_input.pack(pady=5)
        self.spl_input.pack_forget()  # Hide initially

        # For Simple Tune action
        self.field_selector_label = tk.Label(frame, text="Select Field:")
        self.field_selector = ttk.Combobox(frame, values=["dest", "host", "user"])
        self.value_input = tk.Entry(frame)
        self.field_selector_label.pack()
        self.field_selector.pack(pady=5)
        self.value_input.pack(pady=5)
        self.field_selector_label.pack_forget()
        self.field_selector.pack_forget()
        self.value_input.pack_forget()

        # Navigation buttons
        nav_frame = tk.Frame(frame)
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        back_button = tk.Button(nav_frame, text="Back", command=self.go_to_page2)
        back_button.pack(side=tk.LEFT, padx=5)

        next_button = tk.Button(nav_frame, text="Next", command=self.go_to_page4)
        next_button.pack(side=tk.RIGHT, padx=5)

    def setup_page4(self):
        """Setup for Page 4: Scratch Pad and Confirmation."""
        frame = self.page4
        label = tk.Label(frame, text="Scratch Pad:")
        label.pack(pady=10)

        self.scratch_pad = tk.Text(frame, height=15)
        self.scratch_pad.pack(pady=5, fill=tk.BOTH, expand=True)

        # Navigation buttons
        nav_frame = tk.Frame(frame)
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        back_button = tk.Button(nav_frame, text="Back", command=self.go_to_page3)
        back_button.pack(side=tk.LEFT, padx=5)

        finish_button = tk.Button(nav_frame, text="Finish", command=self.finish_process)
        finish_button.pack(side=tk.RIGHT, padx=5)

    def go_to_page(self, page_number):
        if self.current_page:
            self.current_page.pack_forget()
        self.current_page = self.pages[page_number]
        self.current_page.pack(fill=tk.BOTH, expand=True)

    def go_to_page1(self):
        self.go_to_page(1)

    def go_to_page2(self):
        self.selected_client = self.client_selector.get()
        if not self.selected_client:
            messagebox.showwarning("Selection Required", "Please select a client.")
            return
        self.go_to_page(2)

    def go_to_page3(self):
        # Load alerts for the selected client
        client_dir = os.path.join(CLIENT_BASE_PATH, self.selected_client)
        if not os.path.exists(client_dir):
            messagebox.showerror("Error", f"Client '{self.selected_client}' does not exist.")
            return

        ids = self.read_alerts_file(client_dir)
        if not ids:
            messagebox.showwarning("No Alerts", f"No valid alerts found for client '{self.selected_client}'.")
            return

        self.alert_list.delete(0, tk.END)
        for alert_id in ids:
            self.alert_list.insert(tk.END, alert_id)

        # Show/hide input fields based on action
        if self.selected_action == "Add Suppression":
            self.spl_input.pack()
            self.field_selector_label.pack_forget()
            self.field_selector.pack_forget()
            self.value_input.pack_forget()
        elif self.selected_action == "Simple Tune":
            self.spl_input.pack_forget()
            self.field_selector_label.pack()
            self.field_selector.pack()
            self.value_input.pack()

        self.go_to_page(3)

    def go_to_page4(self):
        selection = self.alert_list.curselection()
        if selection:
            self.selected_alert = self.alert_list.get(selection[0])
        else:
            self.selected_alert = None

        if not self.selected_alert:
            messagebox.showwarning("Selection Required", "Please select an alert.")
            return

        if self.selected_action == "Add Suppression":
            spl = self.spl_input.get("1.0", tk.END).strip()
            if not spl:
                messagebox.showwarning("Input Required", "Please enter an SPL query.")
                return
            self.scratch_pad.delete("1.0", tk.END)
            self.scratch_pad.insert("1.0", spl)
        elif self.selected_action == "Simple Tune":
            field = self.field_selector.get()
            value = self.value_input.get().strip()
            if not value:
                messagebox.showwarning("Input Required", "Please enter a value.")
                return
            # Generate SPL for simple tune
            alert_id_snake_case = self.to_snake_case(self.selected_alert)
            unix_time = int((datetime.now() + timedelta(weeks=1)).timestamp())
            spl = f'`notable_index` source={alert_id_snake_case} {field}="{value}" _time > {unix_time}'
            self.scratch_pad.delete("1.0", tk.END)
            self.scratch_pad.insert("1.0", spl)

        self.go_to_page(4)

    def finish_process(self):
        # Use the content from scratch pad as the SPL
        spl = self.scratch_pad.get("1.0", tk.END).strip()
        if not spl:
            messagebox.showwarning("Input Required", "Scratch pad cannot be empty.")
            return

        if self.selected_action == "Add Suppression":
            nms_ticket = simpledialog.askstring("NMS Ticket Number", "Enter NMS Ticket Number:")
            if not nms_ticket:
                messagebox.showwarning("Input Required", "NMS Ticket Number is required.")
                return
            reason = simpledialog.askstring("Reason", "Enter Reason:")
            if not reason:
                messagebox.showwarning("Input Required", "Reason is required.")
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
                        messagebox.showinfo("Success", f"Suppression added and pushed to branch '{branch_name}'!")
        elif self.selected_action == "Simple Tune":
            # For simple tune, proceed with existing process
            suppression_id = f"simple_tune_{self.to_snake_case(self.selected_alert)}_{self.field_selector.get()}_{self.value_input.get().strip()}"

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
                    messagebox.showinfo("Success", f"Simple tune suppression added for '{self.selected_alert}'!")

        # Reset the application
        self.reset_app()

    def reset_app(self):
        """Reset the application to initial state."""
        self.selected_client = None
        self.selected_action = None
        self.selected_alert = None
        self.scratch_pad.delete("1.0", tk.END)
        self.spl_input.delete("1.0", tk.END)
        self.field_selector.set("")
        self.value_input.delete(0, tk.END)
        self.go_to_page1()

    def select_add_suppression(self):
        self.selected_action = "Add Suppression"
        self.go_to_page3()

    def select_simple_tune(self):
        self.selected_action = "Simple Tune"
        self.go_to_page3()

    def git_operations(self, client_name, nms_number, reason, branch_name):
        progress = tk.Toplevel(self)
        progress.title("Performing Git operations...")
        label = tk.Label(progress, text="Please wait...")
        label.pack(pady=10)
        self.update()

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
            progress.destroy()

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
        client_name = self.client_selector.get()
        if not client_name:
            messagebox.showwarning("Selection Required", "Please select a client to export suppressions.")
            return

        client_dir = os.path.join(CLIENT_BASE_PATH, client_name)
        suppressions_file = os.path.join(client_dir, 'suppressions.yml')
        if not os.path.exists(suppressions_file):
            messagebox.showwarning("No Suppressions", f"No suppressions found for client '{client_name}'.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save Suppressions As",
            defaultextension=".yml",
            initialfile=f"{client_name}_suppressions.yml",
            filetypes=[("YAML Files", "*.yml *.yaml")])
        if save_path:
            try:
                with open(suppressions_file, 'r') as src, open(save_path, 'w') as dst:
                    dst.write(src.read())
                messagebox.showinfo("Export Successful", f"Suppressions exported to '{save_path}'.")
            except Exception as e:
                logging.error(f"Error exporting suppressions: {e}")
                messagebox.showerror("Export Failed", "An error occurred while exporting suppressions.")

    def populate_clients(self):
        if not os.path.exists(CLIENT_BASE_PATH):
            messagebox.showerror("Error", f"Client base path '{CLIENT_BASE_PATH}' does not exist.")
            return
        client_dirs = [
            d for d in os.listdir(CLIENT_BASE_PATH)
            if os.path.isdir(os.path.join(CLIENT_BASE_PATH, d))
        ]
        self.client_selector['values'] = client_dirs

def main():
    app = MainWindow()
    app.geometry("600x500")
    app.mainloop()

if __name__ == '__main__':
    main()
