"""Shared fixtures for the esxtop_visualizer test-suite.

The helpers here support the ``--list-categories`` CLI tests in
``tests/test_list_categories.py``: they build small PDH-CSV fixtures on disk and
invoke the command-line entry point in a subprocess so stdout and stderr can be
inspected independently.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = REPO_ROOT / "src"

# Primary entry point named by the issue; the sibling script is the documented
# alternative placement for the same flag.
SUMMARIZE_SCRIPT = REPO_ROOT / "scripts" / "summarize_columns.py"
SIBLING_SCRIPT = REPO_ROOT / "scripts" / "list_categories.py"

HOST = "esx01.example.com"


def make_header_column(category: str, counter: str, host: str = HOST) -> str:
    r"""Build a PDH-CSV header cell: ``\\host\category\counter``."""
    return f"\\\\{host}\\{category}\\{counter}"


def write_pdh_csv(path: Path, columns, rows=None) -> Path:
    """Write a minimal PDH-CSV file.

    Args:
        path: Destination file.
        columns: Iterable of ``(category, counter)`` pairs, in the exact order
            they should appear in the header (after the timestamp column).
        rows: Optional list of value rows; one dummy row is written by default.

    Returns:
        The path written, for convenience.
    """
    header = ['"(PDH-CSV 4.0) (UTC)(0)"']
    for category, counter in columns:
        header.append('"' + make_header_column(category, counter) + '"')

    if rows is None:
        rows = [["08/30/2026 10:00:00"] + [str(1.0 + i) for i in range(len(columns))]]

    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join('"' + str(value) + '"' for value in row))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_list_categories(csv_path, *extra_args):
    """Run the CLI with ``--list-categories`` against ``csv_path``.

    Prefers ``scripts/summarize_columns.py --list-categories``. If that script
    does not know the flag yet and the sibling ``scripts/list_categories.py``
    exists, the sibling is used instead (the issue allows either placement).

    Returns:
        The ``subprocess.CompletedProcess`` (text mode).
    """
    def _run(script, args):
        return subprocess.run(
            [sys.executable, str(script), str(csv_path), *args],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )

    result = _run(SUMMARIZE_SCRIPT, ["--list-categories", *extra_args])

    flag_unknown = result.returncode == 2 and "unrecognized arguments" in result.stderr
    if flag_unknown and SIBLING_SCRIPT.exists():
        result = _run(SIBLING_SCRIPT, list(extra_args))

    return result


@pytest.fixture
def pdh_csv(tmp_path):
    """Factory fixture: ``pdh_csv(name, columns)`` -> path to a PDH-CSV file."""
    def _make(name, columns, rows=None):
        return write_pdh_csv(tmp_path / name, columns, rows=rows)

    return _make


@pytest.fixture
def list_categories():
    """Expose :func:`run_list_categories` as a fixture."""
    return run_list_categories
