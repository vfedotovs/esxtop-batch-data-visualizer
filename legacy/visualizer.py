#!/usr/bin/env python3
"""
Unified visualization script for esxtop time series data.
Replaces plot_chart_form_data_file.py and save_chart_from_column_id.py
"""

import argparse
import re
import sys
from datetime import datetime

import matplotlib.pyplot as plt


def parse_args():
    parser = argparse.ArgumentParser(
        description="Plot time series data from esxtop .data files"
    )
    parser.add_argument("data_file", help="Input .data file with timestamp: value format")
    parser.add_argument(
        "-o", "--output",
        help="Save chart to PNG file instead of displaying interactively"
    )
    parser.add_argument(
        "-s", "--scale",
        type=float,
        default=1.0,
        help="Scale factor for values (default: 1.0)"
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Don't display the chart (use with --output)"
    )
    return parser.parse_args()


def load_data(data_file, scale):
    """Load and parse time series data from .data file."""
    timestamps = []
    values = []
    skipped = 0

    with open(data_file, 'r') as f:
        for line in f:
            try:
                ts, val = line.strip().split(": ")
                dt = datetime.strptime(ts, "%m/%d/%Y %H:%M:%S")
                val = float(val) * scale
                timestamps.append(dt)
                values.append(val)
            except (ValueError, IndexError):
                skipped += 1
                continue

    if skipped > 0:
        print(f"Warning: Skipped {skipped} malformed lines", file=sys.stderr)

    return timestamps, values


def get_title(data_file):
    """Generate chart title from filename."""
    match = re.search(r'col_(\d+)', data_file)
    if match:
        return f"Column {match.group(1)} Data Over Time"
    return f"Data from {data_file}"


def get_default_output(data_file):
    """Generate default output filename from input filename."""
    match = re.search(r'col_(\d+)', data_file)
    if match:
        return f"esxtop_col_{match.group(1)}.png"
    return data_file.replace('.data', '.png')


def plot_chart(timestamps, values, title, scale, output=None, show=True):
    """Create and display/save the chart."""
    if not timestamps:
        print("Error: No data to plot", file=sys.stderr)
        sys.exit(1)

    label = f"Value × {scale}" if scale != 1.0 else "Value"
    ylabel = label

    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, values, label=label, color='blue')
    plt.xlabel("Timestamp")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(True)
    plt.legend()

    if output:
        plt.savefig(output)
        print(f"Chart saved as {output}")

    if show:
        plt.show()


def main():
    args = parse_args()

    timestamps, values = load_data(args.data_file, args.scale)
    title = get_title(args.data_file)

    show = not args.no_show
    plot_chart(timestamps, values, title, args.scale, args.output, show)


if __name__ == "__main__":
    main()
