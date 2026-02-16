"""
Tests for esxtop_visualizer.visualizer module.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for testing
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.visualizer import (
    load_data_file,
    generate_title,
    generate_output_filename,
    plot_time_series,
)


def test_generate_title_with_column_pattern():
    """Test title generation from filename with col_NNN pattern."""
    title = generate_title("col_123.data")
    assert "Column 123" in title
    assert "Over Time" in title


def test_generate_title_without_pattern():
    """Test title generation from filename without col_NNN pattern."""
    title = generate_title("my_data_file.data")
    assert "my_data_file.data" in title


def test_generate_output_filename_with_column_pattern():
    """Test output filename generation from col_NNN pattern."""
    filename = generate_output_filename("col_456.data")
    assert filename == "esxtop_col_456.png"


def test_generate_output_filename_without_pattern():
    """Test output filename generation without col_NNN pattern."""
    filename = generate_output_filename("my_data.data")
    assert filename == "my_data.png"


def test_load_data_file_not_found():
    """Test that load_data_file raises FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        load_data_file("nonexistent_file.data")


# TODO: Add tests with actual sample data files
# - test_load_data_file_with_sample_data()
# - test_load_data_file_with_scaling()
# - test_plot_time_series_basic()
# - test_plot_time_series_empty_data()
