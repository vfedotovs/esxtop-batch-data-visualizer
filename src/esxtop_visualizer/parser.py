"""
CSV parsing module for PDH-CSV format esxtop batch data.

This module provides utilities to parse Performance Data Helper (PDH) CSV format
headers from VMware ESXi esxtop batch mode exports.
"""

import csv
import re
from dataclasses import dataclass
from typing import List


@dataclass
class ColumnMetadata:
    """Represents metadata for a single CSV column.

    Attributes:
        index: Zero-based column index
        host: ESXi hostname extracted from column path
        category: Performance category (e.g., "Virtual Disk")
        counter: Performance counter name (e.g., "Average MilliSec/Write")
        original: Original column header string
    """
    index: int
    host: str
    category: str
    counter: str
    original: str

    def __repr__(self) -> str:
        return f"Column {self.index}: {self.original}"

    def matches_pattern(self, pattern: str) -> bool:
        """Check if column matches a regex pattern.

        Args:
            pattern: Regular expression pattern to match

        Returns:
            True if the column's original header matches the pattern
        """
        return bool(re.search(pattern, self.original, re.IGNORECASE))


def parse_csv_header(filename: str) -> List[ColumnMetadata]:
    """Parse PDH-CSV header and extract column metadata.

    Parses CSV files in PDH-CSV format (Performance Data Helper) which use
    the structure: \\hostname\category\counter

    Args:
        filename: Path to CSV file

    Returns:
        List of ColumnMetadata objects, one per column

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If file cannot be parsed as CSV

    Example:
        >>> columns = parse_csv_header("esxtop_batch.csv")
        >>> print(columns[0])
        Column 0: \\esx01.example.com\Virtual Disk(VM:scsi0:0)\Average MilliSec/Write
    """
    columns = []

    try:
        with open(filename, newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)

            for i, col in enumerate(header):
                col = col.strip('"')  # Remove quotes

                # Skip PDH-CSV metadata columns like "(PDH-CSV 4.0) (UTC)(0)"
                if col.startswith("(PDH-CSV"):
                    continue

                # Parse format: \\host\category\counter
                if col.startswith("\\\\"):
                    parts = col.split("\\")[2:]  # First two elements are empty
                    if len(parts) >= 2:
                        host = col.split("\\")[2]
                        category = parts[1]
                        counter = "\\".join(parts[2:]) if len(parts) > 2 else ""
                    else:
                        host = category = counter = ""
                else:
                    host = category = counter = ""

                columns.append(ColumnMetadata(i, host, category, counter, col))

        return columns

    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file '{filename}' not found")
    except Exception as e:
        raise ValueError(f"Error parsing CSV file: {e}")


def find_columns_by_pattern(filename: str, pattern: str) -> List[ColumnMetadata]:
    """Find all columns matching a regex pattern.

    Args:
        filename: Path to CSV file
        pattern: Regular expression pattern to match against column names

    Returns:
        List of matching ColumnMetadata objects

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If file cannot be parsed as CSV

    Example:
        >>> columns = find_columns_by_pattern("esxtop_batch.csv", r"scsi.*Write")
        >>> print(f"Found {len(columns)} matching columns")
    """
    columns = parse_csv_header(filename)
    return [col for col in columns if col.matches_pattern(pattern)]


def print_column_info(column: ColumnMetadata, verbose: bool = False) -> None:
    """Print formatted column information.

    Args:
        column: ColumnMetadata object to print
        verbose: If True, print detailed multi-line format.
                 If False, print compact single-line format.
    """
    if verbose:
        print(f"Column {column.index}:")
        print(f"  Host:     {column.host}")
        print(f"  Category: {column.category}")
        print(f"  Counter:  {column.counter}")
        print(f"  Raw:      {column.original}")
        print()
    else:
        print(f"Column {column.index} RAW {column.original}' ")
