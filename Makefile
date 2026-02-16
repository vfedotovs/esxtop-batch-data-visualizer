# esxtop-batch-data-visualizer Makefile
# Variables - can be overridden on command line
CSV_FILE ?= esxtop_batch_data.csv
COL_ID ?= 51446
SEARCH_PATTERN ?= scsi.*Write
DATA_FILE = $(basename $(CSV_FILE))_col_$(COL_ID).data
SCALE ?= 1.0
VENV_DIR = .venv
PYTHON = $(VENV_DIR)/bin/python3

.PHONY: help describe find-column extract plot plot-save all clean venv clean-venv

# Default target
help:
	@echo "esxtop-batch-data-visualizer Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make venv                                   - Set up Python virtual environment"
	@echo "  make describe CSV_FILE=<file>              - Describe esxtop CSV file"
	@echo "  make find-column CSV_FILE=<file> SEARCH_PATTERN=<pattern>"
	@echo "                                              - Find column index by pattern"
	@echo "  make extract CSV_FILE=<file> COL_ID=<id>   - Extract time series data"
	@echo "  make plot DATA_FILE=<file> [SCALE=<n>]     - Plot time series data (interactive)"
	@echo "  make plot-save DATA_FILE=<file> [SCALE=<n>] - Save chart to PNG file"
	@echo "  make all CSV_FILE=<file> COL_ID=<id>       - Run extract and plot"
	@echo "  make clean                                 - Remove generated files"
	@echo "  make clean-venv                            - Remove virtual environment"
	@echo ""
	@echo "Example workflow:"
	@echo "  0. make venv  (first time setup)"
	@echo "  1. make describe CSV_FILE=esxtop_batch_data.csv"
	@echo "  2. make find-column CSV_FILE=esxtop_batch_data.csv SEARCH_PATTERN='scsi.*Write'"
	@echo "  3. make extract CSV_FILE=esxtop_batch_data.csv COL_ID=51446"
	@echo "  4. make plot DATA_FILE=esxtop_batch_data_col_51446.data"
	@echo "  Or simply: make all CSV_FILE=esxtop_batch_data.csv COL_ID=51446"
	@echo ""
	@echo "Current settings:"
	@echo "  CSV_FILE=$(CSV_FILE)"
	@echo "  COL_ID=$(COL_ID)"
	@echo "  SEARCH_PATTERN=$(SEARCH_PATTERN)"
	@echo "  DATA_FILE=$(DATA_FILE)"

# Set up virtual environment using uv
venv:
	@echo "Setting up Python virtual environment using uv..."
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "Error: uv is not installed. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	uv venv $(VENV_DIR)
	uv pip install -r requirements.txt
	@echo "Virtual environment created at $(VENV_DIR)"
	@echo "Dependencies installed successfully!"

# Step 2: Describe collected batch data from CSV file
describe:
	@echo "Describing esxtop batch data from $(CSV_FILE)..."
	./scripts/describe_extop.sh $(CSV_FILE)

# Step 3: Extract data column index id of interest
find-column: venv
	@echo "Finding column index matching pattern: $(SEARCH_PATTERN)"
	$(PYTHON) ./scripts/find_column_idx.py $(CSV_FILE) | grep -E -B 4 "$(SEARCH_PATTERN)"

# Step 4: Extract time series data from the chosen column
extract: venv
	@echo "Extracting time series data from column $(COL_ID)..."
	$(PYTHON) scripts/extract_column.py $(CSV_FILE) $(COL_ID)
	@echo "Data saved to $(DATA_FILE)"

# Step 5: Plot the time series data (interactive)
plot: venv
	@echo "Plotting time series data from $(DATA_FILE)..."
	$(PYTHON) scripts/visualize_data.py $(DATA_FILE) --scale $(SCALE)

# Step 5 (alt): Save chart to PNG file
plot-save: venv
	@echo "Saving chart from $(DATA_FILE) to PNG..."
	$(PYTHON) scripts/visualize_data.py $(DATA_FILE) --scale $(SCALE) --output esxtop_col_$(COL_ID).png --no-show

# Run extract and plot together
all: extract plot

# Cleanup generated files
clean:
	@echo "Cleaning up generated files..."
	@find . -maxdepth 1 -name "*.data" -type f -exec rm -v {} \;
	@find . -maxdepth 1 -name "*_col_*.png" -type f -exec rm -v {} \;
	@echo "Cleanup complete!"

# Remove virtual environment
clean-venv:
	@echo "Removing virtual environment..."
	@rm -rf $(VENV_DIR)
	@echo "Virtual environment removed!"
