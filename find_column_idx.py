import csv
#!/usr/bin/env python3


import sys

# Ensure CSV file is provided
if len(sys.argv) < 2:
    print("Usage: python ext_v6.py <filename.csv>")
    sys.exit(1)

filename = sys.argv[1]

try:
    with open(filename, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)

        parsed_columns = []

        for col in header:
            col = col.strip('"')  # Remove quotes

            # Skip metadata like (PDH-CSV 4.0) (UTC)(0)
            if col.startswith("(PDH-CSV"):
                continue

            # Expect format: \\host\category\counter
            if col.startswith("\\\\"):
                parts = col.split("\\")[2:]  # First two elements are empty and host
                if len(parts) >= 2:
                    host = col.split("\\")[2]
                    category = parts[1]
                    counter = "\\".join(parts[2:]) if len(parts) > 2 else ""
                else:
                    host = category = counter = ""
            else:
                host = category = counter = ""

            parsed_columns.append({
                "host": host,
                "category": category,
                "counter": counter,
                "original": col
            })

        # Print first 10 parsed columns
        for i, col in enumerate(parsed_columns):
            print(f"Column {i} RAW {col['original']}' ")
            # print(f"  Host:     {col['host']}")
            # print(f"  Category: {col['category']}")
            # print(f"  Counter:  {col['counter']}")
            # print(f"  Raw:      {col['original']}")
            # print("")

except FileNotFoundError:
    print(f"Error: File '{filename}' not found.")
    sys.exit(1)
except Exception as e:
    print(f"An error occurred: {e}")
    sys.exit(1)

