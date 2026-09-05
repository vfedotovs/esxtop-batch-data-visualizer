"""
Shared fixtures and helpers for the esxtop_visualizer test suite.

Most of what lives here supports the VM VMDK stat-category discovery tests
(``tests/test_parser.py``) and the container report tests
(``tests/test_describe_extop_web.py``).

Discovery contract exercised by those tests
-------------------------------------------
``esxtop_visualizer.parser`` exposes a discovery function -- canonically
``discover_vmdk_categories(filename)`` -- that reads only the CSV header and
returns one entry per *distinct* VM VMDK stat category, i.e. per
``(vm, vmdk instance, counter)`` triple found in a ``Virtual Disk(...)``
column. Each entry carries:

    vm       - the VM name ("vm1")
    vmdk     - the VMDK instance; either the full header instance
               ("vm1:scsi0:0") or just the disk part ("scsi0:0"). For a
               VM-level rollup column -- ``Virtual Disk(vm1)`` -- the VMDK is
               empty/None (or simply repeats the VM name).
    scope    - "vmdk" for a per-VMDK instance, "vm" for a VM-level rollup,
               matching the SCOPE column of the report table
               (scripts/describe_extop_web.sh:34)
    counter  - the counter name ("Average MilliSec/Write", "Commands/sec", ...)
    columns  - the zero-based column indices the category was found at

Entries may be plain objects (dataclass/namedtuple) or mappings; the helpers
below read either, and tolerate the field-name variations listed in
``_FIELD_ALIASES``.
"""

import shutil
import sys
from pathlib import Path

import pytest

# Add src to path for testing
SRC_PATH = Path(__file__).parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

REPO_ROOT = Path(__file__).parent.parent
DESCRIBE_SCRIPT = REPO_ROOT / "scripts" / "describe_extop_web.sh"

HOST = "esx01.example.com"

# Candidate names for the discovery function, most canonical first.
DISCOVERY_FUNCTION_NAMES = (
    "discover_vmdk_categories",
    "discover_vm_vmdk_categories",
    "discover_vmdk_stat_categories",
    "discover_vmdk_stats",
    "find_vmdk_categories",
)

_FIELD_ALIASES = {
    "vm": ("vm", "vm_name", "virtual_machine"),
    "vmdk": ("vmdk", "vmdk_instance", "instance", "disk", "vmdk_name"),
    "counter": ("counter", "counter_name", "stat_name", "stat"),
    "scope": ("scope", "level", "kind"),
    "columns": ("columns", "column_indices", "column_indexes", "indices", "column_ids"),
}


# --------------------------------------------------------------------------
# CSV fixture building
# --------------------------------------------------------------------------

def make_header(column_tails, host=HOST):
    """Build a PDH-CSV header row from ``\\category\\counter`` tails."""
    fields = ['"(PDH-CSV 4.0) (UTC)(0)"']
    for tail in column_tails:
        fields.append('"\\\\{host}\\{tail}"'.format(host=host, tail=tail))
    return ",".join(fields)


def write_csv(path, column_tails, rows=3, host=HOST):
    """Write a small esxtop-style PDH-CSV capture and return its path.

    Values are deterministic: the value in data row ``r`` of the column at
    header position ``i`` (1-based, since column 0 is the timestamp) is
    ``i + r``.
    """
    lines = [make_header(column_tails, host=host)]
    for r in range(rows):
        timestamp = '"10/03/2025 12:%02d:00"' % r
        values = ['"%.2f"' % (i + r) for i in range(1, len(column_tails) + 1)]
        lines.append(",".join([timestamp] + values))
    path = Path(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# A capture with several VMs, several VMDKs per VM and more than two counters
# per VMDK -- the shape tests/test_parser.py is required to cover.
VM_LAYOUT = {
    "vm1": ["scsi0:0", "scsi0:1"],
    "vm2": ["scsi0:0", "scsi1:3"],
    "prod-db-01": ["scsi0:0"],
}

# Deliberately more than the two latency counters the old report hardcoded,
# including counters no allowlist would know about.
VMDK_COUNTERS = [
    "Average MilliSec/Write",
    "Average MilliSec/Read",
    "Commands/sec",
    "Reads/sec",
    "MBWritten/sec",
    "Average Outstanding IO",
]

# Non-VMDK noise, including a Physical Disk column that carries one of the
# latency counter names, so discovery cannot get away with matching on the
# counter alone.
NOISE_COLUMNS = [
    "Physical Disk(naa.60000000000000000)\\Average MilliSec/Write",
    "Physical Cpu(_Total)\\% Util Time",
    "Group Cpu(1234:vm1)\\% Ready",
    "Memory\\Machine MBytes",
]


def vmdk_column_tails(layout=None, counters=None):
    """Return (column tails, expected (vm, disk, counter) keys).

    ``disk`` is ``None`` for a VM-level rollup instance.
    """
    layout = VM_LAYOUT if layout is None else layout
    counters = VMDK_COUNTERS if counters is None else counters

    tails = []
    expected = []
    for vm, disks in layout.items():
        for instance, disk in [(vm, None)] + [("%s:%s" % (vm, d), d) for d in disks]:
            for counter in counters:
                tails.append("Virtual Disk(%s)\\%s" % (instance, counter))
                expected.append((vm, disk, counter))
    return tails, expected


@pytest.fixture
def multi_vm_csv(tmp_path):
    """A capture with 3 VMs, 5 VMDKs and 6 counters per instance, plus noise."""
    tails, expected = vmdk_column_tails()
    path = write_csv(tmp_path / "multi_vm.csv", tails + NOISE_COLUMNS)
    return path, expected


@pytest.fixture
def no_vmdk_csv(tmp_path):
    """A valid capture that contains no ``Virtual Disk`` columns at all."""
    return write_csv(tmp_path / "no_vmdk.csv", NOISE_COLUMNS)


# --------------------------------------------------------------------------
# Discovery helpers
# --------------------------------------------------------------------------

def get_discovery_function():
    """Return the parser's VMDK category discovery function.

    Fails the calling test (rather than erroring at import time) while the
    function does not exist yet.
    """
    from esxtop_visualizer import parser

    for name in DISCOVERY_FUNCTION_NAMES:
        func = getattr(parser, name, None)
        if callable(func):
            return func

    pytest.fail(
        "esxtop_visualizer.parser has no VM VMDK category discovery function; "
        "expected one of: %s" % ", ".join(DISCOVERY_FUNCTION_NAMES)
    )


def _field(entry, field):
    """Read ``field`` from a discovery entry (mapping or object)."""
    aliases = _FIELD_ALIASES[field]
    if hasattr(entry, "keys"):
        for alias in aliases:
            if alias in entry:
                return entry[alias]
    else:
        for alias in aliases:
            if hasattr(entry, alias):
                return getattr(entry, alias)
    pytest.fail(
        "discovery entry %r carries no %r field (tried %s)"
        % (entry, field, ", ".join(aliases))
    )


def entry_scope(entry):
    """Normalised scope label of a discovery entry: "vm" or "vmdk"."""
    return str(_field(entry, "scope")).strip().lower()


def entry_columns(entry):
    """Sorted list of zero-based column indices of a discovery entry."""
    value = _field(entry, "columns")
    if isinstance(value, int):
        value = [value]
    try:
        return sorted(int(v) for v in value)
    except (TypeError, ValueError):
        pytest.fail("discovery entry %r has non-integer column indices: %r" % (entry, value))


def entry_key(entry):
    """Return the ``(vm, disk, counter)`` identity of a discovery entry.

    ``disk`` is ``None`` for VM-level rollups. The VMDK field is accepted
    either as the full header instance ("vm1:scsi0:0") or as the bare disk
    ("scsi0:0").
    """
    vm = str(_field(entry, "vm")).strip()
    counter = str(_field(entry, "counter")).strip()

    raw = _field(entry, "vmdk")
    disk = None if raw is None else str(raw).strip()
    if not disk or disk == vm:
        disk = None
    elif disk.startswith(vm + ":"):
        disk = disk[len(vm) + 1:]

    return (vm, disk, counter)


def discovery_keys(entries):
    return [entry_key(e) for e in entries]


# --------------------------------------------------------------------------
# Container report helpers
# --------------------------------------------------------------------------

@pytest.fixture
def run_describe(tmp_path):
    """Run scripts/describe_extop_web.sh on a CSV inside an isolated cwd."""
    import subprocess

    def _run(csv_path, cwd=None):
        bash = shutil.which("bash")
        if bash is None:  # pragma: no cover - linux CI always has bash
            pytest.skip("bash is required to run describe_extop_web.sh")
        workdir = Path(cwd) if cwd else tmp_path / "run"
        workdir.mkdir(parents=True, exist_ok=True)
        return subprocess.run(
            [bash, str(DESCRIBE_SCRIPT), str(csv_path)],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=300,
        )

    return _run


# --------------------------------------------------------------------------
# Min / max / average statistics helpers
# --------------------------------------------------------------------------
#
# Contract exercised by the statistics tests
# ------------------------------------------
# ``esxtop_visualizer.extractor`` exposes a reusable helper that computes the
# minimum, maximum and average of a ``TimeSeriesData`` series -- canonically
# ``series_stats(series)``. ``None`` samples (non-numeric or missing cells, as
# produced by ``extract_multiple_columns``) are excluded from all three
# statistics rather than counted as zero.
#
# The helper may be a module-level function or a method on ``TimeSeriesData``,
# and may return a mapping, an object with ``min``/``max``/``avg`` style
# attributes, or a ``(min, max, avg)`` tuple; ``stats_triple`` reads any of
# those, tolerating the field-name variations in ``_STAT_ALIASES``.

# Candidate names for a module-level stats helper, most canonical first.
STATS_FUNCTION_NAMES = (
    "series_stats",
    "compute_series_stats",
    "calculate_series_stats",
    "series_statistics",
    "compute_stats",
    "calculate_stats",
    "compute_statistics",
    "calculate_statistics",
    "summarize_series",
    "summarise_series",
    "summarize_time_series",
    "time_series_stats",
    "min_max_avg",
    "min_max_average",
    "compute_min_max_avg",
    "compute_min_max_average",
)

# Candidate names for the same helper exposed as a TimeSeriesData method.
STATS_METHOD_NAMES = (
    "stats",
    "statistics",
    "series_stats",
    "compute_stats",
    "summary",
    "summarize",
    "min_max_avg",
)

_STAT_ALIASES = {
    "min": ("min", "minimum", "min_value", "minimum_value", "min_val"),
    "max": ("max", "maximum", "max_value", "maximum_value", "max_val"),
    "avg": ("avg", "average", "mean", "avg_value", "average_value", "avg_val"),
}


def make_series(values):
    """Build a TimeSeriesData from ``values`` (floats and/or ``None``)."""
    from esxtop_visualizer.extractor import TimeSeriesData

    series = TimeSeriesData()
    for i, value in enumerate(values):
        series.add_point("10/03/2025 12:%02d:00" % i, value)
    return series


def get_stats_callable():
    """Return ``(callable, label)`` for the min/max/average helper.

    Fails the calling test (rather than erroring at import time) while no such
    helper exists.
    """
    from esxtop_visualizer import extractor

    for name in STATS_FUNCTION_NAMES:
        func = getattr(extractor, name, None)
        if callable(func):
            return func, "esxtop_visualizer.extractor.%s()" % name

    for name in STATS_METHOD_NAMES:
        method = getattr(extractor.TimeSeriesData, name, None)
        if callable(method):
            return (lambda series, _m=name: getattr(series, _m)()), \
                "TimeSeriesData.%s()" % name

    pytest.fail(
        "esxtop_visualizer.extractor has no reusable min/max/average helper; "
        "expected a function named one of: %s (or a TimeSeriesData method "
        "named one of: %s)"
        % (", ".join(STATS_FUNCTION_NAMES), ", ".join(STATS_METHOD_NAMES))
    )


def _stat_field(result, field):
    """Read ``field`` from a stats result (mapping, object or triple)."""
    aliases = _STAT_ALIASES[field]

    if hasattr(result, "keys"):
        for alias in aliases:
            if alias in result:
                return result[alias]
    else:
        for alias in aliases:
            value = getattr(result, alias, None)
            if value is not None and not callable(value):
                return value
        # Plain (min, max, avg) sequence.
        if isinstance(result, (tuple, list)) and len(result) == 3:
            return result[("min", "max", "avg").index(field)]

    pytest.fail(
        "stats result %r carries no %r value (tried %s, and a (min, max, avg) "
        "sequence)" % (result, field, ", ".join(aliases))
    )


def stats_triple(values):
    """Run the stats helper over ``values`` and return ``(min, max, avg)``.

    Accepts a helper taking a ``TimeSeriesData``; falls back to one taking a
    plain sequence of samples.
    """
    func, label = get_stats_callable()
    series = make_series(values)

    try:
        result = func(series)
    except Exception as series_error:  # noqa: BLE001 - reported via pytest.fail
        try:
            result = func(list(values))
        except Exception:  # noqa: BLE001
            pytest.fail(
                "%s raised %r on a TimeSeriesData of %r"
                % (label, series_error, list(values))
            )

    return tuple(float(_stat_field(result, f)) for f in ("min", "max", "avg"))


def expected_stats(samples):
    """Reference (min, max, avg) over the numeric entries of ``samples``."""
    numeric = [float(v) for v in samples if isinstance(v, (int, float))]
    assert numeric, "fixture series %r has no numeric samples" % (samples,)
    return min(numeric), max(numeric), sum(numeric) / len(numeric)


# --------------------------------------------------------------------------
# A capture with hand-picked values, for checking reported statistics
# --------------------------------------------------------------------------
#
# (vm, vmdk, counter, samples). Every series has a distinct min, max and
# average, so a row that prints only two of the three cannot pass by accident.
# Empty and non-numeric cells stand in for the ``None`` samples
# ``extract_multiple_columns`` yields.
STATS_SERIES = [
    ("vm1", "", "Average MilliSec/Write", [1.0, 2.0, 3.0, 10.0]),
    ("vm1", "scsi0:0", "Average MilliSec/Write", [5.0, 1.5, 9.5, 3.0]),
    ("vm1", "scsi0:1", "Average MilliSec/Write", ["", 4.0, "-", 6.0]),
    ("vm2", "scsi0:0", "Average MilliSec/Write", [2.25, 8.75, 0.5, 4.5]),
    ("vm1", "scsi0:0", "Commands/sec", [10.0, 30.0, 20.0, 60.0]),
    ("vm2", "scsi0:0", "Commands/sec", [0.5, 2.5, 1.5, 3.5]),
]

# Same counter name on a physical disk: it must not be reported as a VMDK, and
# its values must not leak into any VMDK row.
STATS_NOISE_SERIES = [
    ("Physical Disk(naa.60000000000000000)\\Average MilliSec/Write",
     [99.0, 99.0, 99.0, 99.0]),
    ("Memory\\Machine MBytes", [4096.0, 4096.0, 4096.0, 4096.0]),
]


def stats_instance(vm, vmdk):
    """Header instance string: "vm1:scsi0:0", or "vm1" for a VM rollup."""
    return "%s:%s" % (vm, vmdk) if vmdk else vm


def write_stats_csv(path, series=None, noise=None, host=HOST):
    """Write a capture whose columns carry the values in ``STATS_SERIES``."""
    series = STATS_SERIES if series is None else series
    noise = STATS_NOISE_SERIES if noise is None else noise

    tails = ["Virtual Disk(%s)\\%s" % (stats_instance(vm, vmdk), counter)
             for vm, vmdk, counter, _samples in series]
    tails += [tail for tail, _samples in noise]
    columns = [samples for _vm, _vmdk, _counter, samples in series]
    columns += [samples for _tail, samples in noise]

    row_count = len(columns[0])
    lines = [make_header(tails, host=host)]
    for r in range(row_count):
        cells = ['"10/03/2025 12:%02d:00"' % r]
        cells += ['"%s"' % column[r] for column in columns]
        lines.append(",".join(cells))

    path = Path(path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def stats_csv(tmp_path):
    """(csv path, STATS_SERIES) for a capture with known per-column values."""
    return write_stats_csv(tmp_path / "stats.csv"), STATS_SERIES
