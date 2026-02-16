"""
Time series data extraction module for esxtop CSV files.

This module extracts time series performance data from specific columns
in PDH-CSV format esxtop batch exports.
"""

import csv
import re
from collections import OrderedDict
from typing import Dict, Optional, Iterator, Tuple


class TimeSeriesData:
    """Represents extracted time series data with timestamp-value pairs.

    Internally uses OrderedDict to maintain temporal sequence.

    Attributes:
        data: Ordered dictionary mapping timestamps to values
    """

    def __init__(self):
        self.data: Dict[str, Optional[float]] = OrderedDict()

    def add_point(self, timestamp: str, value: Optional[float]) -> None:
        """Add a data point to the time series.

        Args:
            timestamp: Timestamp string in MM/DD/YYYY HH:MM:SS format
            value: Numeric value or None for missing data
        """
        self.data[timestamp] = value

    def __len__(self) -> int:
        """Return number of data points."""
        return len(self.data)

    def __iter__(self) -> Iterator[Tuple[str, Optional[float]]]:
        """Iterate over (timestamp, value) pairs."""
        return iter(self.data.items())

    def __repr__(self) -> str:
        return f"TimeSeriesData({len(self)} points)"


# Timestamp pattern: MM/DD/YYYY HH:MM:SS (quoted in CSV)
TIMESTAMP_PATTERN = re.compile(r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}')


def extract_column_data(filename: str, column_index: int) -> TimeSeriesData:
    """Extract time series data from a specific CSV column.

    Scans CSV rows looking for timestamp cells, then extracts the corresponding
    value from the specified column index.

    Args:
        filename: Path to CSV file
        column_index: Zero-based column index to extract

    Returns:
        TimeSeriesData object containing timestamp-value pairs

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV cannot be parsed

    Example:
        >>> data = extract_column_data("esxtop_batch.csv", 100)
        >>> print(f"Extracted {len(data)} data points")
    """
    time_series = TimeSeriesData()

    try:
        with open(filename, newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)

            for row in reader:
                # Look for timestamp in any column
                for cell in row:
                    cell_clean = cell.strip('"')
                    if TIMESTAMP_PATTERN.fullmatch(cell_clean):
                        timestamp = cell_clean

                        # Extract value from target column
                        try:
                            value = float(row[column_index])
                            time_series.add_point(timestamp, value)
                        except (IndexError, ValueError):
                            time_series.add_point(timestamp, None)
                        break

        return time_series

    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file '{filename}' not found")
    except Exception as e:
        raise ValueError(f"Error extracting data: {e}")


def save_time_series(time_series: TimeSeriesData, output_file: str) -> None:
    """Save time series data to a .data file.

    Output format: One line per data point in "timestamp: value" format.
    Missing values are written as "NaN".

    Args:
        time_series: TimeSeriesData object
        output_file: Path to output file

    Example:
        >>> data = extract_column_data("esxtop_batch.csv", 100)
        >>> save_time_series(data, "col_100.data")
    """
    with open(output_file, 'w') as out:
        for timestamp, value in time_series:
            if value is not None:
                out.write(f"{timestamp}: {value}\n")
            else:
                out.write(f"{timestamp}: NaN\n")


def extract_and_save(
    filename: str,
    column_index: int,
    output_file: Optional[str] = None
) -> str:
    """Extract column data and save to file in one operation.

    This is a convenience function that combines extraction and saving.

    Args:
        filename: Path to CSV file
        column_index: Column index to extract
        output_file: Optional output filename (defaults to col_{index}.data)

    Returns:
        Path to the created output file

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV cannot be parsed

    Example:
        >>> output = extract_and_save("esxtop_batch.csv", 100)
        >>> print(f"Saved to {output}")
        Saved to col_100.data
    """
    if output_file is None:
        output_file = f"col_{column_index}.data"

    time_series = extract_column_data(filename, column_index)
    save_time_series(time_series, output_file)

    return output_file
