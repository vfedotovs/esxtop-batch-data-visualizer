#!/usr/bin/env python3
"""
CLI wrapper for batch extraction of multiple columns.
Reads the CSV file once and extracts all specified columns efficiently.

Usage:
    ./scripts/extract_columns_batch.py [--quiet] [--stats FILE] <csv_file> <col1> ...

Options:
    --quiet         Suppress the per-column listing.
    --stats FILE    Also write the min/max/average of every extracted column to
                    FILE, as tab separated
                    "column<TAB>sort_key<TAB>min<TAB>avg<TAB>max<TAB>samples"
                    lines. Consumed by scripts/describe_extop_web.sh.

Example:
    ./scripts/extract_columns_batch.py esxtop.csv 100 200 300
    # Creates: col_100.data, col_200.data, col_300.data
"""

import sys
from pathlib import Path

# Add src/ to path for development mode (allows running without installation)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.extractor import (
    extract_multiple_columns,
    numeric_samples,
    save_extracted_columns,
    series_stats,
)
from esxtop_visualizer.parser import parse_csv_header


# A column with no numeric samples at all sorts below every column that has
# one, instead of impersonating the quietest disk with a 0.0000 average.
NO_DATA_SORT_KEY = "-1"
NO_DATA = "n/a"


def write_stats(results, stats_file):
    """Write per-column min/avg/max over the samples already in memory.

    One tab separated line per column:

        column <TAB> sort_key <TAB> min <TAB> avg <TAB> max <TAB> samples

    ``sort_key`` is the average at full precision, which the report sorts on
    descending; the three statistics are rounded for display. Missing samples
    are excluded by ``series_stats()`` rather than counted as zero.
    """
    with open(stats_file, 'w') as out:
        for col_idx, time_series in results.items():
            stats = series_stats(time_series)
            if stats is None:
                out.write(f"{col_idx}\t{NO_DATA_SORT_KEY}\t{NO_DATA}\t"
                          f"{NO_DATA}\t{NO_DATA}\t0\n")
                continue

            samples = len(numeric_samples(time_series))
            out.write(
                f"{col_idx}\t{stats.average:.10f}\t{stats.minimum:.4f}\t"
                f"{stats.average:.4f}\t{stats.maximum:.4f}\t{samples}\n"
            )


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

    # --quiet suppresses the per-column listing, which runs to one line per
    # matched column. A real capture matches dozens, and the report that
    # follows names every column anyway.
    args = sys.argv[1:]
    quiet = '--quiet' in args
    args = [a for a in args if a != '--quiet']

    # --stats takes the path to write the summary to.
    stats_file = None
    if '--stats' in args:
        index = args.index('--stats')
        if index + 1 >= len(args):
            print("Error: --stats must be followed by an output file path")
            sys.exit(1)
        stats_file = args[index + 1]
        del args[index:index + 2]

    if len(args) < 2:
        print("Usage: extract_columns_batch.py [--quiet] [--stats FILE] "
              "<csv_file> <col1> [col2] ...")
        sys.exit(1)

    filename = args[0]

    # Parse column indices
    try:
        column_indices = [int(col) for col in args[1:]]
    except ValueError:
        print("Error: Column indices must be integers")
        sys.exit(1)

    if not column_indices:
        print("Error: At least one column index must be provided")
        sys.exit(1)

    try:
        if not quiet:
            print(f"Extracting {len(column_indices)} columns from {filename}...")
            print("Reading column metadata...")

        # Parse CSV header to get friendly names
        columns = parse_csv_header(filename)
        column_map = {col.index: col for col in columns}

        # Build title mapping
        column_titles = {}
        for idx in column_indices:
            if idx in column_map:
                column_titles[idx] = column_map[idx].get_friendly_name()

        # Extract with metadata. The samples are kept in hand so --stats can
        # summarise them without reading the capture, or the .data files, twice.
        results = extract_multiple_columns(filename, column_indices)
        output_files = save_extracted_columns(results, column_titles=column_titles)

        if stats_file:
            write_stats(results, stats_file)

        if quiet:
            print(f"Extracted {len(output_files)} columns.")
        else:
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
