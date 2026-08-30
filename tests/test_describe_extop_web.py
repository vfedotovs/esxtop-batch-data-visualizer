"""
Tests for the container's text report: scripts/describe_extop_web.sh.

The report must be driven by the VM VMDK stat categories discovered in the
loaded CSV header, not by the two hardcoded
``grep -E "\\Average MilliSec/(Write|Read)"`` pipelines it used to run.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tests.conftest import (  # noqa: E402
    DESCRIBE_SCRIPT,
    NOISE_COLUMNS,
    VMDK_COUNTERS,
    VM_LAYOUT,
    write_csv,
)

# The two literal pipelines this change removes
# (scripts/describe_extop_web.sh:179 and :252).
HARDCODED_GREP = re.compile(r"grep\s+-E\s+[\"']?\\?Average MilliSec/(Write|Read)")

BASH_ERROR = re.compile(
    r"(command not found|unary operator expected|syntax error|"
    r"No such file or directory|bad array subscript|Usage: extract_columns_batch)",
    re.IGNORECASE,
)


def all_output(proc):
    return proc.stdout + proc.stderr


def test_describe_script_has_no_hardcoded_counter_greps():
    """The counter set comes from discovery, not from two literal greps."""
    source = DESCRIBE_SCRIPT.read_text(encoding="utf-8")

    matches = HARDCODED_GREP.findall(source)

    assert not matches, (
        "scripts/describe_extop_web.sh still selects counters with hardcoded "
        f"'Average MilliSec/...' greps: {matches}"
    )


def test_report_covers_every_discovered_counter(multi_vm_csv, run_describe):
    """A CSV with N distinct VMDK counters is reported on for all N."""
    csv_path, _expected = multi_vm_csv

    proc = run_describe(csv_path)
    output = all_output(proc)

    assert proc.returncode == 0, output

    missing = [c for c in VMDK_COUNTERS if c not in output]
    assert not missing, (
        f"report covers {len(VMDK_COUNTERS) - len(missing)} of "
        f"{len(VMDK_COUNTERS)} discovered counters; missing: {missing}"
    )


def test_report_covers_every_vmdk_for_every_counter(multi_vm_csv, run_describe):
    """Every VM and VMDK is reported once per discovered counter."""
    csv_path, _expected = multi_vm_csv

    proc = run_describe(csv_path)
    output = all_output(proc)

    assert proc.returncode == 0, output

    expected_reports = len(VMDK_COUNTERS)
    for vm, disks in VM_LAYOUT.items():
        for disk in disks:
            instance = f"{vm}:{disk}"
            # One line per counter in the report body, plus the single
            # "VIRTUAL DISKS PER VM" listing line near the top.
            count = output.count(instance)
            assert count >= expected_reports, (
                f"{instance} appears {count} times in the report; expected at "
                f"least one row per counter ({expected_reports})"
            )


def test_report_without_virtual_disk_columns_says_so(no_vmdk_csv, run_describe):
    """No VMDK categories -> an explicit message, not an empty table."""
    proc = run_describe(no_vmdk_csv)
    output = all_output(proc)

    assert proc.returncode == 0, output
    assert "no vm vmdk categories found" in output.lower(), output

    # The physical-disk column carrying "Average MilliSec/Write" must not be
    # mistaken for a VMDK, and no empty latency table may be printed.
    assert "unknown_vmdk" not in output, output
    assert not BASH_ERROR.search(proc.stderr), proc.stderr
    assert not re.search(r"SCOPE\s+VMDK", output), (
        "an empty latency table was printed instead of the message:\n" + output
    )
