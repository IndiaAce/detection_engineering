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
from flask import Flask, render_template_string, request, redirect, url_for, flash, Response

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Set CLIENT_BASE_PATH to the specified directory
CLIENT_BASE_PATH = config.get('Paths', 'ClientBasePath', fallback='/workspaces/content-live/client/')
CURRENT_USER = subprocess.getoutput('whoami')

# Initialize YAML object
yaml_ruamel = YAML()
yaml_ruamel.preserve_quotes = True  # Ensure quotes are preserved

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your own secret key for session management

def format_yaml_string(yaml_string):
    """Formats the YAML string to correct style issues."""
    yaml_string = re.sub(r"'# Creator of suppression':", "# Creator of suppression:", yaml_string)
    yaml_string = yaml_string.replace(">-\n", ">\n")
    return yaml_string

def to_snake_case(text):
    return text.lower().replace(' ', '_')

def update_suppressions_file(client_name, new_suppression):
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

def read_alerts_file(client_dir):
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

@app.route('/', methods=['GET', 'POST'])
def select_client():
    if request.method == 'POST':
        client = request.form.get('client')
        if not client:
            flash('Please select a client.', 'warning')
            return redirect(url_for('select_client'))
        return redirect(url_for('select_action', client=client))
    else:
        if not os.path.exists(CLIENT_BASE_PATH):
            flash(f"Client base path '{CLIENT_BASE_PATH}' does not exist.", 'error')
            clients = []
        else:
            clients = [
                d for d in os.listdir(CLIENT_BASE_PATH)
                if os.path.isdir(os.path.join(CLIENT_BASE_PATH, d))
            ]
        return render_template_string(TEMPLATE_SELECT_CLIENT, clients=clients)

@app.route('/action/<client>', methods=['GET', 'POST'])
def select_action(client):
    if request.method == 'POST':
        action = request.form.get('action')
        if not action:
            flash('Please select an action.', 'warning')
            return redirect(url_for('select_action', client=client))
        return redirect(url_for('alert_selection', client=client, action=action))
    else:
        return render_template_string(TEMPLATE_SELECT_ACTION, client=client)

@app.route('/alerts/<client>/<action>', methods=['GET', 'POST'])
def alert_selection(client, action):
    client_dir = os.path.join(CLIENT_BASE_PATH, client)
    if not os.path.exists(client_dir):
        flash(f"Client '{client}' does not exist.", 'error')
        return redirect(url_for('select_client'))

    alerts = read_alerts_file(client_dir)
    if not alerts:
        flash(f"No valid alerts found for client '{client}'.", 'warning')
        alerts = []

    if request.method == 'POST':
        alert = request.form.get('alert')
        if not alert:
            flash('Please select an alert.', 'warning')
            return redirect(url_for('alert_selection', client=client, action=action))

        if action == 'Add Suppression':
            spl = request.form.get('spl').strip()
            if not spl:
                flash('Please enter an SPL query.', 'warning')
                return redirect(url_for('alert_selection', client=client, action=action))
            return redirect(url_for('preview_suppression', client=client, action=action, alert=alert, spl=spl))
        elif action == 'Simple Tune':
            field = request.form.get('field')
            value = request.form.get('value').strip()
            if not value:
                flash('Please enter a value.', 'warning')
                return redirect(url_for('alert_selection', client=client, action=action))
            # Generate SPL for simple tune
            alert_id_snake_case = to_snake_case(alert)
            unix_time = int((datetime.now() + timedelta(weeks=1)).timestamp())
            spl = f'`notable_index` source={alert_id_snake_case} {field}="{value}" _time > {unix_time}'
            # Pass field and value as query parameters for later use
            return redirect(url_for('preview_suppression', client=client, action=action, alert=alert, spl=spl, field=field, value=value))
    else:
        return render_template_string(TEMPLATE_ALERT_SELECTION, client=client, action=action, alerts=alerts)

@app.route('/preview/<client>/<action>/<alert>', methods=['GET', 'POST'])
def preview_suppression(client, action, alert):
    spl = request.args.get('spl', '')
    field = request.args.get('field', '')
    value = request.args.get('value', '')
    if request.method == 'POST':
        if 'confirm' in request.form:
            if action == 'Add Suppression':
                nms_ticket = request.form.get('nms_ticket').strip()
                if not nms_ticket:
                    flash('NMS Ticket Number is required.', 'warning')
                    return redirect(url_for('preview_suppression', client=client, action=action, alert=alert, spl=spl))
                reason = request.form.get('reason').strip()
                if not reason:
                    flash('Reason is required.', 'warning')
                    return redirect(url_for('preview_suppression', client=client, action=action, alert=alert, spl=spl))
                suppression_id = f"{nms_ticket}_{client}_{alert.replace(' ', '_').lower()}"
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

                # Update suppressions file
                if update_suppressions_file(client, new_suppression):
                    flash(f"Suppression added for '{alert}'!", 'success')
                    return redirect(url_for('select_client'))
            elif action == 'Simple Tune':
                suppression_id = f"simple_tune_{to_snake_case(alert)}_{field}_{value}"
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

                # Update suppressions file
                if update_suppressions_file(client, new_suppression):
                    flash(f"Simple tune suppression added for '{alert}'!", 'success')
                    return redirect(url_for('select_client'))
        else:
            return redirect(url_for('alert_selection', client=client, action=action))
    else:
        return render_template_string(TEMPLATE_PREVIEW_SUPPRESSION, client=client, action=action, alert=alert, spl=spl, field=field, value=value)

@app.route('/export', methods=['GET', 'POST'])
def export_suppressions():
    if request.method == 'POST':
        client = request.form.get('client')
        if not client:
            flash('Please select a client to export suppressions.', 'warning')
            return redirect(url_for('export_suppressions'))

        client_dir = os.path.join(CLIENT_BASE_PATH, client)
        suppressions_file = os.path.join(client_dir, 'suppressions.yml')
        if not os.path.exists(suppressions_file):
            flash(f"No suppressions found for client '{client}'.", 'warning')
            return redirect(url_for('export_suppressions'))

        # Read the suppressions file
        with open(suppressions_file, 'r') as f:
            suppressions_content = f.read()

        # Serve the file content as a download
        return Response(
            suppressions_content,
            mimetype='text/yaml',
            headers={'Content-Disposition': f'attachment;filename={client}_suppressions.yml'}
        )
    else:
        if not os.path.exists(CLIENT_BASE_PATH):
            flash(f"Client base path '{CLIENT_BASE_PATH}' does not exist.", 'error')
            clients = []
        else:
            clients = [
                d for d in os.listdir(CLIENT_BASE_PATH)
                if os.path.isdir(os.path.join(CLIENT_BASE_PATH, d))
            ]
        return render_template_string(TEMPLATE_EXPORT_SUPPRESSIONS, clients=clients)

# Templates (as multi-line strings)
TEMPLATE_SELECT_CLIENT = '''
<!doctype html>
<title>Select Client</title>
<h1>Select Client</h1>
<form method=post>
  <select name="client">
    <option value="">--Select Client--</option>
    {% for client in clients %}
    <option value="{{ client }}">{{ client }}</option>
    {% endfor %}
  </select>
  <br><br>
  <input type=submit value=Next>
</form>
'''

TEMPLATE_SELECT_ACTION = '''
<!doctype html>
<title>Select Action</title>
<h1>Select Action for {{ client }}</h1>
<form method=post>
  <input type="radio" name="action" value="Add Suppression"> Add Suppression<br>
  <input type="radio" name="action" value="Simple Tune"> Simple Tune<br><br>
  <input type=submit value=Next>
</form>
'''

TEMPLATE_ALERT_SELECTION = '''
<!doctype html>
<title>Select Alert</title>
<h1>Select Alert for {{ client }}</h1>
<form method=post>
  <select name="alert">
    <option value="">--Select Alert--</option>
    {% for alert in alerts %}
    <option value="{{ alert }}">{{ alert }}</option>
    {% endfor %}
  </select>
  <br><br>
  {% if action == 'Add Suppression' %}
    <textarea name="spl" rows="5" cols="50" placeholder="Enter SPL Query here..."></textarea><br><br>
  {% elif action == 'Simple Tune' %}
    Select Field:
    <select name="field">
      <option value="dest">dest</option>
      <option value="host">host</option>
      <option value="user">user</option>
    </select><br><br>
    Value:
    <input type="text" name="value"><br><br>
  {% endif %}
  <input type=submit value=Next>
</form>
'''

TEMPLATE_PREVIEW_SUPPRESSION = '''
<!doctype html>
<title>Preview Suppression</title>
<h1>Preview Suppression</h1>
<pre>{{ spl }}</pre>
<form method=post>
  {% if action == 'Add Suppression' %}
    NMS Ticket Number: <input type="text" name="nms_ticket"><br><br>
    Reason: <input type="text" name="reason"><br><br>
  {% endif %}
  <button name="confirm" type="submit">Confirm</button>
  <button name="cancel" type="submit">Cancel</button>
</form>
'''

TEMPLATE_EXPORT_SUPPRESSIONS = '''
<!doctype html>
<title>Export Suppressions</title>
<h1>Export Suppressions</h1>
<form method=post>
  <select name="client">
    <option value="">--Select Client--</option>
    {% for client in clients %}
    <option value="{{ client }}">{{ client }}</option>
    {% endfor %}
  </select>
  <br><br>
  <input type=submit value=Export>
</form>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
