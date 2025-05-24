
#!/bin/bash


# Get the first argument passed to the script
input_file="$1"

# Check if file exists
if [[ ! -f "$input_file" ]]; then
  echo "Error: esxtop batch capture csv file '$input_file' is required!"
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

echo "-- Future extract CPU %RDY for each VM"

