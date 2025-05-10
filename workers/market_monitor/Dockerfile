FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/

# Create workers directory and copy market_monitor into it
RUN mkdir -p /app/workers && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app/logs

COPY --chown=appuser:appuser . /app/workers/market_monitor/

# Switch to non-root user
USER appuser

# Set PYTHONPATH to include the root directory
ENV PYTHONPATH=/app

# Run market monitor
CMD ["python", "-m", "workers.market_monitor.monitor"]
