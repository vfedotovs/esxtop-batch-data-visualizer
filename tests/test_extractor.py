"""
Tests for esxtop_visualizer.extractor module.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for testing
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.extractor import (
    TimeSeriesData,
    extract_column_data,
    save_time_series,
    extract_and_save,
)


def test_time_series_data_creation():
    """Test TimeSeriesData class basic functionality."""
    ts = TimeSeriesData()
    assert len(ts) == 0

    ts.add_point("01/01/2024 12:00:00", 42.5)
    assert len(ts) == 1

    ts.add_point("01/01/2024 12:00:05", 45.2)
    assert len(ts) == 2


def test_time_series_data_iteration():
    """Test TimeSeriesData iteration."""
    ts = TimeSeriesData()
    ts.add_point("01/01/2024 12:00:00", 42.5)
    ts.add_point("01/01/2024 12:00:05", 45.2)

    data_points = list(ts)
    assert len(data_points) == 2
    assert data_points[0] == ("01/01/2024 12:00:00", 42.5)
    assert data_points[1] == ("01/01/2024 12:00:05", 45.2)


def test_time_series_data_with_none_values():
    """Test TimeSeriesData handles None values."""
    ts = TimeSeriesData()
    ts.add_point("01/01/2024 12:00:00", 42.5)
    ts.add_point("01/01/2024 12:00:05", None)
    ts.add_point("01/01/2024 12:00:10", 45.2)

    assert len(ts) == 3
    data_points = list(ts)
    assert data_points[1][1] is None


def test_extract_column_data_file_not_found():
    """Test that extract_column_data raises FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        extract_column_data("nonexistent_file.csv", 0)


# TODO: Add tests with actual sample CSV data
# - test_extract_column_data_with_sample_csv()
# - test_save_time_series_to_file()
# - test_extract_and_save_integration()
