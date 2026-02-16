# Architecture Review: esxtop-batch-data-visualizer

## Critical Issues (Fix Immediately)

### 1. ~~Scaling/Label Mismatch in Charts~~ ✅ FIXED
- ~~`plot_chart_form_data_file.py:21` multiplies by `100` but labels say `× 1000`~~ → Fixed: labels now say `× 100`
- ~~`save_chart_from_column_id.py:32` multiplies by `1` but labels say `× 1000`~~ → Fixed: labels now say `Value` (no scaling)
- **Impact**: Charts display misleading data to users

### 2. ~~Code Duplication~~ ✅ FIXED
- ~~`plot_chart_form_data_file.py` and `save_chart_from_column_id.py` are 95% identical~~ → Created unified `visualizer.py`
- ~~Different scaling factors (100 vs 1) suggest copy-paste without refactoring~~ → Now uses `--scale` CLI argument
- ~~Any bug fix must be applied in TWO places~~ → Single source of truth
- New usage: `visualizer.py data.data [-o output.png] [-s SCALE] [--no-show]`

### 3. ~~Bare Exception Handler~~ ✅ FIXED
- ~~`plot_chart_form_data_file.py:24` uses `except:` which catches ALL exceptions~~ → Fixed in `visualizer.py` with `except (ValueError, IndexError)`
- ~~Masks errors and makes debugging difficult~~ → Now logs skipped lines count

## High Priority Issues

### 4. ~~No Shared Library/Module Structure~~ ✅ FIXED
~~Current flat structure~~ → Refactored into proper Python package structure

**Implemented structure:**
```
├── src/
│   └── esxtop_visualizer/
│       ├── __init__.py      # Public API exports
│       ├── parser.py        # CSV parsing logic
│       ├── extractor.py     # Column data extraction
│       └── visualizer.py    # Plotting utilities
├── scripts/
│   ├── find_column_idx.py   # CLI wrapper
│   ├── extract_column.py    # CLI wrapper
│   ├── visualize_data.py    # CLI wrapper
│   └── describe_extop.sh    # Shell script
├── legacy/
│   ├── README.md            # Migration guide
│   ├── plot_chart_form_data_file.py
│   └── save_chart_from_column_id.py
├── tests/
│   ├── test_parser.py
│   ├── test_extractor.py
│   └── test_visualizer.py
├── pyproject.toml           # Package configuration
├── Makefile                 # Updated paths
├── requirements.txt
└── README.md                # Updated docs
```

**Benefits achieved:**
- Code can now be imported as a library
- Proper separation of concerns (library vs CLI)
- Test structure in place
- Legacy scripts archived with migration guide
- Full backward compatibility maintained

### 5. ~~Hard-coded Magic Numbers~~ ✅ FIXED
- ~~Scaling factors (100, 1) not parameterized~~ → Now uses `--scale` argument in `visualizer.py`
- ~~Should be CLI arguments: `--scale 100`~~ → Implemented: `visualizer.py data.data --scale 100`
- Makefile also supports `SCALE=100` variable

### 6. Stale todo.md
- Bug fixed in commit `80d0151` but todo.md not updated

## Medium Priority Issues

### 7. No Tests or CI/CD
- No unit tests for CSV parsing edge cases
- No GitHub Actions workflow

### 8. Shell Script Fragility
- `describe_extop.sh` uses fragile glob patterns
- ~~Multiple full-file scans for 400MB files (inefficient)~~ ✅ FIXED
  - Implemented batch extraction: `extract_columns_batch.py` reads file once and extracts all columns
  - Performance improvement: O(N) → O(1) file scans (where N = number of columns)
  - Updated `describe_extop.sh` to use batch extraction instead of loop

### 9. No Input Validation
- Timestamp format is rigid (MM/DD/YYYY HH:MM:SS only)
- No bounds checking for column indices

## Recommended Improvements

### Consolidate Visualization Scripts
Create single `visualizer.py` with:
```python
def plot_timeseries(data_file, scale=1, output=None, show=True):
    """Plot or save chart from .data file."""
    # Shared logic
    if output:
        plt.savefig(output)
    if show:
        plt.show()
```

### Add CLI with argparse
```python
# visualizer.py
parser.add_argument('--scale', type=float, default=1.0)
parser.add_argument('--output', '-o', help='Save to PNG')
parser.add_argument('--no-show', action='store_true')
```

### Fix Exception Handling
```python
# Replace bare except:
except (ValueError, IndexError) as e:
    logging.warning(f"Skipped line: {e}")
    continue
```
