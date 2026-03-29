#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting BRAIN 3.0 API..."
exec uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"
