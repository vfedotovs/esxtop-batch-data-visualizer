#!/usr/bin/env python3

import sys
import matplotlib.pyplot as plt
from datetime import datetime
import os
import re

if len(sys.argv) < 2:
    print("Usage: plot_chart_from_ext.py <data_values_filtered_by_column_idx.data>")
    sys.exit(1)

data_file = sys.argv[1]

timestamps = []
values = []

# Extract column index from filename
match = re.search(r'col_(\d+)', data_file)
if match:
    col_index = match.group(1)
    output_file = f"esxtop_col_{col_index}.png"
else:
    print("Error: Could not extract column index from filename.")
    sys.exit(1)

with open(data_file, 'r') as f:
    for line in f:
        try:
            ts, val = line.strip().split(": ")
            dt = datetime.strptime(ts, "%m/%d/%Y %H:%M:%S")
            val = float(val) * 1
            timestamps.append(dt)
            values.append(val)
        except ValueError:
            continue

plt.figure(figsize=(12, 6))
plt.plot(timestamps, values, label='Value', color='blue')
plt.xlabel("Timestamp")
plt.ylabel("Value")
plt.title(f"Column {col_index} Data Over Time")
plt.xticks(rotation=45)
plt.tight_layout()
plt.grid(True)
plt.legend()

# Save plot to PNG file
plt.savefig(output_file)
print(f"Chart saved as {output_file}")

