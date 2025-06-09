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


echo "-- esxtop batch capture was run on ESXi hostname: --" 
head -n 1 "$input_file" | \
  tr ',' '\n'| \
  nl | \
  tr -d " "  | \
  awk -F "\\" '{print $3}' | uniq


echo "-- Extract batchmode collected datapoint iteration count --"
cat "$input_file" | tr ',' '\n' | grep -E '"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}"' | wc -l

echo "-- Extract batchmode range interval first 3 data points --"
cat "$input_file" | tr ',' '\n' | grep -E '"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}"' | head -n 3

echo "-- Extract batchmode range interval last  3 data points --"
cat "$input_file" | tr ',' '\n' | grep -E '"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}"' | tail -n 3



echo "-- VM list that where on host during esxtop run"
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

echo "-- scsiX:X (vmdk) list for each vm --"
head -n 1 "$input_file" | \
  tr ',' '\n'| \
  nl | \
  tr -d " " | \
  awk -F "\\" '{print $4}' | \
  grep  VirtualDisk | \
  grep scsi  | \
  uniq  | \
  nl


echo "-- Extract naa/nvme/ etc/ devices on host"
head -n 1 "$input_file" | \
   tr ',' '\n' | \
   nl | \
   tr -d " " | \
   awk -F "\\" '{print $4}' | \
   grep PhysicalDiskSCSIDevice | \
   uniq | \
   nl


if [ -f "vdisk_avg_ms_write__all_col_ids" ]; then
    rm vdisk_avg_ms_write__all_col_ids
fi


echo "Creating file vdisk_avg_ms_write__all_col_ids with indexes and SCSI names..."
python3 find_column_idx.py "$input_file"| grep -E "\Average MilliSec/Write" > vdisk_avg_ms_write__all_col_ids


vdisk_avg_wr_ms_index_count=$(cat vdisk_avg_ms_write__all_col_ids | wc -l)
echo "Counting SCSI Write indexes..."
echo "SCSI Write index count: $vdisk_avg_wr_ms_index_count"


echo "Extracting data pionts for each SCSI index..."

# Create the array from command output
vdisk_wr_col_numbers=($(awk '{print $2}' vdisk_avg_ms_write__all_col_ids))

# Iterate over the array
for num in "${vdisk_wr_col_numbers[@]}"; do
  echo "Extracting index: $num data points..."
  python3 get_value_by_col_index_v2_fs.py "$input_file" "$num"
done


echo "Creating vdisk average and max write latency ms table for each vmdk..."
files=($(ls -l col_*.data | awk '{print $9}'))
for file in "${files[@]}"; do
  # awk '{ sum += $3; if ($3 > max) max = $3 } END { print "Average lat ms:", sum/NR; print "Max lat ms:", max }' "$file"
  awk '{ sum += $3; if ($3 > max) max = $3 } END { printf "File: %s  Average: %.4f  Max: %.4f\n", FILENAME, sum/NR, max }' "$file"

done




