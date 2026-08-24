# ==============================================================================
# Multi-Stage Dockerfile for Production LangGraph FastAPI Application with uv
# ==============================================================================

# --- Stage 1: Builder with uv ---
FROM python:3.12-slim AS builder

# Copy uv binary from official uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Configure virtual environment and uv flags
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Install dependencies into /opt/venv
COPY requirements.txt .
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv --no-cache -r requirements.txt


# --- Stage 2: Production Runtime ---
FROM python:3.12-slim AS runtime

# Set Python and VirtualEnv environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

# Install runtime system libraries (libpq, curl for healthcheck, nodejs & npm for MCP stdio servers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user for security
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/bash -m appuser

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Pre-download NLTK tokenizers
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)"

# Copy application source code
COPY --chown=appuser:appgroup app/ /app/app/
COPY --chown=appuser:appgroup scripts/ /app/scripts/
COPY --chown=appuser:appgroup pyproject.toml /app/

# Create directory for static assets
RUN mkdir -p /app/app/static && chown -R appuser:appgroup /app/app/static

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI application using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
