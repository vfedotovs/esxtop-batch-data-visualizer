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

# Single source of truth for the package version. pyproject.toml reads this
# via [tool.setuptools.dynamic], so bump it here only. Keep it a plain string
# literal: setuptools parses this file statically rather than importing it.
__version__ = "2026.8.17"
__author__ = "esxtop-visualizer contributors"

# Public API exports from parser module
from .parser import (
    ColumnMetadata,
    VmdkCategory,
    parse_csv_header,
    discover_vmdk_categories,
    format_vmdk_categories,
    find_columns_by_pattern,
    print_column_info,
    summarize_columns,
    print_summary,
)

# Public API exports from extractor module
from .extractor import (
    TimeSeriesData,
    SeriesStats,
    numeric_samples,
    series_stats,
    extract_column_data,
    save_time_series,
    extract_and_save,
    extract_multiple_columns,
    save_extracted_columns,
    extract_and_save_batch,
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
    "VmdkCategory",
    "parse_csv_header",
    "discover_vmdk_categories",
    "format_vmdk_categories",
    "find_columns_by_pattern",
    "print_column_info",
    "summarize_columns",
    "print_summary",
    # Extractor
    "TimeSeriesData",
    "SeriesStats",
    "numeric_samples",
    "series_stats",
    "extract_column_data",
    "save_time_series",
    "extract_and_save",
    "extract_multiple_columns",
    "save_extracted_columns",
    "extract_and_save_batch",
    # Visualizer
    "load_data_file",
    "plot_time_series",
    "visualize",
    "generate_title",
    "generate_output_filename",
]
