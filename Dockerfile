# ==============================================================================
# FinTrack — Production Backend & Workers Dockerfile
# Multi-stage build for minimal attack surface and small image size
# ==============================================================================

# Stage 1: Build Dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Final Minimal Runtime
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime PostgreSQL client library & curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user
RUN groupadd -r fintrack && useradd -r -g fintrack -d /home/fintrack -m -s /bin/bash fintrack

# Copy installed Python packages from builder
COPY --from=builder /root/.local /home/fintrack/.local

ENV PATH="/home/fintrack/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app"

# Copy application source code
COPY --chown=fintrack:fintrack . /app

# Ensure live Excel workbook directory exists with full write permissions
RUN mkdir -p /app/data && chown -R fintrack:fintrack /app/data

USER fintrack

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
