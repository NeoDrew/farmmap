#!/bin/bash
# FarmMap local start script
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export DATABASE_URL="postgresql+asyncpg://farmmap:farmmap@localhost:5433/farmmap"
export DATABASE_URL_SYNC="postgresql+psycopg://farmmap:farmmap@localhost:5433/farmmap"
export REDIS_URL="redis://localhost:6379/0"

# Ensure infrastructure is up
docker compose up -d

# Wait for DB
echo "Waiting for database..."
until docker exec farmmap-db-1 pg_isready -U farmmap -q 2>/dev/null; do sleep 1; done

# Run migrations
uv run alembic upgrade head

# Start API (serves frontend + API on port 8000)
echo "Starting FarmMap on http://localhost:8000"
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
