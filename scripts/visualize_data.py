#!/usr/bin/env python3
"""
CLI wrapper for esxtop_visualizer.visualizer module.
Maintains backward compatibility with existing Makefile workflows.

Usage:
    ./scripts/visualize_data.py <data_file> [-o output] [-s scale] [--no-show]
"""

import argparse
import sys
from pathlib import Path

# Add src/ to path for development mode (allows running without installation)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.visualizer import visualize


def main():
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

    args = parser.parse_args()

    try:
        show = not args.no_show
        visualize(args.data_file, args.scale, args.output, show)

    except FileNotFoundError:
        print(f"Error: File '{args.data_file}' not found.", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
