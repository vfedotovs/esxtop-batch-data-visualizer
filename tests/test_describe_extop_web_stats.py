"""
Min / max / average in the container's text report (scripts/describe_extop_web.sh).

The report must print a MIN value next to MAX and AVG, for every selected VMDK
category (VM/VMDK plus counter name), with the three statistics computed over
the numeric samples only.

``run_describe`` executes the same script, with the same argument, that the
container runs through ``run_describe_script()`` in ``app.py``; the CSV it is
pointed at stands in for the host-mounted capture.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tests.conftest import (  # noqa: E402
    STATS_SERIES,
    expected_stats,
    stats_instance,
)

ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# A printed statistic: a decimal number. Column indices and sample counts are
# plain integers and are deliberately not matched.
NUMBER = re.compile(r"-?\d+\.\d+")

COUNTERS = [counter for _vm, _vmdk, counter, _samples in STATS_SERIES]
INSTANCES = {stats_instance(vm, vmdk) for vm, vmdk, _c, _s in STATS_SERIES}

TOLERANCE = 1e-3


def clean_output(proc):
    return ANSI.sub("", proc.stdout + proc.stderr)


def index_rows(output):
    """Map ``(instance, counter)`` -> the report line(s) reporting on it.

    A row is a line that names a known VMDK instance as a whitespace-separated
    token and carries statistics. The counter is read from the row itself if it
    is named there, otherwise from the nearest preceding line that names one --
    so both a table-per-counter layout and a single table with a counter column
    are read the same way.
    """
    rows = {}
    section = None

    for line in output.splitlines():
        instance = next((t for t in line.split() if t in INSTANCES), None)
        if instance is not None and len(NUMBER.findall(line)) >= 2:
            counter = next((c for c in COUNTERS if c in line), section)
            rows.setdefault((instance, counter), []).append(line)
            continue

        named = next((c for c in COUNTERS if c in line), None)
        if named is not None:
            section = named

    return rows


def row_for(rows, vm, vmdk, counter):
    instance = stats_instance(vm, vmdk)
    lines = rows.get((instance, counter))
    assert lines, (
        f"no report row for VMDK category {instance!r} / {counter!r}; "
        f"reported rows: {sorted(rows)}"
    )
    assert len(lines) == 1, (
        f"VMDK category {instance!r} / {counter!r} is reported "
        f"{len(lines)} times:\n" + "\n".join(lines)
    )
    return lines[0]


def stat_spans(line, samples):
    """Map "min"/"max"/"avg" -> the (start, end) span of its token in ``line``.

    Statistics are located by value: every fixture series has three distinct
    statistics, so a row printing only two of them cannot match all three.
    """
    tokens = [(m.group(0), m.span()) for m in NUMBER.finditer(line)]
    spans = {}
    for name, value in zip(("min", "max", "avg"), expected_stats(samples)):
        for text, span in tokens:
            if abs(float(text) - value) < TOLERANCE:
                spans[name] = (text, span)
                break
    return spans


@pytest.fixture
def report(stats_csv, run_describe):
    csv_path, _series = stats_csv
    proc = run_describe(csv_path)
    output = clean_output(proc)
    assert proc.returncode == 0, output
    return output


def test_report_header_labels_min_next_to_max_and_avg(report):
    """The table header gains a MIN column alongside AVG and MAX."""
    headers = [
        line for line in report.splitlines()
        if re.search(r"\bAVG\b", line) and re.search(r"\bMAX\b", line)
    ]
    assert headers, "no AVG/MAX table header found in the report:\n" + report

    without_min = [line for line in headers if not re.search(r"\bMIN\b", line)]
    assert not without_min, (
        "table header prints MAX and AVG but no MIN: " + repr(without_min)
    )


def test_report_prints_min_max_and_average_for_every_category(report):
    """Every selected category gets a row carrying all three statistics."""
    rows = index_rows(report)

    for vm, vmdk, counter, samples in STATS_SERIES:
        line = row_for(rows, vm, vmdk, counter)
        numbers = NUMBER.findall(line)
        assert len(numbers) >= 3, (
            f"row for {stats_instance(vm, vmdk)!r} / {counter!r} carries "
            f"{len(numbers)} numeric values {numbers}; expected at least three "
            f"(min, max and average):\n{line}"
        )


def test_report_values_match_the_csv_columns(report):
    """The printed statistics equal those computed from the same CSV columns."""
    rows = index_rows(report)

    for vm, vmdk, counter, samples in STATS_SERIES:
        line = row_for(rows, vm, vmdk, counter)
        numbers = [float(n) for n in NUMBER.findall(line)]
        for name, value in zip(("min", "max", "avg"), expected_stats(samples)):
            assert any(abs(n - value) < TOLERANCE for n in numbers), (
                f"{name} of {stats_instance(vm, vmdk)!r} / {counter!r} is "
                f"{value} over samples {samples}, but the row prints "
                f"{numbers}:\n{line}"
            )


def test_report_excludes_none_samples_from_the_statistics(report):
    """A column with blank/non-numeric cells reports 4.0 / 6.0 / 5.0."""
    vm, vmdk, counter, samples = ("vm1", "scsi0:1", "Average MilliSec/Write",
                                  ["", 4.0, "-", 6.0])
    assert (vm, vmdk, counter, samples) in [
        (v, d, c, s) for v, d, c, s in STATS_SERIES
    ], "fixture series changed"

    line = row_for(index_rows(report), vm, vmdk, counter)
    numbers = [float(n) for n in NUMBER.findall(line)]

    for value in (4.0, 6.0, 5.0):
        assert any(abs(n - value) < TOLERANCE for n in numbers), (
            f"{value} missing from the row for a series with missing samples; "
            f"row prints {numbers}:\n{line}"
        )
    for bogus in (0.0, 2.5):
        assert not any(abs(n - bogus) < TOLERANCE for n in numbers), (
            f"{bogus} printed for {vmdk!r}: missing samples were counted as "
            f"zero instead of being skipped:\n{line}"
        )


def test_report_min_max_and_average_share_formatting_and_alignment(report):
    """All three statistics use the table's numeric format and column layout."""
    rows = index_rows(report)
    spans_by_counter = {}

    for vm, vmdk, counter, samples in STATS_SERIES:
        line = row_for(rows, vm, vmdk, counter)
        spans = stat_spans(line, samples)

        missing = [n for n in ("min", "max", "avg") if n not in spans]
        assert not missing, (
            f"row for {stats_instance(vm, vmdk)!r} / {counter!r} does not print "
            f"{missing} (expected {expected_stats(samples)}):\n{line}"
        )

        decimals = {len(text.split(".")[1]) for text, _span in spans.values()}
        assert len(decimals) == 1, (
            f"min, max and average use different numeric formats "
            f"{[t for t, _s in spans.values()]}:\n{line}"
        )

        columns = {name: span for name, (_text, span) in spans.items()}
        first_vm, first_columns, first_line = spans_by_counter.setdefault(
            counter, (stats_instance(vm, vmdk), columns, line)
        )
        for name, span in columns.items():
            assert span[0] == first_columns[name][0] or \
                span[1] == first_columns[name][1], (
                f"the {name.upper()} column is not aligned between rows "
                f"{first_vm!r} and {stats_instance(vm, vmdk)!r} of table "
                f"{counter!r}:\n{first_line}\n{line}"
            )
