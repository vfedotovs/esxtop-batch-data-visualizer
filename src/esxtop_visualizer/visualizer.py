"""
Visualization module for esxtop time series data.

This module provides utilities to load and plot time series data
extracted from esxtop batch exports.
"""

import re
import sys
from datetime import datetime
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt


def load_data_file(data_file: str, scale: float = 1.0) -> Tuple[List[datetime], List[float]]:
    """Load and parse time series data from .data file.

    Parses files in "timestamp: value" format and applies optional scaling.

    Args:
        data_file: Path to .data file with "timestamp: value" format
        scale: Scaling factor to apply to values (default: 1.0)

    Returns:
        Tuple of (timestamps, values) as lists

    Raises:
        FileNotFoundError: If data file doesn't exist
        ValueError: If no valid data points found

    Example:
        >>> timestamps, values = load_data_file("col_100.data", scale=100.0)
        >>> print(f"Loaded {len(timestamps)} data points")
    """
    timestamps = []
    values = []
    skipped = 0

    try:
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

        if not timestamps:
            raise ValueError("No valid data points found in file")

        return timestamps, values

    except FileNotFoundError:
        raise FileNotFoundError(f"Data file '{data_file}' not found")


def generate_title(data_file: str) -> str:
    """Generate chart title from filename.

    Extracts column number from filename pattern "col_NNN.data".

    Args:
        data_file: Input filename

    Returns:
        Chart title string

    Example:
        >>> generate_title("col_123.data")
        'Column 123 Data Over Time'
    """
    match = re.search(r'col_(\d+)', data_file)
    if match:
        return f"Column {match.group(1)} Data Over Time"
    return f"Data from {data_file}"


def generate_output_filename(data_file: str) -> str:
    """Generate default output filename from input filename.

    Args:
        data_file: Input filename

    Returns:
        PNG output filename

    Example:
        >>> generate_output_filename("col_123.data")
        'esxtop_col_123.png'
    """
    match = re.search(r'col_(\d+)', data_file)
    if match:
        return f"esxtop_col_{match.group(1)}.png"
    return data_file.replace('.data', '.png')


def plot_time_series(
    timestamps: List[datetime],
    values: List[float],
    title: str,
    scale: float = 1.0,
    output_file: Optional[str] = None,
    show: bool = True
) -> None:
    """Create and display/save a time series chart.

    Args:
        timestamps: List of datetime objects
        values: List of numeric values
        title: Chart title
        scale: Scale factor (for label display)
        output_file: Optional PNG output file path
        show: Whether to display interactive plot

    Raises:
        ValueError: If no data to plot

    Example:
        >>> timestamps, values = load_data_file("col_100.data")
        >>> plot_time_series(timestamps, values, "My Chart", output_file="chart.png")
    """
    if not timestamps:
        raise ValueError("No data to plot")

    # Generate appropriate y-axis label based on scale
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

    if output_file:
        plt.savefig(output_file)
        print(f"Chart saved as {output_file}")

    if show:
        plt.show()


def visualize(
    data_file: str,
    scale: float = 1.0,
    output_file: Optional[str] = None,
    show: bool = True
) -> None:
    """High-level function to load and visualize a data file.

    This is a convenience function that combines data loading and plotting.

    Args:
        data_file: Path to .data file
        scale: Scaling factor for values (default: 1.0)
        output_file: Optional PNG output file path
        show: Whether to display interactive plot (default: True)

    Raises:
        FileNotFoundError: If data file doesn't exist
        ValueError: If no valid data found

    Example:
        >>> visualize("col_100.data", scale=100.0, output_file="chart.png", show=False)
        Chart saved as chart.png
    """
    timestamps, values = load_data_file(data_file, scale)
    title = generate_title(data_file)
    plot_time_series(timestamps, values, title, scale, output_file, show)
