#!/bin/bash


# Resolve script directory for reliable Python script paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Render a latency summary as a fixed-width table, worst first.
#
# Input is the tab-separated scratch file built by the callers:
#   sort_key <TAB> avg <TAB> max <TAB> column <TAB> name <TAB> sample_count
#
# Rows are sorted by average descending, so the disk that needs attention is
# the first thing read rather than the last. A capture mixes VM-level rollups
# with the per-VMDK counters underneath them, and the two are easy to confuse
# when the numbers repeat, so SCOPE labels which is which.
print_latency_table() {
  local title="$1"
  local data_file="$2"
  local rule="-------------------------------------------------------------------"

  echo
  echo -e "\033[1m${title}\033[0m"
  echo "$rule"
  printf "%-5s  %-30s  %9s  %9s  %8s\n" "SCOPE" "VMDK" "AVG ms" "MAX ms" "COLUMN"
  echo "$rule"

  local rows=0
  local idle=0
  local nodata=0
  while IFS=$'\t' read -r sort_key avg max col name samples; do
    [ -z "$name" ] && continue
    rows=$((rows + 1))

    # "vm1:scsi0:0" is a single virtual disk; "vm1" is the rollup across them.
    local scope="vm"
    case "$name" in
      *:scsi*) scope="vmdk" ;;
    esac

    printf "%-5s  %-30s  %9s  %9s  %8s\n" "$scope" "$name" "$avg" "$max" "$col"

    if [ "$avg" = "n/a" ]; then
      nodata=$((nodata + 1))
    elif [ "$samples" != "0" ] && [ "$max" = "0.0000" ]; then
      idle=$((idle + 1))
    fi
  done < <(sort -k1,1nr "$data_file")

  echo "$rule"
  printf "  %s counters" "$rows"
  [ "$idle" -gt 0 ] && printf ", %s idle (no latency recorded)" "$idle"
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

if [ -f "vdisk_avg_ms_write__all_col_ids" ]; then
    rm vdisk_avg_ms_write__all_col_ids
fi


python3 "$SCRIPT_DIR/find_column_idx.py" "$input_file"| grep -E "\Average MilliSec/Write" > vdisk_avg_ms_write__all_col_ids


vdisk_avg_wr_ms_index_count=$(cat vdisk_avg_ms_write__all_col_ids | wc -l | tr -d ' ')
printf "\nFound %s write latency columns.\n" "$vdisk_avg_wr_ms_index_count"



# Create arrays and mapping from column index to vmdk
declare -A vmdk_by_col
vdisk_wr_col_numbers=()
while IFS= read -r line; do
  col_idx=$(printf '%s\n' "$line" | awk '{print $2}')
  vmdk_name=$(printf '%s\n' "$line" | sed -n 's/.*Virtual Disk(\(.*\))\\Average.*/\1/p')
  if [ -n "$col_idx" ]; then
    vdisk_wr_col_numbers+=("$col_idx")
    if [ -n "$vmdk_name" ]; then
      vmdk_by_col["$col_idx"]="$vmdk_name"
    else
      vmdk_by_col["$col_idx"]="unknown_vmdk"
    fi
  fi
done < vdisk_avg_ms_write__all_col_ids

# The column-index mapping is debugging detail: every index it prints also
# appears in the summary table below, next to the number that matters.
total_data_point_files=${#vdisk_wr_col_numbers[@]}
counter=0
generated_files=()

#   Extract all columns in a single pass (efficient for large files)
printf "Extracting %s write columns in a single pass...\n" "$total_data_point_files"
python3 "$SCRIPT_DIR/extract_columns_batch.py" --quiet "$input_file" "${vdisk_wr_col_numbers[@]}"

# Build generated_files array
for num in "${vdisk_wr_col_numbers[@]}"; do
  generated_files+=("col_${num}.data")
done


tmp_summary=$(mktemp)
for file in "${generated_files[@]}"; do
  col_num=$(printf '%s\n' "$file" | sed -n 's/.*col_\([0-9][0-9]*\)\.data/\1/p')
  vmdk_name="${vmdk_by_col[$col_num]:-unknown_vmdk}"
  awk '
    $3 ~ /^-?[0-9]+(\.[0-9]+)?$/ {
      sum += $3
      if (!seen || $3 > max) { max = $3; seen = 1 }
      n++
    }
    END {
      # Sort key first. Columns with no numeric samples get -1 so they land at
      # the bottom of a descending sort instead of impersonating the worst.
      if (n > 0) {
        avg = sum/n
        printf "%.10f\t%.4f\t%.4f\t%s\t%s\t%s\n", avg, avg, max, col, vmdk, n
      } else {
        printf "-1\tn/a\tn/a\t%s\t%s\t0\n", col, vmdk
      }
    }
  ' vmdk="$vmdk_name" col="$col_num" "$file" >> "$tmp_summary"
done

print_latency_table "SCSI WRITE LATENCY  (Average MilliSec/Write)" "$tmp_summary"
rm -f "$tmp_summary"

# ============================================================
# SCSI READ LATENCY TABLE (Average MilliSec/Read)
# ============================================================
if [ -f "vdisk_avg_ms_read__all_col_ids" ]; then
    rm vdisk_avg_ms_read__all_col_ids
fi

python3 "$SCRIPT_DIR/find_column_idx.py" "$input_file"| grep -E "\Average MilliSec/Read" > vdisk_avg_ms_read__all_col_ids

vdisk_avg_rd_ms_index_count=$(cat vdisk_avg_ms_read__all_col_ids | wc -l | tr -d ' ')
printf "\n\nFound %s read latency columns.\n" "$vdisk_avg_rd_ms_index_count"

# Create arrays and mapping from column index to vmdk for READ
declare -A vmdk_by_col_read
vdisk_rd_col_numbers=()
while IFS= read -r line; do
  col_idx=$(printf '%s\n' "$line" | awk '{print $2}')
  vmdk_name=$(printf '%s\n' "$line" | sed -n 's/.*Virtual Disk(\(.*\))\\Average.*/\1/p')
  if [ -n "$col_idx" ]; then
    vdisk_rd_col_numbers+=("$col_idx")
    if [ -n "$vmdk_name" ]; then
      vmdk_by_col_read["$col_idx"]="$vmdk_name"
    else
      vmdk_by_col_read["$col_idx"]="unknown_vmdk"
    fi
  fi
done < vdisk_avg_ms_read__all_col_ids

total_data_point_files_read=${#vdisk_rd_col_numbers[@]}
generated_files_read=()

# Extract all READ columns in a single pass (efficient for large files)
printf "Extracting %s read columns in a single pass...\n" "$total_data_point_files_read"
python3 "$SCRIPT_DIR/extract_columns_batch.py" --quiet "$input_file" "${vdisk_rd_col_numbers[@]}"

# Build generated_files_read array
for num in "${vdisk_rd_col_numbers[@]}"; do
  generated_files_read+=("col_${num}.data")
done

tmp_summary_read=$(mktemp)
for file in "${generated_files_read[@]}"; do
  col_num=$(printf '%s\n' "$file" | sed -n 's/.*col_\([0-9][0-9]*\)\.data/\1/p')
  vmdk_name="${vmdk_by_col_read[$col_num]:-unknown_vmdk}"
  awk '
    $3 ~ /^-?[0-9]+(\.[0-9]+)?$/ {
      sum += $3
      if (!seen || $3 > max) { max = $3; seen = 1 }
      n++
    }
    END {
      if (n > 0) {
        avg = sum/n
        printf "%.10f\t%.4f\t%.4f\t%s\t%s\t%s\n", avg, avg, max, col, vmdk, n
      } else {
        printf "-1\tn/a\tn/a\t%s\t%s\t0\n", col, vmdk
      }
    }
  ' vmdk="$vmdk_name" col="$col_num" "$file" >> "$tmp_summary_read"
done

print_latency_table "SCSI READ LATENCY  (Average MilliSec/Read)" "$tmp_summary_read"
rm -f "$tmp_summary_read"
