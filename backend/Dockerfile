# Development image for the Phase 2 Django foundation.
# Production image hardening will be finalized with the deployment baseline.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
RUN python -m pip install --upgrade pip && pip install -e ".[dev]"

COPY . .

EXPOSE 8000
