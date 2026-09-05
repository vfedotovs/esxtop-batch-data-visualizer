#!/bin/bash


# Resolve script directory for reliable Python script paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Render one discovered counter as a fixed-width table, worst first.
#
# Input is the tab-separated scratch file built by the caller:
#   sort_key <TAB> min <TAB> avg <TAB> max <TAB> column <TAB> name <TAB> samples
#
# Rows are sorted by average descending, so the disk that needs attention is
# the first thing read rather than the last. MIN sits beside AVG and MAX
# because an average alone hides the shape of a series: a disk that idles and
# then spikes and one that is steadily mediocre average the same. A capture
# mixes VM-level rollups with the per-VMDK counters underneath them, and the
# two are easy to confuse when the numbers repeat, so SCOPE labels which is
# which. Units are left to the counter name in the title: the counters
# discovered in a capture are not all milliseconds.
print_counter_table() {
  local title="$1"
  local data_file="$2"
  local rule="--------------------------------------------------------------------------------"

  echo
  echo -e "\033[1m${title}\033[0m"
  echo "$rule"
  printf "%-5s  %-30s  %9s  %9s  %9s  %8s\n" \
    "SCOPE" "VMDK" "MIN" "AVG" "MAX" "COLUMN"
  echo "$rule"

  local rows=0
  local idle=0
  local nodata=0
  while IFS=$'\t' read -r sort_key min avg max col name samples; do
    [ -z "$name" ] && continue
    rows=$((rows + 1))

    # "vm1:scsi0:0" is a single virtual disk; "vm1" is the rollup across them.
    local scope="vm"
    case "$name" in
      *:scsi*) scope="vmdk" ;;
    esac

    printf "%-5s  %-30s  %9s  %9s  %9s  %8s\n" \
      "$scope" "$name" "$min" "$avg" "$max" "$col"

    if [ "$avg" = "n/a" ]; then
      nodata=$((nodata + 1))
    elif [ "$samples" != "0" ] && [ "$max" = "0.0000" ]; then
      idle=$((idle + 1))
    fi
  done < <(sort -k1,1nr "$data_file")

  echo "$rule"
  printf "  %s columns" "$rows"
  [ "$idle" -gt 0 ] && printf ", %s idle (nothing recorded)" "$idle"
  [ "$nodata" -gt 0 ] && printf ", %s with no numeric samples" "$nodata"
  printf "\n"
}

# Get the first argument passed to the script
input_file="$1"

# Check if file exists
if [[ ! -f "$input_file" ]]; then
  echo "Error: esxtop batch capture csv file '$input_file' is required!"
  exit 1
fi

# Check if file is empty
if [[ ! -s "$input_file" ]]; then
  echo "Error: The file '$input_file' is empty!"
  exit 1
fi

# Check if file is readable
if [[ ! -r "$input_file" ]]; then
  echo "Error: The file '$input_file' is not readable!"
  exit 1
fi

echo "Reading capture summary..."

# echo "-- esxtop batch capture was run on ESXi hostname: --" 
hostname=$(cat "$input_file" | tr ',' '\n' | tr -d " "  | awk -F "\\" '{print $3}' | uniq | tr '\n' ' ')


# echo "-- Extract batchmode collected datapoint iteration count --"
iteration_count=$(cat "$input_file" | tr ',' '\n' | grep -E '"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}"' | wc -l | tr -d ' ')

# echo "-- Extract batchmode range interval first 3 data points --"
first_ts=$(cat "$input_file" | tr ',' '\n' | grep -E '"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}"' | head -n 1)

# echo "-- Extract batchmode range interval last  3 data points --"
last_ts=$(cat "$input_file" | tr ',' '\n' | grep -E '"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}"' | tail -n 1)

clean_first_ts=$(echo "$first_ts" | tr -d '"')
clean_last_ts=$(echo "$last_ts" | tr -d '"')


# Convert to Unix timestamps using `date`
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  first_epoch=$(date -j -f "%m/%d/%Y %H:%M:%S" "$clean_first_ts" "+%s")
  last_epoch=$(date -j -f "%m/%d/%Y %H:%M:%S" "$clean_last_ts" "+%s")
else
  # Linux
  first_epoch=$(date -d "$clean_first_ts" "+%s")
  last_epoch=$(date -d  "$clean_last_ts" "+%s")
fi


# Calculate the difference
interval_sec=$((last_epoch - first_epoch))

# Print

# Trim surrounding whitespace and the quotes the CSV carries, so the values
# line up under a fixed label width. Emoji are deliberately absent from this
# block: they render double-width in a monospace console and knock every
# following column out of alignment.
clean_hostname=$(printf '%s' "$hostname" | awk '{$1=$1; print}')

# Humanise the interval alongside the raw seconds.
if [ "$interval_sec" -ge 60 ] 2>/dev/null; then
  interval_human=$(printf '%dm %ds' $((interval_sec / 60)) $((interval_sec % 60)))
  interval_display="${interval_sec} seconds (${interval_human})"
else
  interval_display="${interval_sec} seconds"
fi

echo
echo -e "\033[1mESXTOP BATCH MODE SUMMARY\033[0m"
echo "==================================================================="
printf "  %-18s : %s\n" "Hostname"        "$clean_hostname"
printf "  %-18s : %s\n" "Data points"     "$iteration_count"
printf "  %-18s : %s\n" "First timestamp" "$clean_first_ts"
printf "  %-18s : %s\n" "Last timestamp"  "$clean_last_ts"
printf "  %-18s : %s\n" "Duration"        "$interval_display"
echo "==================================================================="


echo -e "\n\nVIRTUAL MACHINES ON HOST DURING CAPTURE\n-------------------------------------------------------------------"
# Extract and process the header line from the file
head -n 1 "$input_file" | \
  tr ',' '\n' | \
  nl | \
  tr -d " " | \
  awk -F "\\" '{print $4}' | \
  grep VirtualDisk | \
  grep -v scsi | \
  uniq | \
  nl 

echo -e "\n\nVIRTUAL DISKS PER VM  (vm:scsiC:T)\n-------------------------------------------------------------------"
head -n 1 "$input_file" | \
  tr ',' '\n'| \
  nl | \
  tr -d " " | \
  awk -F "\\" '{print $4}' | \
  grep  VirtualDisk | \
  grep scsi  | \
  uniq  | \
  nl


# echo "-- Extract naa/nvme/ etc/ devices on host"
# head -n 1 "$input_file" | \
#    tr ',' '\n' | \
#    nl | \
#    tr -d " " | \
#    awk -F "\\" '{print $4}' | \
#    grep PhysicalDiskSCSIDevice | \
#    uniq | \
#    nl

# Non-interactive web version - automatically continue with analysis

# ============================================================
# VM VMDK STAT CATEGORIES
#
# The counter set is whatever the capture's header carries: discovery walks
# every "Virtual Disk(<vm>[:<scsiC:T>])\<counter>" column and reports one
# table per distinct counter, so a capture with N counters gets N tables.
# ============================================================
categories_file=$(mktemp)
python3 "$SCRIPT_DIR/find_column_idx.py" "$input_file" --vmdk-categories > "$categories_file"

if [ ! -s "$categories_file" ]; then
  rm -f "$categories_file"
  printf "\n\nNo VM VMDK categories found in '%s'.\n" "$input_file"
  exit 0
fi

category_count=$(cut -f1 "$categories_file" | sort -u | wc -l | tr -d ' ')
printf "\n\nFound %s VM VMDK stat categories.\n" "$category_count"

while IFS= read -r counter; do
  # Column index -> instance name, for the counter being reported on.
  unset vmdk_by_col
  declare -A vmdk_by_col
  col_numbers=()
  while IFS=$'\t' read -r vmdk_name col_idx; do
    [ -z "$col_idx" ] && continue
    col_numbers+=("$col_idx")
    vmdk_by_col["$col_idx"]="${vmdk_name:-unknown_vmdk}"
  done < <(awk -F'\t' -v counter="$counter" '$1 == counter { print $2 "\t" $3 }' "$categories_file")

  # Extract all columns of this counter in a single pass (efficient for large
  # files) and summarise them from the same pass. The statistics come from
  # series_stats() in esxtop_visualizer.extractor, so the report and the Python
  # API agree on what a missing sample means: skipped, never read as zero.
  printf "\nExtracting %s %s columns in a single pass...\n" "${#col_numbers[@]}" "$counter"
  tmp_stats=$(mktemp)
  python3 "$SCRIPT_DIR/extract_columns_batch.py" --quiet --stats "$tmp_stats" \
    "$input_file" "${col_numbers[@]}"

  # Attach the instance name, which only this loop knows, to each column's row.
  tmp_summary=$(mktemp)
  while IFS=$'\t' read -r col_num sort_key min avg max samples; do
    [ -z "$col_num" ] && continue
    vmdk_name="${vmdk_by_col[$col_num]:-unknown_vmdk}"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
      "$sort_key" "$min" "$avg" "$max" "$col_num" "$vmdk_name" "$samples" \
      >> "$tmp_summary"
  done < "$tmp_stats"
  rm -f "$tmp_stats"

  print_counter_table "$counter" "$tmp_summary"
  rm -f "$tmp_summary"
done < <(cut -f1 "$categories_file" | sort -u)

rm -f "$categories_file"
