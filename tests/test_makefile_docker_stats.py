"""Tests for the ``make`` target that runs the container's text-stats report.

The target must analyse a CSV that lives on the *host* by bind-mounting it
read-only into the container -- no copy into the image, no upload through the
Flask UI, and no host-side ``.venv``/matplotlib install.

``docker`` is replaced by a recording stub (see
``tests/makefile_helpers.py``), so these tests never contact a daemon; they
assert on how the target invokes it and on what the invocation prints.
"""

import re
from pathlib import Path

import pytest

from tests.conftest import vmdk_column_tails, write_csv
from tests.makefile_helpers import (
    COMPOSE_FILE,
    DEFAULT_CSV_NAME,
    MAKEFILE,
    README,
    REPO_ROOT,
    STUB_REPORT_MARKER,
    Makefile,
    compose_readonly_bind,
    compose_used,
    csv_mounts,
    docker_invocations,
    docker_stub_dir,
    get_docker_stats_target,
    mentions_csv,
    run_make,
    stub_env,
)

# ``docker build`` / ``docker compose build`` / ``docker pull`` / ``up --build``
BUILD_OR_PULL = re.compile(
    r"docker(-compose)?\s+(compose\s+)?(build|pull)|--build\b|\bpull\b", re.IGNORECASE
)

VENV_MARKERS = ("$(PYTHON)", "$(VENV_DIR)", ".venv", "uv pip", "uv venv", "pip install")


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def makefile():
    return Makefile(MAKEFILE)


@pytest.fixture
def host_csv(tmp_path):
    """A realistic esxtop capture living outside the repository."""
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    tails, _expected = vmdk_column_tails()
    return write_csv(capture_dir / "host_capture.csv", tails)


@pytest.fixture
def docker(tmp_path):
    """Fake ``docker``/``docker-compose`` on PATH that records invocations."""

    class Stub(object):
        def __init__(self, bin_dir, log):
            self.bin_dir = bin_dir
            self.log = log
            self.env = stub_env(bin_dir, log)

        @property
        def invocations(self):
            return docker_invocations(self.log)

        def describe(self):
            return "\n".join(
                "%s %s" % (i["program"], " ".join(i["argv"])) for i in self.invocations
            ) or "<docker was never invoked>"

    bin_dir, log = docker_stub_dir(tmp_path)
    return Stub(bin_dir, log)


@pytest.fixture
def repo_copy(tmp_path):
    """A minimal checkout copy so the default CSV can be created next to it."""
    dest = tmp_path / "checkout"
    dest.mkdir()
    for name in ("Makefile", "Dockerfile", "docker-compose.yml", "requirements.txt",
                 ".dockerignore"):
        source = REPO_ROOT / name
        if source.exists():
            (dest / name).write_bytes(source.read_bytes())
    return dest


def assert_readonly_csv_mount(invocations, csv_path, compose_dir, context):
    """Assert the host CSV is exposed to the container read-only."""
    hits = csv_mounts(invocations, csv_path)
    if hits:
        assert any(read_only for _h, _c, read_only in hits), (
            "the host CSV is bind-mounted but not read-only: %s\n%s" % (hits, context)
        )
        return
    if compose_used(invocations):
        compose_file = Path(compose_dir) / "docker-compose.yml"
        if not compose_file.exists():
            compose_file = COMPOSE_FILE
        assert compose_file.exists() and compose_readonly_bind(
            compose_file.read_text(encoding="utf-8")
        ), (
            "the target runs docker compose but %s declares no read-only bind "
            "mount for the host CSV\n%s" % (compose_file, context)
        )
        assert mentions_csv(invocations, csv_path), (
            "the host CSV path %s is never passed to docker compose\n%s"
            % (csv_path, context)
        )
        return
    pytest.fail(
        "no docker invocation bind-mounts the host CSV %s (read-only) into the "
        "container\n%s" % (csv_path, context)
    )


# --------------------------------------------------------------------------
# Criterion 1: the target exists, is phony and shows up in `make help`
# --------------------------------------------------------------------------

def test_container_report_target_exists_and_is_phony(makefile):
    target = get_docker_stats_target(makefile)

    assert target in makefile.rules, "expected a make target running the container report"
    assert target in makefile.phony, (
        "target '%s' is missing from .PHONY (found: %s)"
        % (target, ", ".join(sorted(makefile.phony)))
    )


def test_help_lists_the_container_report_target(makefile):
    target = get_docker_stats_target(makefile)

    result = run_make("help")

    assert result.returncode == 0, result
    assert target in result.stdout, (
        "'make help' does not mention the '%s' target:\n%s" % (target, result.stdout)
    )


# --------------------------------------------------------------------------
# Criterion 2: CSV override with the usual default
# --------------------------------------------------------------------------

def test_csv_variable_is_overridable_and_defaults_to_the_usual_csv(makefile):
    assert makefile.assignment_op("CSV") == "?=", (
        "Makefile must declare an overridable 'CSV ?= ...' variable in the same "
        "style as CSV_FILE (found operator: %r)" % makefile.assignment_op("CSV")
    )
    assert makefile.variable("CSV") == DEFAULT_CSV_NAME, (
        "CSV must default to %r like the other targets, got %r"
        % (DEFAULT_CSV_NAME, makefile.variable("CSV"))
    )


def test_csv_override_selects_the_host_file(makefile, host_csv, docker):
    target = get_docker_stats_target(makefile)

    result = run_make(target, overrides={"CSV": str(host_csv)}, env=docker.env)

    assert result.returncode == 0, result
    assert mentions_csv(docker.invocations, host_csv), (
        "CSV=%s was not passed through to the container run:\n%s"
        % (host_csv, docker.describe())
    )


def test_default_csv_is_used_when_no_override_is_given(makefile, repo_copy, docker):
    target = get_docker_stats_target(makefile)
    tails, _expected = vmdk_column_tails()
    default_csv = write_csv(repo_copy / DEFAULT_CSV_NAME, tails)

    result = run_make(target, cwd=repo_copy, env=docker.env)

    assert result.returncode == 0, result
    assert mentions_csv(docker.invocations, default_csv), (
        "running '%s' with no CSV= override did not analyse the default %s:\n%s"
        % (target, DEFAULT_CSV_NAME, docker.describe())
    )


# --------------------------------------------------------------------------
# Criterion 3: read-only bind mount, report on make's stdout
# --------------------------------------------------------------------------

def test_host_csv_is_bind_mounted_read_only(makefile, host_csv, docker):
    target = get_docker_stats_target(makefile)

    result = run_make(target, overrides={"CSV": str(host_csv)}, env=docker.env)

    assert result.returncode == 0, result
    assert_readonly_csv_mount(docker.invocations, host_csv, REPO_ROOT, docker.describe())


def test_container_report_is_printed_on_make_stdout(makefile, host_csv, docker):
    target = get_docker_stats_target(makefile)

    result = run_make(target, overrides={"CSV": str(host_csv)}, env=docker.env)

    assert result.returncode == 0, result

    started = [
        i for i in docker.invocations
        if {"run", "up", "exec", "start"} & {a for a in i["argv"] if not a.startswith("-")}
    ]
    assert started, (
        "the target never starts a container to produce the report:\n%s" % docker.describe()
    )
    assert STUB_REPORT_MARKER in result.stdout, (
        "the container's report is not printed on the stdout of the make "
        "invocation:\n--- stdout ---\n%s\n--- stderr ---\n%s"
        % (result.stdout, result.stderr)
    )


# --------------------------------------------------------------------------
# Criterion 4: missing CSV fails fast
# --------------------------------------------------------------------------

def test_missing_csv_fails_fast_with_a_message_naming_the_path(makefile, tmp_path, docker):
    target = get_docker_stats_target(makefile)
    missing = tmp_path / "captures" / "does_not_exist.csv"

    result = run_make(target, overrides={"CSV": str(missing)}, env=docker.env)

    assert result.returncode != 0, (
        "'make %s CSV=%s' must exit non-zero for a missing CSV:\n%s"
        % (target, missing, result)
    )
    assert "No rule to make target" not in result.output, result.output
    assert str(missing) in result.output, (
        "the failure does not name the missing path %s:\n%s" % (missing, result.output)
    )


def test_missing_csv_does_not_start_the_container(makefile, tmp_path, docker):
    target = get_docker_stats_target(makefile)
    missing = tmp_path / "captures" / "does_not_exist.csv"

    result = run_make(target, overrides={"CSV": str(missing)}, env=docker.env)

    assert result.returncode != 0, result
    assert docker.invocations == [], (
        "docker was invoked even though the CSV %s does not exist:\n%s"
        % (missing, docker.describe())
    )


# --------------------------------------------------------------------------
# Criterion 5: works from a clean checkout, no host venv
# --------------------------------------------------------------------------

def test_target_does_not_depend_on_the_host_venv(makefile):
    target = get_docker_stats_target(makefile)
    rule = makefile.rules[target]

    assert "venv" not in rule.prereqs, (
        "'%s' must not depend on the host virtualenv (prereqs: %s)"
        % (target, rule.prereqs)
    )

    recipe = rule.recipe_text
    for prereq in rule.prereqs:
        prereq_rule = makefile.rules.get(prereq)
        if prereq_rule is not None:
            recipe += "\n" + prereq_rule.recipe_text
    used = [marker for marker in VENV_MARKERS if marker in recipe]
    assert not used, (
        "'%s' must run entirely inside the container, but its recipe uses %s:\n%s"
        % (target, used, recipe)
    )


def test_target_builds_or_pulls_the_image(makefile):
    target = get_docker_stats_target(makefile)
    rule = makefile.rules[target]
    recipe = rule.recipe_text
    for prereq in rule.prereqs:
        prereq_rule = makefile.rules.get(prereq)
        if prereq_rule is not None:
            recipe += "\n" + prereq_rule.recipe_text

    assert BUILD_OR_PULL.search(recipe), (
        "'%s' must build or pull the image so it works from a clean checkout:\n%s"
        % (target, recipe)
    )


# --------------------------------------------------------------------------
# Criterion 6: README documentation
# --------------------------------------------------------------------------

def test_readme_documents_the_target_with_a_copy_pasteable_example(makefile):
    target = get_docker_stats_target(makefile)
    text = README.read_text(encoding="utf-8")

    in_block = False
    examples = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_block = not in_block
            continue
        if in_block and re.search(r"\bmake\s+%s\b" % re.escape(target), line):
            examples.append(line.strip())

    assert examples, (
        "README.md has no fenced example running 'make %s'" % target
    )
    assert any("CSV=" in line and ".csv" in line for line in examples), (
        "README.md must show a host CSV being mounted and analysed, e.g. "
        "'make %s CSV=/path/to/%s'; found: %s" % (target, DEFAULT_CSV_NAME, examples)
    )
