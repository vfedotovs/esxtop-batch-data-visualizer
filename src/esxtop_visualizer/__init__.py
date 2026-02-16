"""
esxtop_visualizer: Parse and visualize VMware ESXi esxtop batch mode data.

This package provides tools to:
- Parse PDH-CSV format headers from esxtop exports
- Extract time series data from specific columns
- Visualize performance metrics over time

Example:
    >>> from esxtop_visualizer import parse_csv_header, extract_and_save, visualize
    >>> columns = parse_csv_header("esxtop_batch.csv")
    >>> extract_and_save("esxtop_batch.csv", 100)
    >>> visualize("col_100.data", scale=100.0)
"""

__version__ = "1.0.0"
__author__ = "esxtop-visualizer contributors"

# Public API exports from parser module
from .parser import (
    ColumnMetadata,
    parse_csv_header,
    find_columns_by_pattern,
    print_column_info,
)

# Public API exports from extractor module
from .extractor import (
    TimeSeriesData,
    extract_column_data,
    save_time_series,
    extract_and_save,
)

# Public API exports from visualizer module
from .visualizer import (
    load_data_file,
    plot_time_series,
    visualize,
    generate_title,
    generate_output_filename,
)

__all__ = [
    # Parser
    "ColumnMetadata",
    "parse_csv_header",
    "find_columns_by_pattern",
    "print_column_info",
    # Extractor
    "TimeSeriesData",
    "extract_column_data",
    "save_time_series",
    "extract_and_save",
    # Visualizer
    "load_data_file",
    "plot_time_series",
    "visualize",
    "generate_title",
    "generate_output_filename",
]
