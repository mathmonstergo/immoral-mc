#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/game-service"

cd "$SERVICE_DIR"

if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -e '.[dev]'
exec .venv/bin/python -m uvicorn immortal_mmo.main:app --host 127.0.0.1 --port 8000
