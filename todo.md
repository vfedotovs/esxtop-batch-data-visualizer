# Review Findings Todo

## Critical
- [ ] Fix column index offset in `get_value_by_col_index_v2_fs.py` (use absolute column index or compute correct offset).

## Minor
- [ ] Replace fragile globbing in `describe_extop.sh` (`ls -l col_*.data | awk ...`) with safe glob loop and handle no matches.
- [ ] Align scaling/labels in `plot_chart_form_data_file.py` (multiplier vs label).
- [ ] Replace bare `except:` in `plot_chart_form_data_file.py` with specific exceptions and optional logging/count.
- [ ] Align scaling/labels in `save_chart_from_column_id.py` (multiplier vs label).
