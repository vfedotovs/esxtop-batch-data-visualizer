# esxtop-batch-data-visualizer
Visualize performance data from esxtop batch mode CSV exports. This tool extracts, filters, and graphs key VM and host metrics (CPU, disk, memory, etc.) from large esxtop datasets, helping analyze performance trends over time.

## How to use 
1. Collect esxtop batch data as mentined [here](https://knowledge.broadcom.com/external/article/370279/collecting-esxtop-batch-data-for-esxi-pe.html)
2. Describe collected batch data from csv file
```sh
./describe_extop.sh esxtop_batch_data.csv
```
3. Extract data column index id of your interest
```sh
python3 ./find_column_idx.py  esxtop_batch_data.csv | grep -E -B 4 "scsi.*Write"
... 
Column 51446:
  Host:     esx01.example.com
  Category: Virtual Disk(EXAMPLE_VM_NAME:scsi3:0)
  Counter:  Average MilliSec/Write
  Raw:      \\esx01.example.com\Virtual Disk(EXAMPLE_VM_NAME:scsi3:0)\Average MilliSec/Write
```
4. Extract time series data from the chosen column
This will generate a .data file (e.g., esxtop_batch_data_col_51446.data) with timestamped metric values.
```sh
 python3  get_value_by_col_index_v2_fs.py  esxtop-batch-data.csv 51446
```
 5.  Plot the time series data
Visualize the extracted data using:
```sh
python3  plot_chart_form_data_file.py  esxtop_batch_data_col_51446.data
```
![Exmample of vizualized data](visualisation_example.png)



## Feature Roadmap
- [x] Parse large CSV files exported by esxtop in batch mode
- [x] Extract column metadata (host, category, counter)
- [x] Filter by specific performance metrics (e.g., virtualdisk latency, device latency)
- [x] Generate time series data from a selected metric
- [x] Plot data with time on the X-axis and metric values on the Y-axis
- [ ] Support multiple column extraction and chart overlay
- [ ] Export charts as PNG/PDF for reporting
- [ ] Add interactive dashboards using Plotly or Streamlit
- [ ] Add CLI options for batch processing and automation
