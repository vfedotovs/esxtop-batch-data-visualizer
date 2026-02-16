# Legacy Scripts (Deprecated)

These scripts have been replaced by the unified `visualize_data.py` tool and are no longer maintained. They are kept here for historical reference only.

## Deprecated Files

- **plot_chart_form_data_file.py** - Interactive plotting with hardcoded scale×100
- **save_chart_from_column_id.py** - Save to PNG with hardcoded scale×1

## Why Deprecated?

These scripts were deprecated because:
- **Code duplication**: 95% identical code between the two files
- **Inconsistent scaling**: Different hardcoded scale factors (100 vs 1)
- **Inflexible**: No command-line control over scaling or output options
- **Maintenance burden**: Bug fixes had to be applied in multiple places

## Migration Guide

### Old: plot_chart_form_data_file.py

```bash
# Old way (deprecated)
python3 plot_chart_form_data_file.py data.data
```

```bash
# New way (recommended)
python3 scripts/visualize_data.py data.data --scale 100
```

### Old: save_chart_from_column_id.py

```bash
# Old way (deprecated)
python3 save_chart_from_column_id.py data.data
```

```bash
# New way (recommended)
python3 scripts/visualize_data.py data.data -o output.png --no-show
```

## Benefits of New Unified Tool

The new `scripts/visualize_data.py` provides:
- **Configurable scaling**: Use `--scale` argument to set any scale factor
- **Flexible output**: Choose to display, save, or both
- **Better error handling**: Specific exception types instead of bare except
- **Consistent behavior**: Single source of truth
- **Library integration**: Built on top of importable modules in `src/esxtop_visualizer/`

## Full Feature Comparison

| Feature | Old Scripts | New visualize_data.py |
|---------|-------------|----------------------|
| Interactive display | plot_chart... only | `--scale 100` |
| Save to PNG | save_chart... only | `-o output.png` |
| Custom scaling | Hardcoded | `--scale N` |
| Both display & save | Not possible | `--scale 100 -o out.png` |
| Save without display | Not easily | `--no-show -o out.png` |
| Default output name | N/A | Auto-generated |

For more information, see the main project README.md.
