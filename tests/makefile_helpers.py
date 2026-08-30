"""Helpers for testing ``Makefile`` targets without requiring GNU make.

The container-report target added for the "run the container's text-stats
report against a host CSV" issue is a plain ``make`` target that shells out to
``docker``. Neither ``make`` nor ``docker`` is guaranteed to exist wherever the
suite runs, so this module provides:

* :func:`parse_makefile` - a small parser for variables, rules and ``.PHONY``.
* :func:`run_make` - runs a target with real ``make`` when it is installed and
  otherwise interprets the recipe itself (variable expansion + ``/bin/sh``),
  which is faithful for the shell-only recipes this ``Makefile`` uses.
* :func:`docker_stub_dir` - a fake ``docker`` / ``docker-compose`` that records
  every invocation instead of contacting a daemon.

Nothing here imports the application, so a missing implementation shows up as
an assertion failure in the test that needs it, never as a collection error.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = REPO_ROOT / "Makefile"
README = REPO_ROOT / "README.md"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# The default capture name every other Makefile target already uses
# (``CSV_FILE ?= esxtop_batch_data.csv``).
DEFAULT_CSV_NAME = "esxtop_batch_data.csv"

# Targets that exist today; the container-report target is whichever *new*
# target drives docker.
EXISTING_TARGETS = frozenset(
    {
        "help",
        "venv",
        "describe",
        "describe-pdisk",
        "summarize",
        "find-column",
        "extract",
        "plot",
        "plot-save",
        "all",
        "clean",
        "clean-venv",
    }
)

# Printed by the fake docker whenever a container is actually run, so a test can
# tell that the container's output reached the stdout of the make invocation.
STUB_REPORT_MARKER = "STUB-DOCKER-CONTAINER-REPORT"

STUB_LOG_ENV = "DOCKER_STUB_LOG"

DOCKER_STUB = r'''#!/usr/bin/env python3
import json
import os
import sys

argv = sys.argv[1:]
log = os.environ.get("{log_env}")
if log:
    record = {{
        "program": os.path.basename(sys.argv[0]),
        "argv": argv,
        "cwd": os.getcwd(),
        "env": {{k: v for k, v in os.environ.items() if ".csv" in v.lower()}},
    }}
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

words = [a for a in argv if not a.startswith("-")]

# ``docker build -q`` is often used to grab an image id; keep that usable.
if "build" in words:
    print("sha256:0000000000000000000000000000000000000000000000000000000000000000")
    sys.exit(0)

if {{"run", "up", "exec", "start"}} & set(words):
    print("{marker}")
    print("VM VMDK stats report (stub container output)")

sys.exit(0)
'''.format(log_env=STUB_LOG_ENV, marker=STUB_REPORT_MARKER)


# --------------------------------------------------------------------------
# Makefile parsing
# --------------------------------------------------------------------------

class MakeError(Exception):
    """Raised for ``$(error ...)`` and unknown targets."""


class Rule(object):
    def __init__(self, name, prereqs, recipe):
        self.name = name
        self.prereqs = prereqs
        self.recipe = recipe  # list of logical recipe lines, tab stripped

    @property
    def recipe_text(self):
        return "\n".join(self.recipe)

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Rule(%r, prereqs=%r)" % (self.name, self.prereqs)


class Makefile(object):
    def __init__(self, path=MAKEFILE, overrides=None):
        self.path = Path(path)
        self.text = self.path.read_text(encoding="utf-8")
        self.overrides = dict(overrides or {})
        self.vars = {}
        self.rules = {}
        self.phony = set()
        self._parse()

    # -- parsing ---------------------------------------------------------
    def _parse(self):
        raw_lines = self.text.split("\n")
        lines = []
        i = 0
        while i < len(raw_lines):
            line = raw_lines[i]
            # Join backslash continuations, keeping them intact for recipes so
            # the shell sees the same logical line make would hand it.
            while line.endswith("\\") and i + 1 < len(raw_lines):
                i += 1
                line = line + "\n" + raw_lines[i]
            lines.append(line)
            i += 1

        current = None
        cond_stack = []  # list of (taken_so_far, active)

        assign_re = re.compile(
            r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*(\?=|:=|::=|\+=|=)\s*(.*)$"
        )
        rule_re = re.compile(r"^([^\t=#][^=#]*?)\s*:(?!=)\s*(.*)$")

        for line in lines:
            active = all(a for _t, a in cond_stack)
            stripped = line.strip()

            directive = stripped.split(" ", 1)[0] if stripped else ""
            if directive in ("ifeq", "ifneq", "ifdef", "ifndef"):
                arg = stripped[len(directive):].strip()
                if active:
                    value = self._eval_condition(directive, arg)
                else:
                    value = False
                cond_stack.append((value, value and active))
                continue
            if directive == "else":
                if cond_stack:
                    taken, _cur = cond_stack[-1]
                    rest = stripped[4:].strip()
                    parent_active = all(a for _t, a in cond_stack[:-1])
                    if rest.startswith("if"):
                        sub = rest.split(" ", 1)[0]
                        arg = rest[len(sub):].strip()
                        value = (not taken) and parent_active and self._eval_condition(sub, arg)
                        cond_stack[-1] = (taken or value, value)
                    else:
                        cond_stack[-1] = (True, (not taken) and parent_active)
                continue
            if directive == "endif":
                if cond_stack:
                    cond_stack.pop()
                continue
            if not active:
                continue

            if line.startswith("\t"):
                if current is not None:
                    current.recipe.append(line[1:])
                continue

            if not stripped or stripped.startswith("#"):
                continue

            match = rule_re.match(line)
            if match and not assign_re.match(line):
                targets = match.group(1).split()
                prereqs = [p for p in match.group(2).split() if p != ";"]
                current = None
                for target in targets:
                    if target == ".PHONY":
                        self.phony.update(prereqs)
                        continue
                    rule = self.rules.get(target)
                    if rule is None:
                        rule = Rule(target, list(prereqs), [])
                        self.rules[target] = rule
                    else:
                        rule.prereqs.extend(prereqs)
                    current = rule
                continue

            match = assign_re.match(line)
            if match:
                current = None
                name, op, value = match.group(1), match.group(2), match.group(3)
                value = value.replace("\\\n", " ")
                if name == ".PHONY":
                    self.phony.update(value.split())
                    continue
                if op == "?=" and name in self.vars:
                    continue
                if op == "+=" and name in self.vars:
                    self.vars[name] = self.vars[name] + " " + value
                else:
                    self.vars[name] = value
                continue

    def _eval_condition(self, directive, arg):
        if directive in ("ifdef", "ifndef"):
            name = arg.split()[0] if arg.split() else ""
            defined = bool(self.lookup(name))
            return defined if directive == "ifdef" else not defined
        left, right = self._split_condition_args(arg)
        equal = self.expand(left).strip() == self.expand(right).strip()
        return equal if directive == "ifeq" else not equal

    @staticmethod
    def _split_condition_args(arg):
        arg = arg.strip()
        if arg.startswith("(") and arg.endswith(")"):
            inner = arg[1:-1]
            depth = 0
            for idx, ch in enumerate(inner):
                if ch in "({":
                    depth += 1
                elif ch in ")}":
                    depth -= 1
                elif ch == "," and depth == 0:
                    return inner[:idx], inner[idx + 1:]
            return inner, ""
        parts = arg.split(None, 1)
        if len(parts) == 2:
            return parts[0].strip("\"'"), parts[1].strip().strip("\"'")
        return arg, ""

    # -- expansion -------------------------------------------------------
    def lookup(self, name):
        if name in self.overrides:
            return self.overrides[name]
        if name in self.vars:
            return self.vars[name]
        return os.environ.get(name, "")

    def expand(self, text, target=None, cwd=None, depth=0):
        if depth > 40 or not text:
            return text or ""
        out = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch != "$":
                out.append(ch)
                i += 1
                continue
            if i + 1 >= len(text):
                out.append(ch)
                break
            nxt = text[i + 1]
            if nxt == "$":
                out.append("$")
                i += 2
                continue
            if nxt in "({":
                close = ")" if nxt == "(" else "}"
                depth_paren = 1
                j = i + 2
                while j < len(text) and depth_paren:
                    if text[j] == nxt:
                        depth_paren += 1
                    elif text[j] == close:
                        depth_paren -= 1
                    j += 1
                inner = text[i + 2: j - 1]
                out.append(self._resolve(inner, target=target, cwd=cwd, depth=depth))
                i = j
                continue
            if nxt == "@":
                out.append(target or "")
                i += 2
                continue
            out.append(self.expand(self.lookup(nxt), target=target, cwd=cwd, depth=depth + 1))
            i += 2
        return "".join(out)

    def _resolve(self, inner, target=None, cwd=None, depth=0):
        exp = lambda t: self.expand(t, target=target, cwd=cwd, depth=depth + 1)
        head, _, rest = inner.partition(" ")
        if head in (
            "shell", "wildcard", "abspath", "realpath", "notdir", "dir",
            "basename", "firstword", "lastword", "strip", "error", "if",
            "warning", "info", "addprefix", "addsuffix", "subst", "patsubst",
        ):
            if head == "if":
                parts = _split_args(rest)
                cond = exp(parts[0]).strip()
                if cond:
                    return exp(parts[1]) if len(parts) > 1 else ""
                return exp(parts[2]) if len(parts) > 2 else ""
            if head == "error":
                raise MakeError(exp(rest).strip())
            if head in ("warning", "info"):
                return ""
            if head == "shell":
                command = exp(rest)
                proc = subprocess.run(
                    ["/bin/sh", "-c", command],
                    cwd=str(cwd or REPO_ROOT),
                    capture_output=True,
                    text=True,
                )
                return " ".join(proc.stdout.split("\n")).strip()
            value = exp(rest)
            if head == "wildcard":
                base = Path(cwd or REPO_ROOT)
                hits = []
                for pattern in value.split():
                    path = Path(pattern)
                    if path.is_absolute():
                        hits.extend(str(p) for p in Path(path.anchor).glob(str(path.relative_to(path.anchor))))
                    else:
                        hits.extend(str(p) for p in base.glob(pattern))
                return " ".join(sorted(hits))
            if head == "abspath":
                return " ".join(str(Path(cwd or REPO_ROOT, w).absolute()) for w in value.split())
            if head == "realpath":
                return " ".join(
                    str(Path(cwd or REPO_ROOT, w).resolve()) for w in value.split()
                    if Path(cwd or REPO_ROOT, w).exists()
                )
            if head == "notdir":
                return " ".join(w.rsplit("/", 1)[-1] for w in value.split())
            if head == "dir":
                return " ".join(
                    (w.rsplit("/", 1)[0] + "/") if "/" in w else "./" for w in value.split()
                )
            if head == "basename":
                return " ".join(
                    w[: -(len(w.split(".")[-1]) + 1)] if "." in w.rsplit("/", 1)[-1] else w
                    for w in value.split()
                )
            if head == "firstword":
                words = value.split()
                return words[0] if words else ""
            if head == "lastword":
                words = value.split()
                return words[-1] if words else ""
            if head == "strip":
                return " ".join(value.split())
            parts = _split_args(rest)
            args = [exp(p) for p in parts]
            if head == "addprefix" and len(args) == 2:
                return " ".join(args[0] + w for w in args[1].split())
            if head == "addsuffix" and len(args) == 2:
                return " ".join(w + args[0] for w in args[1].split())
            if head == "subst" and len(args) == 3:
                return args[2].replace(args[0], args[1])
            if head == "patsubst" and len(args) == 3:
                pattern, repl, words = args
                out = []
                for w in words.split():
                    if "%" in pattern:
                        pre, _, post = pattern.partition("%")
                        if w.startswith(pre) and w.endswith(post):
                            stem = w[len(pre): len(w) - len(post) or None]
                            out.append(repl.replace("%", stem))
                            continue
                    out.append(w)
                return " ".join(out)
            return value

        name = inner.strip()
        if name in ("CURDIR", "PWD"):
            return str(cwd or REPO_ROOT)
        if ":" in name and "=" in name.split(":", 1)[1]:
            var, _, subst = name.partition(":")
            frm, _, to = subst.partition("=")
            value = self.expand(self.lookup(var.strip()), target=target, cwd=cwd, depth=depth + 1)
            return " ".join(
                (w[: -len(frm)] + to) if frm and w.endswith(frm) else w for w in value.split()
            )
        return self.expand(self.lookup(name), target=target, cwd=cwd, depth=depth + 1)

    # -- convenience -----------------------------------------------------
    def variable(self, name, cwd=None):
        """Expanded value of a variable, or ``None`` when it is not defined."""
        if name not in self.vars and name not in self.overrides:
            return None
        return self.expand(self.lookup(name), cwd=cwd).strip()

    def assignment_op(self, name):
        """Return the operator a variable was declared with, or ``None``."""
        pattern = re.compile(
            r"^\s*(?:export\s+)?%s\s*(\?=|:=|::=|\+=|=)" % re.escape(name), re.MULTILINE
        )
        match = pattern.search(self.text)
        return match.group(1) if match else None


def _split_args(text):
    parts = []
    depth = 0
    current = []
    for ch in text:
        if ch in "({":
            depth += 1
        elif ch in ")}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return parts


# --------------------------------------------------------------------------
# Target discovery
# --------------------------------------------------------------------------

DOCKER_RE = re.compile(r"\bdocker(-compose)?\b")


def docker_targets(makefile):
    """New (non pre-existing) targets whose recipe drives docker."""
    found = []
    for name, rule in makefile.rules.items():
        if name in EXISTING_TARGETS or name.startswith("."):
            continue
        text = rule.recipe_text
        for prereq in rule.prereqs:
            prereq_rule = makefile.rules.get(prereq)
            if prereq_rule is not None and prereq not in EXISTING_TARGETS:
                text += "\n" + prereq_rule.recipe_text
        if DOCKER_RE.search(text):
            found.append(name)
    return found


def get_docker_stats_target(makefile):
    """Name of the make target that runs the containerised text-stats report.

    Fails the calling test (never errors at import/collection time) while no
    such target exists.
    """
    candidates = docker_targets(makefile)
    if not candidates:
        pytest.fail(
            "Makefile has no target that runs the container's text-stats report "
            "on a host CSV (expected something like 'docker-stats'); targets "
            "found: %s" % ", ".join(sorted(makefile.rules))
        )
    preferred = [c for c in candidates if "stat" in c or "report" in c]
    return sorted(preferred or candidates)[0]


# --------------------------------------------------------------------------
# Running a target
# --------------------------------------------------------------------------

class MakeResult(object):
    def __init__(self, returncode, stdout, stderr, runner):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.runner = runner

    @property
    def output(self):
        return self.stdout + self.stderr

    def __repr__(self):  # pragma: no cover - debugging aid
        return "MakeResult(rc=%d, runner=%s)\n--- stdout ---\n%s\n--- stderr ---\n%s" % (
            self.returncode,
            self.runner,
            self.stdout,
            self.stderr,
        )


def run_make(target, cwd=REPO_ROOT, overrides=None, env=None, timeout=300):
    """Run ``make <target> [VAR=value ...]`` in ``cwd``.

    Uses GNU make when it is installed; otherwise interprets the recipe
    directly, which matches make's behaviour for the shell-only recipes in this
    repository.
    """
    overrides = dict(overrides or {})
    run_env = dict(os.environ)
    run_env.update(env or {})
    cwd = Path(cwd)

    make_bin = shutil.which("make", path=run_env.get("PATH", os.defpath)) or shutil.which("make")
    if make_bin:
        argv = [make_bin, target] + ["%s=%s" % (k, v) for k, v in overrides.items()]
        proc = subprocess.run(
            argv, cwd=str(cwd), env=run_env, capture_output=True, text=True, timeout=timeout
        )
        return MakeResult(proc.returncode, proc.stdout, proc.stderr, "make")

    makefile = Makefile(cwd / "Makefile", overrides=overrides)
    stdout, stderr = [], []
    rc = _run_target(makefile, target, cwd, run_env, stdout, stderr, set(), timeout)
    return MakeResult(rc, "".join(stdout), "".join(stderr), "make-lite")


def _run_target(makefile, target, cwd, env, stdout, stderr, seen, timeout):
    if target in seen:
        return 0
    seen.add(target)

    rule = makefile.rules.get(target)
    if rule is None:
        if (Path(cwd) / target).exists():
            return 0
        stderr.append("make: *** No rule to make target '%s'.  Stop.\n" % target)
        return 2

    for prereq in rule.prereqs:
        rc = _run_target(makefile, prereq, cwd, env, stdout, stderr, seen, timeout)
        if rc != 0:
            return rc

    for line in rule.recipe:
        command = line
        ignore_errors = False
        while command[:1] in ("@", "-", "+"):
            if command[0] == "-":
                ignore_errors = True
            command = command[1:]
        if not command.strip():
            continue
        try:
            command = makefile.expand(command, target=target, cwd=cwd)
        except MakeError as exc:
            stderr.append("Makefile: *** %s.  Stop.\n" % exc)
            return 2
        proc = subprocess.run(
            ["/bin/sh", "-c", command],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout.append(proc.stdout)
        stderr.append(proc.stderr)
        if proc.returncode != 0 and not ignore_errors:
            stderr.append(
                "make: *** [%s] Error %d\n" % (target, proc.returncode)
            )
            return proc.returncode
    return 0


# --------------------------------------------------------------------------
# Fake docker
# --------------------------------------------------------------------------

def docker_stub_dir(tmp_path):
    """Create a PATH directory holding fake docker executables.

    Returns ``(bin_dir, log_path)``.
    """
    bin_dir = Path(tmp_path) / "stub-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(tmp_path) / "docker-invocations.jsonl"
    for name in ("docker", "docker-compose", "podman"):
        script = bin_dir / name
        script.write_text(DOCKER_STUB, encoding="utf-8")
        script.chmod(0o755)
    return bin_dir, log_path


def stub_env(bin_dir, log_path):
    return {
        "PATH": "%s%s%s" % (bin_dir, os.pathsep, os.environ.get("PATH", os.defpath)),
        STUB_LOG_ENV: str(log_path),
    }


def docker_invocations(log_path):
    log_path = Path(log_path)
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def bind_mounts(invocation):
    """Return ``(host, container, read_only)`` triples from a docker argv."""
    argv = invocation["argv"]
    specs = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        value = None
        kind = None
        if arg in ("-v", "--volume"):
            kind, value = "v", argv[i + 1] if i + 1 < len(argv) else ""
            i += 1
        elif arg == "--mount":
            kind, value = "mount", argv[i + 1] if i + 1 < len(argv) else ""
            i += 1
        elif arg.startswith("--volume="):
            kind, value = "v", arg.split("=", 1)[1]
        elif arg.startswith("--mount="):
            kind, value = "mount", arg.split("=", 1)[1]
        elif arg.startswith("-v") and len(arg) > 2 and not arg.startswith("--"):
            kind, value = "v", arg[2:]
        if kind == "v" and value:
            parts = value.split(":")
            host = parts[0]
            container = parts[1] if len(parts) > 1 else ""
            opts = parts[2].split(",") if len(parts) > 2 else []
            specs.append((host, container, "ro" in [o.strip() for o in opts]))
        elif kind == "mount" and value:
            fields = {}
            for chunk in value.split(","):
                key, _, val = chunk.partition("=")
                fields[key.strip().lower()] = val.strip()
            host = fields.get("source") or fields.get("src") or ""
            container = fields.get("target") or fields.get("dst") or fields.get("destination") or ""
            ro = (
                "readonly" in fields
                and fields["readonly"].lower() in ("", "true", "1")
                or fields.get("ro", "").lower() in ("true", "1")
            )
            specs.append((host, container, ro))
        i += 1
    return specs


def _samefile(a, b):
    try:
        return os.path.realpath(str(a)) == os.path.realpath(str(b))
    except OSError:  # pragma: no cover - defensive
        return False


def csv_mounts(invocations, csv_path):
    """Bind mounts that expose ``csv_path`` (directly or via its directory)."""
    csv_path = Path(csv_path)
    hits = []
    for invocation in invocations:
        for host, container, ro in bind_mounts(invocation):
            if not host:
                continue
            host_abs = host if os.path.isabs(host) else os.path.join(invocation["cwd"], host)
            if _samefile(host_abs, csv_path) or _samefile(host_abs, csv_path.parent):
                hits.append((host, container, ro))
    return hits


def compose_used(invocations):
    for invocation in invocations:
        if invocation["program"].startswith("docker-compose"):
            return True
        if "compose" in invocation["argv"]:
            return True
    return False


def compose_readonly_bind(compose_text):
    """True when a compose file declares at least one read-only bind mount."""
    for line in compose_text.splitlines():
        stripped = line.strip().lstrip("-").strip().strip("\"'")
        if ":ro" in stripped and "/" in stripped:
            return True
        if re.search(r"read_only\s*:\s*true", stripped):
            return True
    return False


def mentions_csv(invocations, csv_path):
    """True when any docker invocation carries the CSV path (argv or env)."""
    needles = {str(csv_path), os.path.realpath(str(csv_path)), Path(csv_path).name}
    for invocation in invocations:
        blob = " ".join(invocation["argv"]) + " " + " ".join(invocation["env"].values())
        if any(needle in blob for needle in needles):
            return True
    return False
