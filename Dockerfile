# esxtop Batch Data Analyzer
# Multi-stage build for smaller final image

FROM python:3.11-slim AS builder

WORKDIR /build

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies (all deps ship wheels, so no compiler is needed)
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

# Set matplotlib to use non-interactive backend, with a writable config dir
# (the app user has no writable home, so the default ~/.config path fails)
ENV MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib

# Run as an unprivileged user
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin esxtop

# Create app directory
WORKDIR /app

# Copy application code
COPY app.py .
COPY templates/ templates/
COPY scripts/ scripts/
COPY src/ src/

# Make scripts executable
RUN chmod +x scripts/*.sh

# Create the output directory owned by the app user. A named volume mounted
# here inherits this ownership on first use.
RUN mkdir -p /tmp/esxtop_output /tmp/matplotlib \
    && chown -R esxtop:esxtop /tmp/esxtop_output /tmp/matplotlib

USER esxtop

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Run the application under gunicorn. Sync workers handle one request each, so
# the per-request os.chdir() in app.py cannot race between concurrent uploads.
# The timeout exceeds the 300s analysis timeout enforced inside app.py.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "600", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
