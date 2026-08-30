"""Tests for the ``--list-categories`` machine-readable listing.

Expected output contract (see the issue for this feature):

* one line per discovered VM VMDK category, written to **stdout**;
* each line carries exactly three fields in a fixed order --
  ``VM<DELIM>VMDK<DELIM>COUNTER`` -- separated by a single, stable,
  single-character delimiter so ``cut``/``awk``/``grep`` can select any field.
  The VMDK field may be the bare instance (``scsi0:0``) or the full esxtop
  instance (``VM:scsi0:0``); both are accepted here;
* counter names are printed in full, never truncated;
* lines are grouped by VM, then by VMDK, deterministically sorted;
* progress chatter goes to stderr, so stdout is pure data.
"""

import re

import pytest

# Delimiters a machine-readable listing could plausibly use. None of them occur
# inside esxtop VM names, VMDK instances or counter names.
DELIMITER_CANDIDATES = ("\t", "|", ";", ",", "\x1f")

DECORATION_PATTERNS = [
    r"={3,}",                 # banner rules
    r"-{3,}",                 # separator rules
    r"[─-╿]",       # box drawing
    r"[\U0001F300-\U0001FAFF☀-➿]",  # emoji / symbols
    r"\.\.\.",                # truncation ellipsis
]

LONG_COUNTER = "Average MilliSec/Write Per Virtual Disk Operation"

# Two VMs, multiple VMDK instances each, deliberately shuffled so a correct
# implementation cannot rely on column order or dict insertion order.
SAMPLE_COLUMNS = [
    ("Virtual Disk(VMBETA:scsi0:2)", "Reads/sec"),
    ("Virtual Disk(VMALPHA:scsi0:1)", LONG_COUNTER),
    ("Group Cpu(1234:VMALPHA)", "% Ready"),
    ("Virtual Disk(VMALPHA:scsi0:0)", "Writes/sec"),
    ("Virtual Disk(VMBETA:scsi0:0)", "Average MilliSec/Write"),
    ("Physical Disk(naa.60000970000297800param)", "Average MilliSec/Write"),
    ("Virtual Disk(VMALPHA:scsi0:0)", "Average MilliSec/Write"),
    ("Virtual Disk(VMBETA:scsi0:2)", "Average MilliSec/Read"),
    ("Virtual Disk(VMALPHA:scsi0:1)", "Average MilliSec/Read"),
]

# Grouped by VM, then by VMDK, then by counter -- the only ordering that is
# stable across runs and independent of the header layout above.
EXPECTED_ENTRIES = [
    ("VMALPHA", "scsi0:0", "Average MilliSec/Write"),
    ("VMALPHA", "scsi0:0", "Writes/sec"),
    ("VMALPHA", "scsi0:1", "Average MilliSec/Read"),
    ("VMALPHA", "scsi0:1", LONG_COUNTER),
    ("VMBETA", "scsi0:0", "Average MilliSec/Write"),
    ("VMBETA", "scsi0:2", "Average MilliSec/Read"),
    ("VMBETA", "scsi0:2", "Reads/sec"),
]

NO_VDISK_COLUMNS = [
    ("Group Cpu(1234:VMALPHA)", "% Ready"),
    ("Physical Disk(naa.60000970000297800param)", "Average MilliSec/Write"),
    ("Memory", "Machine MBytes"),
]


def stdout_lines(result):
    """Return stdout split into lines, keeping empty lines visible."""
    return result.stdout.split("\n")[:-1] if result.stdout.endswith("\n") else result.stdout.split("\n")


def detect_delimiter(lines):
    """Return the single-character delimiter that splits every line in 3."""
    for delimiter in DELIMITER_CANDIDATES:
        if lines and all(len(line.split(delimiter)) == 3 for line in lines):
            return delimiter
    return None


def parse_entries(result):
    """Parse stdout into normalized ``(vm, vmdk, counter)`` tuples."""
    lines = stdout_lines(result)
    delimiter = detect_delimiter(lines)
    assert delimiter is not None, (
        "expected every line to split into exactly 3 fields on one stable "
        f"delimiter, got:\n{result.stdout!r}"
    )

    entries = []
    for line in lines:
        vm, vmdk, counter = (field.strip() for field in line.split(delimiter))
        # Accept either the bare instance or the full "VM:scsi0:0" instance.
        if vmdk.startswith(f"{vm}:"):
            vmdk = vmdk[len(vm) + 1:]
        entries.append((vm, vmdk, counter))
    return entries


@pytest.fixture
def sample_csv(pdh_csv):
    return pdh_csv("sample.csv", SAMPLE_COLUMNS)


def test_list_categories_exits_zero_and_lists_one_category_per_line(sample_csv, list_categories):
    """Exit code 0 and one VMDK category per stdout line."""
    result = list_categories(sample_csv)

    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    assert stdout_lines(result), f"no category lines on stdout:\n{result.stdout!r}"
    assert len(stdout_lines(result)) == len(EXPECTED_ENTRIES)


def test_list_categories_emits_exact_lines_in_deterministic_order(sample_csv, list_categories):
    """The exact expected line set, grouped by VM then VMDK, in order."""
    result = list_categories(sample_csv)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    assert parse_entries(result) == EXPECTED_ENTRIES


def test_list_categories_fields_are_selectable_by_cut(sample_csv, list_categories):
    """A single stable delimiter, three fields, no delimiter inside a field."""
    result = list_categories(sample_csv)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    lines = stdout_lines(result)
    delimiter = detect_delimiter(lines)
    assert delimiter is not None, f"no single stable delimiter in:\n{result.stdout!r}"
    assert len(delimiter) == 1, "delimiter must be a single character for cut -d"

    # Field 1 selects VMs, field 3 selects counters -- as `cut -f1` / `-f3` would.
    first_fields = [line.split(delimiter)[0].strip() for line in lines]
    third_fields = [line.split(delimiter)[2].strip() for line in lines]
    assert set(first_fields) == {"VMALPHA", "VMBETA"}
    assert set(third_fields) == {counter for _, _, counter in EXPECTED_ENTRIES}


def test_list_categories_counter_names_are_not_truncated(sample_csv, list_categories):
    """Long counter names are printed in full, with no ellipsis."""
    result = list_categories(sample_csv)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    assert LONG_COUNTER in result.stdout
    assert "..." not in result.stdout
    counters = [counter for _, _, counter in parse_entries(result)]
    assert LONG_COUNTER in counters


def test_list_categories_output_has_no_decoration(sample_csv, list_categories):
    """No banners, separators, emoji or blank decorative lines on stdout."""
    result = list_categories(sample_csv)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    for pattern in DECORATION_PATTERNS:
        assert not re.search(pattern, result.stdout), (
            f"decoration matching {pattern!r} found in stdout:\n{result.stdout!r}"
        )
    assert "" not in stdout_lines(result), "blank line in listing"
    for banner in ("COLUMN SUMMARY", "TOP ", "TOTALS", "CATEGORIES:", "COUNTERS:"):
        assert banner not in result.stdout


def test_list_categories_excludes_non_vmdk_columns(sample_csv, list_categories):
    """Group Cpu / Physical Disk / timestamp columns are not listed."""
    result = list_categories(sample_csv)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    assert "Group Cpu" not in result.stdout
    assert "% Ready" not in result.stdout
    assert "Physical Disk" not in result.stdout
    assert "naa." not in result.stdout
    assert "PDH-CSV" not in result.stdout


def test_list_categories_is_independent_of_column_order(pdh_csv, list_categories):
    """Same categories in a different header order produce identical stdout."""
    forward = pdh_csv("forward.csv", SAMPLE_COLUMNS)
    reversed_csv = pdh_csv("reversed.csv", list(reversed(SAMPLE_COLUMNS)))

    first = list_categories(forward)
    second = list_categories(reversed_csv)

    assert first.returncode == 0, f"stderr:\n{first.stderr}"
    assert second.returncode == 0, f"stderr:\n{second.stderr}"
    assert first.stdout == second.stdout
    assert parse_entries(first) == EXPECTED_ENTRIES


def test_list_categories_is_stable_across_runs(sample_csv, list_categories):
    """Repeated runs on the same input yield byte-identical stdout."""
    runs = [list_categories(sample_csv) for _ in range(3)]

    for run in runs:
        assert run.returncode == 0, f"stderr:\n{run.stderr}"
    assert len({run.stdout for run in runs}) == 1


def test_list_categories_progress_chatter_goes_to_stderr(sample_csv, list_categories):
    """`--list-categories > out.txt` yields only category lines."""
    result = list_categories(sample_csv)
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    assert "Analyzing" not in result.stdout
    assert str(sample_csv) not in result.stdout
    assert parse_entries(result) == EXPECTED_ENTRIES


def test_list_categories_without_virtual_disk_columns_prints_nothing(pdh_csv, list_categories):
    """A CSV with no Virtual Disk columns exits 0 with empty stdout."""
    csv_path = pdh_csv("no_vdisk.csv", NO_VDISK_COLUMNS)

    result = list_categories(csv_path)

    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    assert result.stdout == "" or result.stdout == "\n", (
        f"expected no stdout for a CSV without Virtual Disk columns, got {result.stdout!r}"
    )
