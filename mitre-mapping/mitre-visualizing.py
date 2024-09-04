import csv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

# Load Alert Status Report
def load_alert_status(file_path):
    alert_status = {}
    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            search_name, status = row
            alert_status[search_name] = status.upper()
    return alert_status

# Main function to match TTP coverage with Alert Status Report
def match_ttp_coverage(coverage_file, alert_status_file, output_file):
    alert_status = load_alert_status(alert_status_file)
    
    rows = []
    live_ttps_count = 0

    with open(coverage_file, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        headers.append('Covered')  # Add a new column for coverage status

        for row in reader:
            id_value = row[0]
            if id_value in alert_status:
                if alert_status[id_value] == 'LIVE':
                    row.append('YES')
                    live_ttps_count += 1
                else:  # Shadow or any other status should be 'NO'
                    row.append('NO')
            else:
                row.append('NO')  # If not in AlertStatusReport, mark as 'NO'
            rows.append(row)

    # Write the output CSV
    try:
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        logging.info(f"CSV file {output_file} created successfully with {live_ttps_count} LIVE TTPs.")
    except Exception as e:
        logging.error(f"Error writing to CSV file {output_file}: {e}")

if __name__ == "__main__":
    # Define input and output files
    coverage_file = 'TTP_Coverage.csv'
    alert_status_file = 'AlertStatusReport.csv'
    output_file = 'Final_TTP_Coverage_Report.csv'

    # Run the matching process
    match_ttp_coverage(coverage_file, alert_status_file, output_file)
