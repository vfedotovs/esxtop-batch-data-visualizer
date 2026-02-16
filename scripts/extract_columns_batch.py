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


def main():
    if len(sys.argv) < 3:
        print("Usage: extract_columns_batch.py <csv_file> <col1> <col2> [col3] ...")
        print()
        print("Extract multiple columns from CSV in a single pass.")
        print("Much more efficient than extracting columns individually.")
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
        output_files = extract_and_save_batch(filename, column_indices)

        print(f"Successfully extracted {len(output_files)} columns:")
        for output_file in output_files:
            print(f"  - {output_file}")

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
