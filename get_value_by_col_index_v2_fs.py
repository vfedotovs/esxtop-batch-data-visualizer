#!/usr/bin/env python3

import csv
import re
import sys
from collections import OrderedDict

if len(sys.argv) < 3:
    print("Usage: get_value_by_col_index.py <esxtop-batch.csv> <column_index>")
    sys.exit(1)

filename = sys.argv[1]
column_index = int(sys.argv[2])
output_file = f"col_{column_index}.data"

timestamp_pattern = re.compile(r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}')
time_series = OrderedDict()

try:
    with open(filename, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            for i, cell in enumerate(row):
                if timestamp_pattern.fullmatch(cell.strip('"')):
                    timestamp = cell.strip('"')
                    values = row[i + 1:]
                    time_series[timestamp] = values
                    break

    # Write to output file
    with open(output_file, 'w') as out:
        for timestamp, values in time_series.items():
            try:
                value = float(values[column_index])
                out.write(f"{timestamp}: {value}\n")
            except (IndexError, ValueError):
                out.write(f"{timestamp}: NaN\n")

    print(f"Saved output to: {output_file}")

except FileNotFoundError:
    print(f"Error: File '{filename}' not found.")
    sys.exit(1)
except Exception as e:
    print(f"An error occurred: {e}")
    sys.exit(1)

