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


# ---------------------------------------------------------------------------
# Min / max / average statistics helper
#
# The helper is looked up through tests.conftest.get_stats_callable(), which
# accepts any of several plausible names and return shapes; see the contract
# note in tests/conftest.py.
# ---------------------------------------------------------------------------

from tests.conftest import (  # noqa: E402
    expected_stats,
    stats_triple,
    write_stats_csv,
)


def test_series_stats_plain_numeric_series():
    """min, max and average over a series with no missing samples."""
    minimum, maximum, average = stats_triple([4.0, 8.0, 6.0])

    assert minimum == pytest.approx(4.0)
    assert maximum == pytest.approx(8.0)
    assert average == pytest.approx(6.0)


def test_series_stats_excludes_none_samples():
    """[None, 4.0, None, 6.0] -> min 4.0, max 6.0, avg 5.0 (not 2.5, not 0.0)."""
    minimum, maximum, average = stats_triple([None, 4.0, None, 6.0])

    assert minimum == pytest.approx(4.0), (
        f"min is {minimum}; None samples must be skipped, not read as 0.0"
    )
    assert maximum == pytest.approx(6.0)
    assert average == pytest.approx(5.0), (
        f"average is {average}; None samples must be excluded from the sample "
        f"count (5.0), not averaged in as zero (2.5)"
    )


def test_series_stats_single_sample_series():
    """A one-sample series reports that sample as min, max and average."""
    minimum, maximum, average = stats_triple([42.5])

    assert minimum == pytest.approx(42.5)
    assert maximum == pytest.approx(42.5)
    assert average == pytest.approx(42.5)


def test_series_stats_leading_and_trailing_none_do_not_shift_extremes():
    """The extremes come from the numeric samples, wherever they sit."""
    minimum, maximum, average = stats_triple([None, 7.0, 1.0, 9.0, None])

    assert minimum == pytest.approx(1.0)
    assert maximum == pytest.approx(9.0)
    assert average == pytest.approx((7.0 + 1.0 + 9.0) / 3)


def test_series_stats_over_extracted_column_skips_non_numeric_cells(tmp_path):
    """Stats over a series straight out of extract_multiple_columns().

    Blank and non-numeric cells come back as None and must not drag the
    statistics towards zero.
    """
    from esxtop_visualizer.extractor import extract_multiple_columns

    series = [("vm1", "scsi0:1", "Average MilliSec/Write", ["", 4.0, "-", 6.0])]
    csv_path = write_stats_csv(tmp_path / "gaps.csv", series=series, noise=[])

    extracted = extract_multiple_columns(str(csv_path), [1])[1]
    values = [value for _timestamp, value in extracted]
    assert values.count(None) == 2, f"fixture did not produce None samples: {values}"

    minimum, maximum, average = stats_triple(values)

    assert (minimum, maximum, average) == pytest.approx(
        expected_stats(["", 4.0, "-", 6.0])
    )
