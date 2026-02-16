#!/usr/bin/env python3
"""
Summarize categories and counters in esxtop CSV file.
Helps explore what metrics are available for extraction.

Usage:
    ./scripts/summarize_columns.py <csv_file> [options]

Options:
    --category PATTERN    Filter by category pattern (regex)
    --counter PATTERN     Filter by counter pattern (regex)
    --top N              Show top N items (default: 20)
    --save FILE          Save summary to file

Example:
    # Show all categories and counters
    ./scripts/summarize_columns.py esxtop_batch.csv

    # Find all Virtual Disk metrics
    ./scripts/summarize_columns.py esxtop_batch.csv --category "Virtual Disk"

    # Find all write latency metrics
    ./scripts/summarize_columns.py esxtop_batch.csv --counter "Write"

    # Find write latency for Virtual Disks
    ./scripts/summarize_columns.py esxtop_batch.csv --category "Virtual Disk" --counter "Write"
"""

import argparse
import sys
from pathlib import Path

# Add src/ to path for development mode
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.parser import summarize_columns, print_summary


def main():
    parser = argparse.ArgumentParser(
        description="Summarize categories and counters in esxtop CSV file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show summary of all metrics
  %(prog)s esxtop_batch.csv

  # Find Virtual Disk metrics
  %(prog)s esxtop_batch.csv --category "Virtual Disk"

  # Find write latency metrics across all devices
  %(prog)s esxtop_batch.csv --counter "MilliSec/Write"

  # Find physical disk (naa) write metrics
  %(prog)s esxtop_batch.csv --category "Physical Disk.*naa" --counter "Write"

  # Show top 50 instead of default 20
  %(prog)s esxtop_batch.csv --top 50

  # Save summary to file
  %(prog)s esxtop_batch.csv --save counter_help.txt
        """
    )
    parser.add_argument(
        "csv_file",
        help="Path to esxtop CSV file"
    )
    parser.add_argument(
        "--category",
        help="Filter by category pattern (regex, case-insensitive)"
    )
    parser.add_argument(
        "--counter",
        help="Filter by counter pattern (regex, case-insensitive)"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top items to display (default: 20)"
    )
    parser.add_argument(
        "--save",
        help="Save summary to file instead of printing"
    )

    args = parser.parse_args()

    try:
        print(f"Analyzing {args.csv_file}...", file=sys.stderr)

        # Get summary
        category_counts, counter_counts, combined_counts = summarize_columns(
            args.csv_file,
            category_pattern=args.category,
            counter_pattern=args.counter
        )

        # Print or save summary
        if args.save:
            original_stdout = sys.stdout
            with open(args.save, 'w') as f:
                sys.stdout = f
                print_summary(category_counts, counter_counts, combined_counts, args.top)
                sys.stdout = original_stdout
            print(f"Summary saved to {args.save}", file=sys.stderr)
        else:
            print_summary(category_counts, counter_counts, combined_counts, args.top)

    except FileNotFoundError:
        print(f"Error: File '{args.csv_file}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
