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
