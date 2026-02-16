#!/usr/bin/env python3
"""
CLI wrapper for esxtop_visualizer.extractor module.
Maintains backward compatibility with existing Makefile workflows.

Usage:
    ./scripts/extract_column.py <esxtop-batch.csv> <column_index>
"""

import sys
from pathlib import Path

# Add src/ to path for development mode (allows running without installation)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.extractor import extract_and_save


def main():
    if len(sys.argv) < 3:
        print("Usage: extract_column.py <esxtop-batch.csv> <column_index>")
        sys.exit(1)

    filename = sys.argv[1]
    column_index = int(sys.argv[2])

    try:
        output_file = extract_and_save(filename, column_index)
        print(f"Saved output to: {output_file}")

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
