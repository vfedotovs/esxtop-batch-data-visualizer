"""
Tests for esxtop_visualizer.parser module.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for testing
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from esxtop_visualizer.parser import (
    ColumnMetadata,
    parse_csv_header,
    find_columns_by_pattern,
    print_column_info,
)


def test_column_metadata_creation():
    """Test ColumnMetadata dataclass creation."""
    col = ColumnMetadata(
        index=0,
        host="esx01.example.com",
        category="Virtual Disk",
        counter="Average MilliSec/Write",
        original="\\\\esx01.example.com\\Virtual Disk(scsi0:0)\\Average MilliSec/Write"
    )

    assert col.index == 0
    assert col.host == "esx01.example.com"
    assert col.category == "Virtual Disk"
    assert "Column 0" in str(col)


def test_column_metadata_pattern_matching():
    """Test pattern matching on column metadata."""
    col = ColumnMetadata(
        index=5,
        host="esx01.example.com",
        category="Virtual Disk",
        counter="Average MilliSec/Write",
        original="\\\\esx01.example.com\\Virtual Disk(scsi0:0)\\Average MilliSec/Write"
    )

    assert col.matches_pattern(r"scsi.*Write")
    assert col.matches_pattern(r"Average.*Write")
    assert not col.matches_pattern(r"Read")


def test_parse_csv_header_file_not_found():
    """Test that parse_csv_header raises FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        parse_csv_header("nonexistent_file.csv")


# TODO: Add tests with actual sample CSV data
# - test_parse_csv_header_with_sample_data()
# - test_find_columns_by_pattern_with_sample_data()
# - test_print_column_info_output()
