# ============================================================
# Waypoint Backend — Root Dockerfile for Cloud Deployments (Render / Railway)
# Python 3.12-slim
# ============================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system waypoint && adduser --system --ingroup waypoint waypoint

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from backend/api
COPY backend/api/requirements.txt .
RUN pip install --default-timeout=100 --retries 5 --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/api/app/ ./app/

RUN chown -R waypoint:waypoint /app
USER waypoint

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info"]
