# Tezaver Cloud Service
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ src/
COPY coin_cells/ coin_cells/

# Set environment
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Create output directories
RUN mkdir -p out/cloud_runs data/cloud

# Default command
ENTRYPOINT ["python", "-m", "tezaver.cloud.run_live"]
CMD ["--symbols", "BTCUSDT", "--tf", "15m", "--mode", "PAPER", "--max-bars", "100"]

# Healthcheck - write heartbeat file
HEALTHCHECK --interval=30s --timeout=3s \
    CMD test -f /app/data/cloud/heartbeat.txt || exit 1
