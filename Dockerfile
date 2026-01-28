# Turtle Trading Bot Dockerfile
# Multi-stage build for production deployment

# Stage 1: Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./

# Install dependencies into virtual environment
RUN uv venv /app/.venv
RUN uv sync --frozen --no-dev

# Stage 2: Production stage
FROM python:3.12-slim as production

WORKDIR /app

# Create non-root user for security
RUN groupadd --gid 1000 turtle && \
    useradd --uid 1000 --gid turtle --shell /bin/bash --create-home turtle

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ /app/src/
COPY scripts/ /app/scripts/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data && \
    chown -R turtle:turtle /app

# Switch to non-root user
USER turtle

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command runs the daily workflow
CMD ["python", "-m", "scripts.daily_run"]
