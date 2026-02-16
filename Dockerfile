# esxtop Batch Data Analyzer
# Multi-stage build for smaller final image

FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Final stage
FROM python:3.11-slim

# Install runtime dependencies (bash, coreutils for scripts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    coreutils \
    gawk \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set matplotlib to use non-interactive backend
ENV MPLBACKEND=Agg

# Create app directory
WORKDIR /app

# Copy application code
COPY app.py .
COPY templates/ templates/
COPY scripts/ scripts/
COPY src/ src/

# Make scripts executable
RUN chmod +x scripts/*.sh

# Create directories for uploads and output
RUN mkdir -p /tmp/esxtop_uploads /tmp/esxtop_output

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Run the application
CMD ["python", "app.py"]
