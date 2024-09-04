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

# Check if the word "risk" is in the ID or description
def contains_risk(id_value, description):
    return "risk" in id_value.lower() or "risk" in description.lower()

# Main function to match TTP coverage with Alert Status Report
def match_ttp_coverage(coverage_file, alert_status_file, output_file):
    alert_status = load_alert_status(alert_status_file)
    
    rows = []
    unique_ttps = set()
    ttps_covered_yes = set()

    with open(coverage_file, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        headers.append('Covered')  # Add a new column for coverage status

        for row in reader:
            id_value = row[0]
            description_value = row[3]
            ttp_id = row[1]
            unique_ttps.add(ttp_id)  # Collect all unique TTPs

            # Determine coverage based on AlertStatusReport
            if contains_risk(id_value, description_value):
                row.append('YES')
                ttps_covered_yes.add(ttp_id)  # Mark TTP as covered by "YES"
            elif id_value in alert_status:
                if alert_status[id_value] == 'LIVE':
                    row.append('YES')
                    ttps_covered_yes.add(ttp_id)  # Mark TTP as covered by "YES"
                else:  # "SHADOW" or any other status should be 'NO'
                    row.append('NO')
            else:
                row.append('NO')  # If not in AlertStatusReport, mark as 'NO'

            rows.append(row)

    # Calculate the percentage of coverage
    total_unique_ttps = len(unique_ttps)
    total_ttps_covered_yes = len(ttps_covered_yes)
    coverage_percentage = (total_ttps_covered_yes / total_unique_ttps) * 100 if total_unique_ttps > 0 else 0

    # Write the output CSV
    try:
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        logging.info(f"CSV file {output_file} created successfully with {total_ttps_covered_yes} unique TTPs covered as 'YES'.")
    except Exception as e:
        logging.error(f"Error writing to CSV file {output_file}: {e}")

    # Output the statistics
    logging.info(f"Total Unique TTPs in TTP_Coverage.csv: {total_unique_ttps}")
    logging.info(f"Unique TTPs Covered by 'YES': {total_ttps_covered_yes}")
    logging.info(f"Percentage of Coverage (YES): {coverage_percentage:.2f}%")

if __name__ == "__main__":
    # Define input and output files
    coverage_file = 'TTP_Coverage.csv'
    alert_status_file = 'AlertStatusReport.csv'
    output_file = 'Final_TTP_Coverage_Report.csv'

    # Run the matching process
    match_ttp_coverage(coverage_file, alert_status_file, output_file)
