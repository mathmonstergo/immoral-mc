#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/game-service"

cd "$SERVICE_DIR"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must be set before starting game-service" >&2
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "game-service/.venv is missing; complete the Wiki first-time setup before starting" >&2
  exit 1
fi

exec .venv/bin/python -m uvicorn immortal_mmo.entrypoint:app --host 127.0.0.1 --port 8000
