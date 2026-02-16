"""
CSV parsing module for PDH-CSV format esxtop batch data.

This module provides utilities to parse Performance Data Helper (PDH) CSV format
headers from VMware ESXi esxtop batch mode exports.
"""

import csv
import re
from dataclasses import dataclass
from typing import List, Dict, Tuple
from collections import Counter


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

    def get_friendly_name(self) -> str:
        """Generate a human-friendly name for this column.

        Extracts the most relevant parts (VM name, disk, counter) for display.

        Returns:
            Friendly name suitable for chart titles

        Example:
            >>> col = ColumnMetadata(...)  # Virtual Disk(SRVBKPORA1VDF:scsi0:2)\Average MilliSec/Write
            >>> col.get_friendly_name()
            'SRVBKPORA1VDF:scsi0:2 - Average MilliSec/Write'
        """
        # Try to extract VMDK name from Virtual Disk category
        if "Virtual Disk" in self.category:
            # Extract VM:disk from "Virtual Disk(VM:scsi0:2)"
            match = re.search(r'Virtual Disk\(([^)]+)\)', self.category)
            if match:
                vmdk = match.group(1)
                return f"{vmdk} - {self.counter}"

        # Fallback: use category and counter
        if self.counter:
            return f"{self.category} - {self.counter}"

        # Last resort: use original
        return self.original


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


def summarize_columns(
    filename: str,
    category_pattern: str = None,
    counter_pattern: str = None
) -> Tuple[Dict[str, int], Dict[str, int], Dict[Tuple[str, str], int]]:
    """Summarize categories and counters in CSV file with counts.

    Args:
        filename: Path to CSV file
        category_pattern: Optional regex to filter categories
        counter_pattern: Optional regex to filter counters

    Returns:
        Tuple of (category_counts, counter_counts, combined_counts)
        - category_counts: Dict mapping category to count
        - counter_counts: Dict mapping counter to count
        - combined_counts: Dict mapping (category, counter) tuple to count

    Example:
        >>> cats, counters, combined = summarize_columns("esxtop.csv")
        >>> print(f"Virtual Disk columns: {cats.get('Virtual Disk', 0)}")
        >>> print(f"Write latency metrics: {counters.get('Average MilliSec/Write', 0)}")
    """
    columns = parse_csv_header(filename)

    # Apply filters if provided
    if category_pattern or counter_pattern:
        filtered_columns = []
        for col in columns:
            if category_pattern and not re.search(category_pattern, col.category, re.IGNORECASE):
                continue
            if counter_pattern and not re.search(counter_pattern, col.counter, re.IGNORECASE):
                continue
            filtered_columns.append(col)
        columns = filtered_columns

    # Count occurrences
    categories = Counter(col.category for col in columns if col.category)
    counters = Counter(col.counter for col in columns if col.counter)
    combined = Counter((col.category, col.counter) for col in columns if col.category and col.counter)

    return dict(categories), dict(counters), dict(combined)


def print_summary(
    category_counts: Dict[str, int],
    counter_counts: Dict[str, int],
    combined_counts: Dict[Tuple[str, str], int],
    top_n: int = 20
) -> None:
    """Print formatted summary of categories and counters.

    Args:
        category_counts: Dictionary of category to count
        counter_counts: Dictionary of counter to count
        combined_counts: Dictionary of (category, counter) tuple to count
        top_n: Number of top items to display (default: 20)
    """
    print("=" * 80)
    print(f"COLUMN SUMMARY - Top {top_n} Categories and Counters")
    print("=" * 80)

    # Print top categories
    print(f"\n📁 TOP {top_n} CATEGORIES:")
    print("-" * 80)
    sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (category, count) in enumerate(sorted_categories[:top_n], 1):
        print(f"{i:3}. {category:50} [{count:4} columns]")

    # Print top counters
    print(f"\n📊 TOP {top_n} COUNTERS:")
    print("-" * 80)
    sorted_counters = sorted(counter_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (counter, count) in enumerate(sorted_counters[:top_n], 1):
        print(f"{i:3}. {counter:50} [{count:4} columns]")

    # Print top combinations
    print(f"\n🔗 TOP {top_n} CATEGORY + COUNTER COMBINATIONS:")
    print("-" * 80)
    sorted_combined = sorted(combined_counts.items(), key=lambda x: x[1], reverse=True)
    for i, ((category, counter), count) in enumerate(sorted_combined[:top_n], 1):
        # Truncate long names for display
        cat_short = category[:35] + "..." if len(category) > 35 else category
        cnt_short = counter[:35] + "..." if len(counter) > 35 else counter
        print(f"{i:3}. {cat_short:38} | {cnt_short:38} [{count:3}]")

    # Print totals
    print(f"\n📈 TOTALS:")
    print("-" * 80)
    print(f"Total unique categories: {len(category_counts)}")
    print(f"Total unique counters: {len(counter_counts)}")
    print(f"Total unique combinations: {len(combined_counts)}")
    total_columns = sum(category_counts.values())
    print(f"Total columns (with category): {total_columns}")
    print("=" * 80)
