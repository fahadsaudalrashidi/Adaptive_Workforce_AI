# Adaptive Workforce AI — Production Dockerfile
# Local deployment only unless cloud infrastructure is configured.
# No real secrets, no hardcoded credentials, no production claims.
#
# Build: docker build -t adaptive-workforce-ai .
# Run:   docker-compose up

FROM python:3.11-slim

# ── System dependencies ────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user (security best practice) ────────────────────────────────
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# ── Dependencies (layer-cached) ────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application code ────────────────────────────────────────────────────────
COPY --chown=appuser:appuser . .

# ── Switch to non-root user ────────────────────────────────────────────────
USER appuser

# ── Data directories ────────────────────────────────────────────────────────
RUN mkdir -p data/uploads data/outputs data/artifacts data/audit_logs saved_models

# ── Port (API) ──────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Healthcheck ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# ── Entry point ─────────────────────────────────────────────────────────────
# In production: replace with a proper process manager (gunicorn + uvicorn workers)
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
