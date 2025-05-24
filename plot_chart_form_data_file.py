#!/usr/bin/env python3

import sys
import matplotlib.pyplot as plt
from datetime import datetime

if len(sys.argv) < 2:
    print("Usage: plot_chart_from_ext.py <data_values_filterd_by_column_idx.data>")
    sys.exit(1)

data_file = sys.argv[1]

timestamps = []
values = []

with open(data_file, 'r') as f:
    for line in f:
        try:
            ts, val = line.strip().split(": ")
            dt = datetime.strptime(ts, "%m/%d/%Y %H:%M:%S")
            val = float(val) * 100
            timestamps.append(dt)
            values.append(val)
        except:
            continue

plt.figure(figsize=(12, 6))
plt.plot(timestamps, values, label='Value × 1000', color='blue')
plt.xlabel("Timestamp")
plt.ylabel("Value × 1000")
plt.title(f"Data from {data_file}")
plt.xticks(rotation=45)
plt.tight_layout()
plt.grid(True)
plt.legend()
plt.show()

