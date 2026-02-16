"""
Time series data extraction module for esxtop CSV files.

This module extracts time series performance data from specific columns
in PDH-CSV format esxtop batch exports.
"""

import csv
import re
from collections import OrderedDict
from typing import Dict, Optional, Iterator, Tuple, List


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


def extract_multiple_columns(
    filename: str,
    column_indices: List[int]
) -> Dict[int, TimeSeriesData]:
    """Extract time series data from multiple CSV columns in a single pass.

    This is much more efficient than calling extract_column_data multiple times
    for large files, as it only reads the CSV file once.

    Args:
        filename: Path to CSV file
        column_indices: List of zero-based column indices to extract

    Returns:
        Dictionary mapping column index to TimeSeriesData object

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV cannot be parsed

    Example:
        >>> results = extract_multiple_columns("esxtop_batch.csv", [100, 200, 300])
        >>> print(f"Extracted data for {len(results)} columns")
        >>> for col_idx, data in results.items():
        ...     print(f"Column {col_idx}: {len(data)} points")
    """
    # Initialize TimeSeriesData for each column
    time_series_map = {idx: TimeSeriesData() for idx in column_indices}

    try:
        with open(filename, newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)

            for row in reader:
                # Look for timestamp in any column
                timestamp = None
                for cell in row:
                    cell_clean = cell.strip('"')
                    if TIMESTAMP_PATTERN.fullmatch(cell_clean):
                        timestamp = cell_clean
                        break

                if timestamp:
                    # Extract value from each target column
                    for col_idx in column_indices:
                        try:
                            value = float(row[col_idx])
                            time_series_map[col_idx].add_point(timestamp, value)
                        except (IndexError, ValueError):
                            time_series_map[col_idx].add_point(timestamp, None)

        return time_series_map

    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file '{filename}' not found")
    except Exception as e:
        raise ValueError(f"Error extracting data: {e}")


def extract_and_save_batch(
    filename: str,
    column_indices: List[int],
    output_dir: str = "."
) -> List[str]:
    """Extract multiple columns and save each to a separate .data file.

    This function reads the CSV file once and extracts all specified columns,
    then saves each to col_{index}.data. Much more efficient than multiple
    individual extractions for large files.

    Args:
        filename: Path to CSV file
        column_indices: List of column indices to extract
        output_dir: Directory to save output files (default: current directory)

    Returns:
        List of created output file paths

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV cannot be parsed

    Example:
        >>> files = extract_and_save_batch("esxtop_batch.csv", [100, 200, 300])
        >>> print(f"Created {len(files)} files: {files}")
        Created 3 files: ['col_100.data', 'col_200.data', 'col_300.data']
    """
    import os

    # Extract all columns in one pass
    results = extract_multiple_columns(filename, column_indices)

    # Save each column to a file
    output_files = []
    for col_idx, time_series in results.items():
        output_file = os.path.join(output_dir, f"col_{col_idx}.data")
        save_time_series(time_series, output_file)
        output_files.append(output_file)

    return output_files
