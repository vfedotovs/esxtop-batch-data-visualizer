#!/usr/bin/env python3
"""
CLI wrapper for esxtop_visualizer.parser module.
Maintains backward compatibility with existing Makefile workflows.

Usage:
    ./scripts/find_column_idx.py <filename.csv> [--limit N]
    ./scripts/find_column_idx.py <filename.csv> --vmdk-categories

Arguments:
    filename.csv        CSV file to parse
    --limit N           Print only first N columns (default: all columns)
    --vmdk-categories   List every VM VMDK stat category found in the header
                        as tab separated "counter<TAB>instance<TAB>column"
                        lines, one line per column. Consumed by
                        scripts/describe_extop_web.sh.
"""

import sys
from pathlib import Path

# Add src/ to path for development mode (allows running without installation)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.parser import (
    discover_vmdk_categories,
    parse_csv_header,
    print_column_info,
)


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_column_idx.py <filename.csv> "
              "[--limit N | --vmdk-categories]")
        sys.exit(1)

    filename = sys.argv[1]
    limit = None  # Default: print all columns

    # Discovery mode: machine readable, one line per Virtual Disk column.
    vmdk_categories = "--vmdk-categories" in sys.argv[2:]

    # Parse optional --limit argument
    if len(sys.argv) >= 4 and sys.argv[2] == "--limit":
        try:
            limit = int(sys.argv[3])
        except ValueError:
            print("Error: --limit must be followed by a number")
            sys.exit(1)

    try:
        if vmdk_categories:
            for category in discover_vmdk_categories(filename):
                for column in category.columns:
                    print(f"{category.counter}\t{category.instance}\t{column}")
            return

        columns = parse_csv_header(filename)

        # Print columns (all or limited)
        columns_to_print = columns[:limit] if limit else columns
        for col in columns_to_print:
            print_column_info(col, verbose=False)

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
