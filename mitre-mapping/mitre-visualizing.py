import matplotlib.pyplot as plt
import csv

# Read the Detailed TTP Coverage Report
covered = 0
not_covered = 0

with open('Detailed_TTP_Coverage_Report.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    for row in reader:
        if len(row) < 5:  # Skip summary or empty rows
            continue
        if row[4] == 'YES':
            covered += 1
        elif row[4] == 'NO':
            not_covered += 1

# Data for visualization
labels = ['Covered TTPs', 'Not Covered TTPs']
sizes = [covered, not_covered]
colors = ['#4CAF50', '#FF6347']
explode = (0.1, 0)  # explode the first slice

# Plotting
plt.figure(figsize=(8, 6))
plt.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=140)
plt.axis('equal')  # Equal aspect ratio ensures the pie chart is circular.
plt.title('TTP Coverage Visualization')
plt.show()
