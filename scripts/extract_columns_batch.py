#!/usr/bin/env python3
"""
CLI wrapper for batch extraction of multiple columns.
Reads the CSV file once and extracts all specified columns efficiently.

Usage:
    ./scripts/extract_columns_batch.py <csv_file> <col1> <col2> <col3> ...

Example:
    ./scripts/extract_columns_batch.py esxtop.csv 100 200 300
    # Creates: col_100.data, col_200.data, col_300.data
"""

import sys
from pathlib import Path

# Add src/ to path for development mode (allows running without installation)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.extractor import extract_and_save_batch
from esxtop_visualizer.parser import parse_csv_header


def main():
    if len(sys.argv) < 3:
        print("Usage: extract_columns_batch.py <csv_file> <col1> <col2> [col3] ...")
        print()
        print("Extract multiple columns from CSV in a single pass.")
        print("Much more efficient than extracting columns individually.")
        print("Also saves human-friendly titles to .meta files for better charts.")
        print()
        print("Example:")
        print("  ./scripts/extract_columns_batch.py esxtop.csv 100 200 300")
        sys.exit(1)

    filename = sys.argv[1]

    # Parse column indices
    try:
        column_indices = [int(col) for col in sys.argv[2:]]
    except ValueError:
        print("Error: Column indices must be integers")
        sys.exit(1)

    if not column_indices:
        print("Error: At least one column index must be provided")
        sys.exit(1)

    try:
        print(f"Extracting {len(column_indices)} columns from {filename}...")

        # Parse CSV header to get friendly names
        print("Reading column metadata...")
        columns = parse_csv_header(filename)
        column_map = {col.index: col for col in columns}

        # Build title mapping
        column_titles = {}
        for idx in column_indices:
            if idx in column_map:
                column_titles[idx] = column_map[idx].get_friendly_name()

        # Extract with metadata
        output_files = extract_and_save_batch(filename, column_indices, column_titles=column_titles)

        print(f"Successfully extracted {len(output_files)} columns:")
        for idx, output_file in zip(column_indices, output_files):
            title = column_titles.get(idx, "Unknown")
            print(f"  - {output_file} ({title})")

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
