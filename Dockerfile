# ═══════════════════════════════════════════════════════════════════════════
# Cloud To-Do — Dockerfile
# Base: python:3.12-slim   (~50 MB compressed)
# ═══════════════════════════════════════════════════════════════════════════

FROM python:3.12-slim AS base

# ── System packages ──────────────────────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ────────────────────────────────────────────────────────────
RUN groupadd --gid 1001 appgroup \
 && useradd  --uid 1001 --gid appgroup --no-create-home appuser

# ── Application directory ────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies (cached layer) ──────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application source ───────────────────────────────────────────────────────
COPY app/     ./app/
COPY wsgi.py  .

# ── Persistent data directory ────────────────────────────────────────────────
# Docker Compose mounts a named volume here; the directory is created now so
# the non-root user can write to it even before the volume is mounted.
RUN mkdir -p /data && chown appuser:appgroup /data

# ── Runtime user ─────────────────────────────────────────────────────────────
USER appuser

# ── Environment ──────────────────────────────────────────────────────────────
ENV DATABASE_PATH=/data/tasks.db \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

EXPOSE 5000

# ── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:5000/api/health || exit 1

# ── Start command ─────────────────────────────────────────────────────────────
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "wsgi:app"]
