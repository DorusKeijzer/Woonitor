import json
import csv
import sys

jsonfile = sys.argv[1]

# Open the JSON file
with open(jsonfile, 'r') as json_file:
    # Load JSON data
    data = json.load(json_file)

# Use the same name as the json
csv_file = json.strip('.json') + ".csv"

# Extract unique keys from all objects in the JSON data
unique_keys = set()
for item in data:
    unique_keys.update(item.keys())

# Open the CSV file in write mode
with open(csv_file, 'w', newline='') as csvfile:
    # Create a CSV writer object
    csvwriter = csv.writer(csvfile)

    # Write the header
    csvwriter.writerow(list(unique_keys))

    # Write the data
    for row in data:
        # Create a list with the values in the order of the header
        csvwriter.writerow([row.get(key, '') for key in unique_keys])
