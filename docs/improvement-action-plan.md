# Improvement Action Plan

**Project:** esxtop-batch-data-visualizer  
**Review date:** 2026-08-12  
**Scope:** Full repository review (library, CLI scripts, Makefile, Flask/Docker web UI, tests, docs). Working tree was clean; this is not a diff review.  
**Reviewer method:** Source inspection plus a synthetic PDH-CSV repro of parser/extractor behavior. Existing unit tests were run (`12 passed`) and do not cover the defects below.

---

## Verdict

The library layout (`src/esxtop_visualizer`) is a solid start, and a few older issues (bare `except:`, duplicated plot scripts, column-index offset in the *new* parser) are already fixed. The product is still closer to a working prototype than to a trustworthy 1.0 analysis tool.

The highest risk is **silent wrong or empty results**, not crashes. A performance tool that plots the wrong column, drops every sample, or times out on a real 400 MB capture will mislead operators. The Docker web UI adds a second class of risk: **unauthenticated, root, threaded Flask** with 500 MB uploads and process-global `os.chdir()`.

**Recommended next 1–2 days of work:** items 1–6 (correctness + broken documented workflow + web race). Then items 7–12 so the same bugs cannot regress.

---

## Critical bugs (reproduced or verified in source)

| ID | Finding | Evidence | User impact |
|----|---------|----------|-------------|
| C1 | Timestamp matcher uses `fullmatch` on `MM/DD/YYYY HH:MM:SS` only | Synthetic PDH-CSV with `01/22/2024 15:30:45.123` extracts **0 points**. ISO `2024-01-22 15:30:45` also extracts 0. PDH-CSV 4.0 / Perfmon / many esxtop exports include fractional seconds. | Describe tables become all `NaN`. Plots fail with "No valid data points". Looks like an empty or corrupt capture. |
| C2 | `make extract` then `make plot` uses two different filenames | Extractor always writes `col_{id}.data`. Makefile `DATA_FILE` is `$(basename $(CSV_FILE))_col_$(COL_ID).data`. README documents the Makefile name. | Documented Quick Start plot path fails with file-not-found. |
| C3 | `make find-column` only scans the first 10 columns | `scripts/find_column_idx.py $(CSV_FILE) --limit 10 \| grep ...`. Default pattern is `scsi.*Write`, which is almost never in the first 10 counters. | Documented "find the column" step returns nothing. Users pick a wrong index by hand. |
| C4 | Web analysis is not concurrency-safe | `app.py` does `os.chdir(output_dir)` around subprocesses. Flask/Werkzeug serves requests threaded by default. Scripts write `col_*.data` into *cwd*. | Two overlapping uploads can mix files, clobber cwd, or attach the wrong artifacts to a download list. |
| C5 | Web UI is an unauthenticated public analyzer | `app.run(host='0.0.0.0')`, docker-compose publishes `5000:5000`, 500 MB uploads, 5-minute `bash` child per request, container runs as **root**, no cleanup of `/tmp/esxtop_output`. | Anyone who can reach the port can fill disk, burn CPU, and read other users' temp dirs if they guess `tmp*` names. |
| C6 | Tests cannot catch C1–C3 | Tests only check dataclasses, title helpers, and `FileNotFoundError`. TODOs in the test files still say "add sample CSV tests". | Green CI (if added later) would still ship empty extractions. |

### Related correctness landmines (high, not fully reproduced)

- **Linux `date -d` locale** in `describe_extop.sh` / `_web.sh`: interval between first/last sample is computed with GNU `date`. `08/12/2024` can be 12 Aug or 8 Dec depending on locale. Docker is Linux, so the web summary interval is untrustworthy.
- **Duplicate timestamps overwrite samples.** `TimeSeriesData` is an `OrderedDict` keyed by the timestamp *string*. With 1-second esxtop delay and no milliseconds, a second sample in the same second is lost.
- **Shell scripts have no `set -euo pipefail`.** If `find_column_idx.py` fails or matches nothing, `extract_columns_batch.py` is invoked with zero column ids (usage error) and the script continues. Web layer then reports success with empty tables.
- **Summary `awk` only accepts `$3 ~ /^-?[0-9]+(\.[0-9]+)?$/`.** Scientific notation (`1.23e-04`) is dropped, so averages can be computed on a subset of samples.
- **`summarize_columns` treats `Virtual Disk(VM:scsi0:0)` as the category.** Every VMDK becomes its own category; the "top categories" view is much less useful than the README implies.
- **Physical disk path only matches `naa.*`.** NVMe (`t10.NVMe_*`, `eui.*`) devices are silently omitted.

---

## Red flags (design / ops / maintenance)

1. **Stated maturity does not match the suite.** `pyproject.toml` is `1.0.0` / "Beta"; commit `73f97d2` still calls the Docker app "MVP with some bugs WIP". Tests are scaffolding.
2. **Two sources of truth for dependencies.** `requirements.txt` has Flask; `pyproject.toml` only lists matplotlib. `pip install -e .` does not produce a working web app.
3. **~300 lines duplicated** between `describe_extop.sh` and `describe_extop_web.sh`. Bugfixes have to land twice (and already drifted: interactive prompt vs auto-continue).
4. **Describe scripts still full-scan huge CSVs 4 times** (`cat \| tr ',' '\n' \| grep`) before the batch extractor runs. A 400 MB file can blow the web 300 s timeout even after the extractor was optimized to one pass.
5. **Process model for analysis is "shell out to bash + python3".** The library is not used by `app.py` directly. Harder to test, timeout, and cancel cleanly.
6. **Flask development server in "production"** (`FLASK_ENV=production` is also deprecated). No gunicorn/uvicorn, no worker/timeouts, no request queue.
7. **Stale docs.** `docs/todo.md` still tracks legacy `get_value_by_col_index_v2_fs.py` offset and old plot scripts. `docs/claude_todo.md` is mostly a completed architecture review. Easy to "fix" the wrong file.
8. **`.gitignore` ignores `*.png`.** `visualisation_example.png` is already tracked; future screenshot updates need `git add -f`.
9. **Docstring `SyntaxWarning`** on Python 3.12+ (`\A`, `\c` in non-raw strings in `parser.py`). These become errors in a future CPython.
10. **No LICENSE file** despite `license = MIT` in `pyproject.toml`.
11. **No CI.** No GitHub Actions, no lint, no typecheck.
12. **`print_column_info` compact format** prints a stray trailing `'` (`Column 1 RAW ...Write'`). Downstream `sed` still works today; it is a fragile contract.

### Already fixed — do not reopen

These appear in `docs/todo.md` / `docs/claude_todo.md` as open or historical items but are **not** current library bugs:

- Chart scale vs label mismatch — fixed in `src/esxtop_visualizer/visualizer.py` (`Value × {scale}`).
- Bare `except:` in the active visualizer — fixed (`ValueError`, `IndexError`).
- Legacy plot script duplication — replaced by `scripts/visualize_data.py`.
- **Column index offset in the current parser.** `parse_csv_header` stores the real `enumerate(header)` index, including skipped `(PDH-CSV …)` columns. The *legacy* `find_column_idx.py` still prints a compacted 0-based index; do not use it.

---

## Ordered action list

Items are in recommended implementation order. Times are for one developer who already knows this repo. Difficulty: **Easy** / **Medium** / **Hard**.

### Milestone A — Stop shipping wrong or empty answers (do first)

| # | Item | Why this position | Approx. time | Difficulty | Notes |
|---|------|-------------------|--------------|------------|-------|
| 1 | **Accept real esxtop timestamps** in extractor + visualizer + describe scripts | Root cause of empty tables/plots on common PDH-CSV 4.0 files | **3–5 h** | Medium | Use `search`/`match`, not `fullmatch`. Allow `.sss` fractional seconds. Keep the time portion for `datetime` (drop or parse fraction). Add ISO-8601 `YYYY-MM-DD HH:MM:SS` as a second pattern (Azure VMware / some wrappers). Key `TimeSeriesData` by parsed datetime, not the raw string, so `15:30:45` and `15:30:45.123` do not collide. |
| 2 | **Fail loud when zero samples are extracted** | Today a "successful" run can write `*: NaN` or empty series and the shell still prints a table | **1–2 h** | Easy | `extract_column_data` / batch extract should raise or return a status if no timestamp row matched, or if every value is `None`. CLI exit non-zero. Web `success=false` with an explicit "unrecognized timestamp format" message. |
| 3 | **Fix Makefile + README extract/plot contract** | Documented Quick Start is broken even when extraction works | **45–90 min** | Easy | Make `extract` write (or copy/symlink) the path `plot` expects, *or* change `DATA_FILE` to `col_$(COL_ID).data` everywhere (README, help text, `plot-save`). Prefer one name. `plot-save` help currently implies `CSV_FILE` but the target reads `DATA_FILE`. |
| 4 | **Remove `--limit 10` from `make find-column`** (or apply limit *after* grep) | Documented discovery path cannot find VMDK write columns | **20–40 min** | Easy | Default should search all columns. If output is huge, add `--pattern` to the Python CLI and filter in-process instead of `grep`. Keep `--limit` as an explicit opt-in. |
| 5 | **Add a tiny committed fixture CSV + tests for C1–C4** | Without this, item 1 will regress | **4–6 h** | Medium | Check in `tests/fixtures/esxtop_min.csv` (header + 3 rows, VMDK + naa device, with **milliseconds**). Tests: parse indices, extract write column, batch extract, friendly title, `load_data_file`. Also a millisecond-less file and an ISO file. Do **not** gitignore this fixture (`tests/fixtures/*.csv` exception). |

**Milestone A total: ~10–16 hours.** After this, CLI extract/plot and describe tables should work on real captures.

### Milestone B — Web UI must be safe to click

| # | Item | Why this position | Approx. time | Difficulty | Notes |
|---|------|-------------------|--------------|------------|-------|
| 6 | **Stop using `os.chdir` in `app.py`** | Threaded request race; also breaks relative paths if anything else runs in-process | **2–4 h** | Medium | Pass `output_dir` into the scripts (`extract_and_save_batch` already has `output_dir`). Run subprocess with `cwd=output_dir` (per-process, not per-interpreter). Delete unused `UPLOAD_FOLDER` or actually use it. |
| 7 | **Harden the Docker service for local-tool use** | C5 is a red flag if compose is bound on a shared/lab network | **3–5 h** | Medium | Default bind `127.0.0.1:5000`. Run as non-root (`USER`). Replace Flask dev server with gunicorn (timeout > analysis budget). Add compose `mem_limit` / pids. Delete output dirs after TTL (e.g. 1 h) or on a cron in-app sweeper. Validate `analysis_type` allow-list. |
| 8 | **Replace four full-file `cat \| tr \| grep` scans** in describe scripts with one Python summary | Web 5-minute timeout + huge host CPU on 400 MB files | **3–5 h** | Medium | New `esxtop_visualizer.summary.capture_overview(path)` reading **header + timestamp column only**. Return hostname(s), sample count, first/last ts, interval (computed in Python, not `date`). Kills the Linux locale date bug at the same time. |
| 9 | **`set -euo pipefail` + empty-match guards** in all three shell scripts | Failed child processes currently look like success | **1.5–2.5 h** | Easy | If column-id file is empty, print a clear message and exit 2. Quote every expansion. Prefer `python3` from `VIRTUAL_ENV` / Makefile `$(PYTHON)` so Docker venv and host venv match. |

**Milestone B total: ~10–17 hours.** After this, Docker is a reasonable local appliance rather than a lab accident.

### Milestone C — Make results trustworthy and maintainable

| # | Item | Why this position | Approx. time | Difficulty | Notes |
|---|------|-------------------|--------------|------------|-------|
| 10 | **Parse PDH object vs instance vs counter** | Summarize and filters are wrong-shaped | **2–3 h** | Easy | Split `Virtual Disk(EXAMPLE_VM:scsi0:0)` into object=`Virtual Disk`, instance=`EXAMPLE_VM:scsi0:0`. Store on `ColumnMetadata`. Update `get_friendly_name` and `summarize_columns`. |
| 11 | **Deduplicate `describe_extop.sh` / `describe_extop_web.sh`** | Drift is already present (prompt vs auto) | **3–4 h** | Medium | One script, `--yes` / `ESXTOP_NONINTERACTIVE=1` for the web path. Better long-term: move the whole describe pipeline into Python (`python -m esxtop_visualizer describe …`) and keep a 10-line shell wrapper. |
| 12 | **Fix summary statistics** | Averages can ignore valid samples; no tail latency | **2–4 h** | Medium | Parse values in Python (accept int/float/scientific/`NaN`). Emit count, min, avg, max, p50/p95/p99. This is also README roadmap item "Percentile statistics" and is cheap once extraction is solid. Optional: color/threshold flags (`>20 ms` warn, `>50 ms` critical). |
| 13 | **CI + lint + dependency single-source** | Prevents silent regressions and install drift | **2–3 h** | Easy | GitHub Actions: `pytest`, ruff, maybe mypy on `src/`. `pyproject.toml` extras: `web = ["flask", "gunicorn"]`, `dev = ["pytest", "pytest-cov", "ruff"]`. `requirements.txt` generated or replaced by `pip install -e ".[web]"`. Fix docstring invalid escapes (raw strings). Add `LICENSE`. |
| 14 | **Bounds-check column indices and header/row width** | `row[column_index]` `IndexError` becomes silent `NaN` today | **1–2 h** | Easy | If index >= header length, error before scanning the file. Warn if a data row is shorter than the header (truncated export). |
| 15 | **Device coverage + print format cleanup** | Silent omissions and a brittle CLI contract | **1.5–2.5 h** | Easy | Physical disk: include `naa.*`, `eui.*`, `t10.*` (or make the prefix a flag). Remove the stray `'` in `print_column_info`. Close matplotlib figures (`plt.close()`). |

**Milestone C total: ~12–19 hours.**

### Milestone D — Product improvements (roadmap, after A–C)

Do these only after extract/describe/web are trustworthy. Times are much softer.

| # | Item | Approx. time | Difficulty | Notes |
|---|------|--------------|------------|-------|
| 16 | CSV/JSON export of summary tables | **2–3 h** | Easy | Web downloads become useful; Excel-friendly. |
| 17 | Unified Typer/Click CLI (`esxtop-viz describe\|find\|extract\|plot`) | **6–10 h** | Medium | Replaces Makefile + many scripts as the real UX. Keep Makefile as thin wrappers. |
| 18 | Interactive HTML report (Plotly) | **8–12 h** | Medium | README roadmap. Much better than one PNG per column for 80 VMDKs. |
| 19 | IOPS / throughput counters next to latency | **3–5 h** | Medium | `Commands/sec`, `Reads/sec`, `Writes/sec`, `KBps`. Same extract path. |
| 20 | Multi-file before/after comparison | **8–16 h** | Hard | Align on relative time or wall clock; overlay or delta tables. |
| 21 | REST API + job queue for large files | **8–16 h** | Hard | Only if this stays a shared service. Pair with auth. Do not expand the current sync `/upload` further. |
| 22 | Streaming / column-pruned parser for 50k-wide CSVs | **12–24 h** | Hard | `csv.reader` materializes every cell of every row. For 400 MB × many columns, consider header-driven column selection (e.g. only keep timestamp + requested indices). |

**Milestone D total: ~47–86 hours** depending on how far you take the product.

---

## Suggested sequencing

```
Week 1 (correctness)
  1 timestamps → 2 fail-loud → 3 Makefile/README → 4 find-column → 5 fixtures/tests
  Gate: synthetic + one real customer CSV extracts non-zero points; make extract && make plot works.

Week 1–2 (web + perf)
  6 cwd race → 7 docker harden → 8 Python overview (kills date locale + 4× scan) → 9 shell guards
  Gate: two parallel curl uploads do not mix files; 400 MB file finishes inside timeout.

Week 2–3 (quality)
  10 object/instance split → 11 one describe entrypoint → 12 percentiles → 13 CI → 14–15 polish

Later
  16–22 only against an actual user request
```

### Effort rollup

| Slice | Items | Approx. calendar | Approx. effort |
|-------|-------|------------------|----------------|
| P0 correctness | 1–5 | 1–2 days | 10–16 h |
| P0/P1 web + reliability | 6–9 | 1–2 days | 10–17 h |
| P1/P2 maintainability | 10–15 | 2–3 days | 12–19 h |
| P2/P3 features | 16–22 | 2–4 weeks | 47–86 h |
| **Minimum useful hardening (A+B)** | **1–9** | **~1 week** | **20–33 h** |

---

## Implementation notes for item 1 (highest leverage)

Current matcher:

```python
TIMESTAMP_PATTERN = re.compile(r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}')
# ...
if TIMESTAMP_PATTERN.fullmatch(cell_clean):  # rejects ".123"
```

Confirmed against a minimal PDH-CSV: **0 points extracted** when the first column is `"01/22/2024 15:30:45.123"`.

Suggested contract:

```text
accepted:
  01/22/2024 15:30:45
  01/22/2024 15:30:45.1
  01/22/2024 15:30:45.123
  2024-01-22 15:30:45
  2024-01-22T15:30:45.123
rejected / skip cell:
  bare numbers, counter names, empty
```

Keep looking in column 0 first (PDH timestamp column) instead of scanning every cell of a 50k-wide row. That is both faster and avoids a future false-positive if a metric string ever looks like a date.

Visualiser `strptime("%m/%d/%Y %H:%M:%S")` must use the same parser. Prefer storing ISO in `.data` files going forward (`2024-01-22T15:30:45.123: 1.5`) and accepting the old `timestamp: value` format on read.

---

## Out of scope / do not do yet

- Rewriting the UI in a JS framework.
- Adding authentication *and* a public REST API in the same change (pick "local tool" or "shared service" first).
- Editing files under `legacy/` except to mark them do-not-use (already done in `legacy/README.md`).
- Treating `docs/todo.md` as the backlog — replace it with this plan or delete it after the next docs pass.

---

## Appendix: test command used during this review

```bash
pytest tests/ -v          # 12 passed, no fixture coverage
# plus an ad-hoc synthetic PDH-CSV that demonstrated 0 extracts on millisecond timestamps
```
