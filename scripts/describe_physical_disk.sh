#!/bin/bash

# Physical Disk SCSI Device Analysis Script
# Extracts and analyzes Physical Disk SCSI Device (naa.*) metrics
# Creates tables for Average Driver MilliSec/Read and Average Driver MilliSec/Write

# Resolve script directory for reliable Python script paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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

# Render a physical-disk latency summary as a fixed-width table, worst first.
# Input columns: sort_key <TAB> avg <TAB> max <TAB> column <TAB> device <TAB> samples
print_pdisk_table() {
  local title="$1"
  local data_file="$2"
  local rule="-------------------------------------------------------------------"

  echo
  echo -e "\033[1m${title}\033[0m"
  echo "$rule"
  printf "%-38s  %9s  %9s  %8s\n" "DEVICE" "AVG ms" "MAX ms" "COLUMN"
  echo "$rule"

  local rows=0
  local nodata=0
  while IFS=$'\t' read -r sort_key avg max col device samples; do
    [ -z "$device" ] && continue
    rows=$((rows + 1))
    printf "%-38s  %9s  %9s  %8s\n" "$device" "$avg" "$max" "$col"
    [ "$avg" = "n/a" ] && nodata=$((nodata + 1))
  done < <(sort -k1,1nr "$data_file")

  echo "$rule"
  printf "  %s devices" "$rows"
  [ "$nodata" -gt 0 ] && printf ", %s with no numeric samples" "$nodata"
  printf "\n"
}

echo -e "\n\033[1mPhysical Disk SCSI Device Analysis (naa.*)\033[0m"
echo "=========================================="

# ============================================================
# List all Physical Disk SCSI Devices (naa.60050*)
# ============================================================
echo -e "\nExtracting Physical Disk SCSI Device list (naa.*)..."

# Get unique naa.* devices from header
pdisk_list=$(head -n 1 "$input_file" | \
  tr ',' '\n' | \
  grep -i "Physical Disk SCSI Device" | \
  grep -i "naa\." | \
  sed -n 's/.*Physical Disk SCSI Device(\([^)]*\)).*/\1/p' | \
  sort -u)

pdisk_count=$(echo "$pdisk_list" | grep -c .)

echo -e "\n\033[1mPhysical Disk SCSI Devices Found: $pdisk_count\033[0m"
echo "------------------------------------------"
echo "$pdisk_list" | nl
echo "------------------------------------------"

# ============================================================
# PHYSICAL DISK READ LATENCY TABLE (Average Driver MilliSec/Read)
# ============================================================
echo -e "\n\n=========================================="
echo "Creating Physical Disk Read Latency Table..."
echo "=========================================="

if [ -f "pdisk_avg_driver_ms_read__all_col_ids" ]; then
    rm pdisk_avg_driver_ms_read__all_col_ids
fi

# Find columns matching Physical Disk SCSI Device with naa.* and Average Driver MilliSec/Read
python3 "$SCRIPT_DIR/find_column_idx.py" "$input_file" | \
  grep -E "Physical Disk SCSI Device.*naa\." | \
  grep -E "Average Driver MilliSec/Read" > pdisk_avg_driver_ms_read__all_col_ids

pdisk_avg_rd_ms_index_count=$(cat pdisk_avg_driver_ms_read__all_col_ids | wc -l)
printf "Found %s physical disk read latency columns.\n" "$pdisk_avg_rd_ms_index_count"

if [ "$pdisk_avg_rd_ms_index_count" -eq 0 ]; then
  echo "Warning: No Physical Disk SCSI Device (naa.*) Read latency columns found."
else

  # Create arrays and mapping from column index to device name for READ
  declare -A pdisk_by_col_read
  pdisk_rd_col_numbers=()
  while IFS= read -r line; do
    col_idx=$(printf '%s\n' "$line" | awk '{print $2}')
    # Extract device name from "Physical Disk SCSI Device(naa.60050...)"
    device_name=$(printf '%s\n' "$line" | sed -n 's/.*Physical Disk SCSI Device(\([^)]*\))\\Average.*/\1/p')
    if [ -n "$col_idx" ]; then
      pdisk_rd_col_numbers+=("$col_idx")
      if [ -n "$device_name" ]; then
        pdisk_by_col_read["$col_idx"]="$device_name"
      else
        pdisk_by_col_read["$col_idx"]="unknown_device"
      fi
    fi
  done < pdisk_avg_driver_ms_read__all_col_ids


  total_pdisk_read_files=${#pdisk_rd_col_numbers[@]}
  generated_files_pdisk_read=()

  # Extract all READ columns in a single pass
  echo "Extracting $total_pdisk_read_files columns in a single pass..."
  python3 "$SCRIPT_DIR/extract_columns_batch.py" --quiet "$input_file" "${pdisk_rd_col_numbers[@]}"

  # Build generated_files array
  for num in "${pdisk_rd_col_numbers[@]}"; do
    generated_files_pdisk_read+=("col_${num}.data")
  done

  tmp_summary_pdisk_read=$(mktemp)
  for file in "${generated_files_pdisk_read[@]}"; do
    col_num=$(printf '%s\n' "$file" | sed -n 's/.*col_\([0-9][0-9]*\)\.data/\1/p')
    device_name="${pdisk_by_col_read[$col_num]:-unknown_device}"
    awk '
      $3 ~ /^-?[0-9]+(\.[0-9]+)?$/ {
        sum += $3
        if (!seen || $3 > max) { max = $3; seen = 1 }
        n++
      }
      END {
        if (n > 0) {
          avg = sum/n
          printf "%.10f\t%.4f\t%.4f\t%s\t%s\t%s\n", avg, avg, max, col, device, n
        } else {
          printf "-1\tn/a\tn/a\t%s\t%s\t0\n", col, device
        }
      }
    ' device="$device_name" col="$col_num" "$file" >> "$tmp_summary_pdisk_read"
  done

  print_pdisk_table "PHYSICAL DISK READ LATENCY  (Average Driver MilliSec/Read)" "$tmp_summary_pdisk_read"
  rm -f "$tmp_summary_pdisk_read"
fi

# ============================================================
# PHYSICAL DISK WRITE LATENCY TABLE (Average Driver MilliSec/Write)
# ============================================================
echo -e "\n\n=========================================="
echo "Creating Physical Disk Write Latency Table..."
echo "=========================================="

if [ -f "pdisk_avg_driver_ms_write__all_col_ids" ]; then
    rm pdisk_avg_driver_ms_write__all_col_ids
fi

# Find columns matching Physical Disk SCSI Device with naa.* and Average Driver MilliSec/Write
python3 "$SCRIPT_DIR/find_column_idx.py" "$input_file" | \
  grep -E "Physical Disk SCSI Device.*naa\." | \
  grep -E "Average Driver MilliSec/Write" > pdisk_avg_driver_ms_write__all_col_ids

pdisk_avg_wr_ms_index_count=$(cat pdisk_avg_driver_ms_write__all_col_ids | wc -l)
printf "Found %s physical disk write latency columns.\n" "$pdisk_avg_wr_ms_index_count"

if [ "$pdisk_avg_wr_ms_index_count" -eq 0 ]; then
  echo "Warning: No Physical Disk SCSI Device (naa.*) Write latency columns found."
else

  # Create arrays and mapping from column index to device name for WRITE
  declare -A pdisk_by_col_write
  pdisk_wr_col_numbers=()
  while IFS= read -r line; do
    col_idx=$(printf '%s\n' "$line" | awk '{print $2}')
    # Extract device name from "Physical Disk SCSI Device(naa.60050...)"
    device_name=$(printf '%s\n' "$line" | sed -n 's/.*Physical Disk SCSI Device(\([^)]*\))\\Average.*/\1/p')
    if [ -n "$col_idx" ]; then
      pdisk_wr_col_numbers+=("$col_idx")
      if [ -n "$device_name" ]; then
        pdisk_by_col_write["$col_idx"]="$device_name"
      else
        pdisk_by_col_write["$col_idx"]="unknown_device"
      fi
    fi
  done < pdisk_avg_driver_ms_write__all_col_ids


  total_pdisk_write_files=${#pdisk_wr_col_numbers[@]}
  generated_files_pdisk_write=()

  # Extract all WRITE columns in a single pass
  echo "Extracting $total_pdisk_write_files columns in a single pass..."
  python3 "$SCRIPT_DIR/extract_columns_batch.py" --quiet "$input_file" "${pdisk_wr_col_numbers[@]}"

  # Build generated_files array
  for num in "${pdisk_wr_col_numbers[@]}"; do
    generated_files_pdisk_write+=("col_${num}.data")
  done

  tmp_summary_pdisk_write=$(mktemp)
  for file in "${generated_files_pdisk_write[@]}"; do
    col_num=$(printf '%s\n' "$file" | sed -n 's/.*col_\([0-9][0-9]*\)\.data/\1/p')
    device_name="${pdisk_by_col_write[$col_num]:-unknown_device}"
    awk '
      $3 ~ /^-?[0-9]+(\.[0-9]+)?$/ {
        sum += $3
        if (!seen || $3 > max) { max = $3; seen = 1 }
        n++
      }
      END {
        if (n > 0) {
          avg = sum/n
          printf "%.10f\t%.4f\t%.4f\t%s\t%s\t%s\n", avg, avg, max, col, device, n
        } else {
          printf "-1\tn/a\tn/a\t%s\t%s\t0\n", col, device
        }
      }
    ' device="$device_name" col="$col_num" "$file" >> "$tmp_summary_pdisk_write"
  done

  print_pdisk_table "PHYSICAL DISK WRITE LATENCY  (Average Driver MilliSec/Write)" "$tmp_summary_pdisk_write"
  rm -f "$tmp_summary_pdisk_write"
fi

echo -e "\n\033[1mPhysical Disk Analysis Complete!\033[0m"
