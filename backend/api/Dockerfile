# ============================================================
# Waypoint Backend — Dockerfile
# Python 3.12-slim for a small, production-appropriate image
# ============================================================

FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create a non-root user for security
RUN addgroup --system waypoint && adduser --system --ingroup waypoint waypoint

WORKDIR /app

# Install system dependencies required by some Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cache friendly)
COPY requirements.txt .
RUN pip install --default-timeout=100 --retries 5 --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Change ownership to non-root user
RUN chown -R waypoint:waypoint /app
USER waypoint

# Expose the application port
EXPOSE 8000

# Health check — used by Docker and AWS load balancers
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn
# Configuration (PORT, LOG_LEVEL, ENVIRONMENT) is passed via environment variables
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
