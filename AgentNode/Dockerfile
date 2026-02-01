# ==============================================================================
# BUILDER STAGE
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/

# Create virtual environment using uv
RUN /uv/bin/uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies using uv
COPY requirements.txt .
RUN /uv/bin/uv pip install --no-cache -r requirements.txt

# Clean up to reduce size
RUN find /opt/venv -name '*.so' -type f -exec strip --strip-unneeded '{}' + 2>/dev/null || true && \
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null && \
    find /opt/venv -name "*.pyc" -delete 2>/dev/null

# ==============================================================================
# RUNTIME STAGE
# ==============================================================================
FROM python:3.12-slim

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Run the application
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8025"]
