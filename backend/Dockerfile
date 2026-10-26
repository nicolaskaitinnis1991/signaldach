FROM python:3.12-slim AS base

# Security: non-root user
RUN groupadd -r signaldach && useradd -r -g signaldach signaldach

WORKDIR /app

# System deps for ML and postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached layer).
# ML extras (torch/transformers, ~6 GB with CUDA wheels) are OPT-IN: the
# German sentiment pipeline falls back to its lexicon without them.
ARG INSTALL_ML=false
COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir ".[ml]"; fi

# Copy application code + migrations
COPY app/ app/
COPY alembic.ini .
COPY alembic/ alembic/

# Create data directory for SQLite (if used)
RUN mkdir -p /app/data && chown -R signaldach:signaldach /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

USER signaldach

EXPOSE 8000

# Production: run migrations then start gunicorn
CMD ["sh", "-c", "\
    python -m alembic upgrade head 2>/dev/null || true && \
    gunicorn app.main:app \
    -w ${WORKERS:-2} \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -"]
