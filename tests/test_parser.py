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


# ===========================================================================
# VM VMDK stat category discovery
#
# Discovery is header-driven: every ``Virtual Disk(<vm>[:<scsiC:T>])\<counter>``
# column in the capture becomes a distinct (vm, vmdk, counter) category,
# whatever the counter is named. See tests/conftest.py for the contract and
# the helpers used below.
# ===========================================================================

from tests.conftest import (  # noqa: E402
    NOISE_COLUMNS,
    VMDK_COUNTERS,
    VM_LAYOUT,
    discovery_keys,
    entry_columns,
    entry_key,
    entry_scope,
    get_discovery_function,
    vmdk_column_tails,
    write_csv,
)


def test_discovery_function_exported_from_package():
    """The discovery function is part of the package's public API."""
    import esxtop_visualizer

    discover = get_discovery_function()
    name = discover.__name__

    assert getattr(esxtop_visualizer, name, None) is discover, (
        f"esxtop_visualizer does not re-export parser.{name}"
    )
    assert name in getattr(esxtop_visualizer, "__all__", []), (
        f"{name} missing from esxtop_visualizer.__all__"
    )


def test_discover_vmdk_categories_finds_every_vm_and_vmdk(multi_vm_csv):
    """Every VM and every VMDK in the header is discovered."""
    csv_path, expected = multi_vm_csv
    discover = get_discovery_function()

    entries = discover(str(csv_path))
    keys = discovery_keys(entries)

    assert set(k[0] for k in keys) == set(VM_LAYOUT), "not every VM was discovered"

    for vm, disks in VM_LAYOUT.items():
        found = set(k[1] for k in keys if k[0] == vm and k[1] is not None)
        assert found == set(disks), f"VMDKs discovered for {vm}: {found}"


def test_discover_vmdk_categories_returns_every_category(multi_vm_csv):
    """Every (vm, vmdk, counter) triple in the header is returned exactly once."""
    csv_path, expected = multi_vm_csv
    discover = get_discovery_function()

    keys = discovery_keys(discover(str(csv_path)))

    assert len(keys) == len(set(keys)), "discovery returned duplicate categories"
    assert set(keys) == set(expected)


def test_discover_vmdk_categories_covers_more_than_two_counters(multi_vm_csv):
    """More than the two hardcoded latency counters are reported per VMDK."""
    csv_path, _expected = multi_vm_csv
    discover = get_discovery_function()

    keys = discovery_keys(discover(str(csv_path)))
    counters = set(k[2] for k in keys)

    assert counters == set(VMDK_COUNTERS)
    assert len(counters) > 2

    # Each VMDK carries the full counter set, not just the latency pair.
    for vm, disks in VM_LAYOUT.items():
        for disk in disks:
            per_disk = set(k[2] for k in keys if k[0] == vm and k[1] == disk)
            assert per_disk == set(VMDK_COUNTERS), f"{vm}:{disk} -> {per_disk}"


def test_discover_vmdk_categories_has_no_counter_allowlist(tmp_path):
    """Counters the code has never heard of are discovered all the same."""
    discover = get_discovery_function()

    exotic = [
        "Zzz Made Up Counter/sec",
        "Average MilliSec/Device Write",
        "Queue Depth",
        "% Reserved Slots",
    ]
    tails, expected = vmdk_column_tails(
        layout={"vmX": ["scsi0:0"]}, counters=exotic
    )
    csv_path = write_csv(tmp_path / "exotic.csv", tails)

    keys = discovery_keys(discover(str(csv_path)))

    assert set(keys) == set(expected)
    assert set(k[2] for k in keys) == set(exotic)


def test_discover_vmdk_categories_distinguishes_vm_and_vmdk_scope(multi_vm_csv):
    """VM-level rollups and per-VMDK instances are both found and told apart."""
    csv_path, _expected = multi_vm_csv
    discover = get_discovery_function()

    entries = discover(str(csv_path))

    scopes = set(entry_scope(e) for e in entries)
    assert scopes == {"vm", "vmdk"}

    for entry in entries:
        vm, disk, _counter = entry_key(entry)
        expected_scope = "vm" if disk is None else "vmdk"
        assert entry_scope(entry) == expected_scope, (
            f"entry {entry!r} for vm={vm} disk={disk} has scope "
            f"{entry_scope(entry)!r}"
        )

    rollups = set(
        entry_key(e)[0] for e in entries if entry_scope(e) == "vm"
    )
    assert rollups == set(VM_LAYOUT), "VM-level rollup instances missing"

    per_vmdk = set(
        (entry_key(e)[0], entry_key(e)[1]) for e in entries if entry_scope(e) == "vmdk"
    )
    assert per_vmdk == {
        (vm, disk) for vm, disks in VM_LAYOUT.items() for disk in disks
    }


def test_discover_vmdk_categories_records_column_indices(multi_vm_csv):
    """Each category carries the header column index it was found at."""
    csv_path, _expected = multi_vm_csv
    discover = get_discovery_function()

    header = csv_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    expected_index = {}
    for index, field in enumerate(header):
        field = field.strip('"')
        if "Virtual Disk(" not in field:
            continue
        instance = field.split("Virtual Disk(", 1)[1].split(")", 1)[0]
        counter = field.rsplit("\\", 1)[1]
        vm, _, disk = instance.partition(":")
        expected_index[(vm, disk or None, counter)] = [index]

    entries = discover(str(csv_path))
    assert expected_index, "fixture built no Virtual Disk columns"

    found_index = {entry_key(e): entry_columns(e) for e in entries}
    assert found_index == expected_index


def test_discover_vmdk_categories_groups_repeated_columns(tmp_path):
    """A category appearing at several columns is one entry with both indices."""
    discover = get_discovery_function()

    tails = [
        "Virtual Disk(vm1)\\Commands/sec",
        "Virtual Disk(vm1:scsi0:0)\\Commands/sec",
        "Virtual Disk(vm1:scsi0:0)\\Commands/sec",
    ]
    csv_path = write_csv(tmp_path / "repeated.csv", tails)

    entries = discover(str(csv_path))
    by_key = {entry_key(e): entry_columns(e) for e in entries}

    assert len(entries) == 2, "repeated columns must collapse into one category"
    assert by_key[("vm1", None, "Commands/sec")] == [1]
    assert by_key[("vm1", "scsi0:0", "Commands/sec")] == [2, 3]


def test_discover_vmdk_categories_ignores_non_virtual_disk_columns(tmp_path):
    """Physical disk / CPU / memory columns are not VM VMDK categories."""
    discover = get_discovery_function()

    tails, expected = vmdk_column_tails(
        layout={"vm1": ["scsi0:0"]}, counters=["Average MilliSec/Write"]
    )
    csv_path = write_csv(tmp_path / "mixed.csv", NOISE_COLUMNS + tails)

    keys = discovery_keys(discover(str(csv_path)))

    assert set(keys) == set(expected)


def test_discover_vmdk_categories_empty_without_virtual_disk_columns(no_vmdk_csv):
    """A capture with no Virtual Disk columns discovers nothing."""
    discover = get_discovery_function()

    entries = discover(str(no_vmdk_csv))

    assert list(entries) == []


def test_discover_vmdk_categories_missing_file():
    """A missing CSV raises FileNotFoundError, like parse_csv_header does."""
    discover = get_discovery_function()

    with pytest.raises(FileNotFoundError):
        discover("nonexistent_file.csv")
