#!/bin/bash


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

echo "Extracting values for summary report...please wait"

echo "Extracting hostname..."
# echo "-- esxtop batch capture was run on ESXi hostname: --" 
hostname=$(cat "$input_file" | tr ',' '\n' | tr -d " "  | awk -F "\\" '{print $3}' | uniq | tr '\n' ' ')


echo "Extracting datapoint count..."
# echo "-- Extract batchmode collected datapoint iteration count --"
iteration_count=$(cat "$input_file" | tr ',' '\n' | grep -E '"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}"' | wc -l)

echo "Extracting first timestamp..."
# echo "-- Extract batchmode range interval first 3 data points --"
first_ts=$(cat "$input_file" | tr ',' '\n' | grep -E '"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}"' | head -n 1)

echo "Extracting last timestamp..."
# echo "-- Extract batchmode range interval last  3 data points --"
last_ts=$(cat "$input_file" | tr ',' '\n' | grep -E '"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}"' | tail -n 1)

echo "Calculating time interval between first and last timestamps..."
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

echo -e "\n \033[1mESXTOP Batch Mode Summary Report\033[0m"
echo "=========================================="
echo   "🔹 Hostname                        : $hostname"
printf "🔹 Data Point Count                : %d\n" "$iteration_count"
printf "🔹 First Timestamp                 : %s\n" "$first_ts"
printf "🔹 Last  Timestamp                 : %s\n" "$last_ts"
printf "🕒 Time interval between timestamps: %s seconds\n"   "$interval_sec"
echo "=========================================="


echo -e "\n\n-- VM list that where on host during esxtop run"
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

echo -e "\n\n-- scsiX:X (ONLY vmdk) list for each vm --"
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

echo -e "\n\nDo you wish to continue with summary table of average write latency at VM level? (y/n)\n"

read -rp "Your choice: " answer

case "$answer" in
  [Yy]* )
    echo "Continuing with script..."
    # place your script logic here
    ;;
  [Nn]* )
    echo "Exiting."
    exit 1
    ;;
  * )
    echo "Invalid input. Please enter y or n."
    exit 1
    ;;
esac

echo "Creating file vdisk_avg_ms_write__all_col_ids with indexes and SCSI names..."
if [ -f "vdisk_avg_ms_write__all_col_ids" ]; then
    rm vdisk_avg_ms_write__all_col_ids
fi


python3 find_column_idx.py "$input_file"| grep -E "\Average MilliSec/Write" > vdisk_avg_ms_write__all_col_ids


vdisk_avg_wr_ms_index_count=$(cat vdisk_avg_ms_write__all_col_ids | wc -l)
echo "Counting SCSI Write indexes..."
echo "Found SCSI Write index count: $vdisk_avg_wr_ms_index_count"


echo "Creating on disk datapiont files for each SCSI index..."

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

echo -e "\n\n-- VMDK list aligned to column indices --"
for num in "${vdisk_wr_col_numbers[@]}"; do
  printf "Column %-8s  %s\n" "$num" "${vmdk_by_col[$num]}"
done
total_data_point_files=${#vdisk_wr_col_numbers[@]}
counter=0
generated_files=()

#   Iterate over the array
echo "Started extracting data points based on index list..."
for num in "${vdisk_wr_col_numbers[@]}"; do
  ((counter++))
  progress=$((counter * 100 / total_data_point_files))
  echo "Creating data files...($progress% complete)"
  python3 get_value_by_col_index_v2_fs.py "$input_file" "$num"
  generated_files+=("col_${num}.data")
done


echo "Creating vdisk average and max write latency ms table for each vmdk (sorted by average)..."
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
      if (n > 0) {
        avg = sum/n
        printf "%.10f\t%.4f\t%.4f\t%s\t%s\n", avg, avg, max, FILENAME, vmdk
      } else {
        printf "9999999999\tNaN\tNaN\t%s\t%s\n", FILENAME, vmdk
      }
    }
  ' vmdk="$vmdk_name" "$file" >> "$tmp_summary"
done

sort -k1,1n "$tmp_summary" | while IFS=$'\t' read -r avg_num avg_disp max_disp file vmdk; do
  printf "VMDK: %s  File: %s  Average: %s  Max: %s\n" "$vmdk" "$file" "$avg_disp" "$max_disp"
  if [ "$avg_disp" = "NaN" ]; then
    printf "Warning: no numeric samples in %s\n" "$file"
  fi
done
rm -f "$tmp_summary"
