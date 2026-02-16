#!/usr/bin/env python3
"""
CLI wrapper for esxtop_visualizer.parser module.
Maintains backward compatibility with existing Makefile workflows.

Usage:
    ./scripts/find_column_idx.py <filename.csv>
"""

import sys
from pathlib import Path

# Add src/ to path for development mode (allows running without installation)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.parser import parse_csv_header, print_column_info


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_column_idx.py <filename.csv>")
        sys.exit(1)

    filename = sys.argv[1]

    try:
        columns = parse_csv_header(filename)

        # Print first 10 columns (matching original behavior)
        for col in columns[:10]:
            print_column_info(col, verbose=False)

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
