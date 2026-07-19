#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GAME_SERVICE_SESSION="immortal-game-service"
RESOURCE_PACK_SESSION="immortal-resource-pack"
PAPER_SESSION="immortal-paper"
GAME_SERVICE_HEALTH_URL="http://127.0.0.1:8000/health"
GAME_SERVICE_READY_URL="http://127.0.0.1:8000/ready"
RESOURCE_PACK_URL="http://127.0.0.1:8164/build.zip"
GAME_SERVICE_WAIT_SECONDS=120
RESOURCE_PACK_WAIT_SECONDS=10
PAPER_WAIT_SECONDS=120

fail() {
  echo "Error: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

tmux_session_exists() {
  tmux has-session -t "=$1" 2>/dev/null
}

wait_for_game_service() {
  local elapsed

  for ((elapsed = 0; elapsed < GAME_SERVICE_WAIT_SECONDS; elapsed++)); do
    if curl -fsS --max-time 2 "$GAME_SERVICE_READY_URL" >/dev/null 2>&1; then
      return 0
    fi

    if ! tmux_session_exists "$GAME_SERVICE_SESSION"; then
      return 1
    fi

    sleep 1
  done

  return 1
}

wait_for_resource_pack() {
  local elapsed

  for ((elapsed = 0; elapsed < RESOURCE_PACK_WAIT_SECONDS; elapsed++)); do
    if curl -fsS --max-time 2 "$RESOURCE_PACK_URL" -o /dev/null 2>/dev/null; then
      return 0
    fi

    if ! tmux_session_exists "$RESOURCE_PACK_SESSION"; then
      return 1
    fi

    sleep 1
  done

  return 1
}

paper_port_is_open() {
  (exec 3<>/dev/tcp/127.0.0.1/25549) 2>/dev/null
}

wait_for_paper() {
  local elapsed

  for ((elapsed = 0; elapsed < PAPER_WAIT_SECONDS; elapsed++)); do
    if paper_port_is_open; then
      return 0
    fi

    if ! tmux_session_exists "$PAPER_SESSION"; then
      return 1
    fi

    sleep 1
  done

  return 1
}

show_game_service_diagnostics() {
  if tmux_session_exists "$GAME_SERVICE_SESSION"; then
    echo "Game Service tmux output:" >&2
    tmux capture-pane -p -t "$GAME_SERVICE_SESSION" -S -80 >&2 || true
  else
    echo "Game Service tmux session exited before becoming ready." >&2
  fi
}

require_command docker
require_command tmux
require_command curl
require_command python3

[[ -f "$ROOT_DIR/game-service/.env" ]] || fail \
  "game-service/.env is missing; create it from game-service/.env.example"
[[ -x "$ROOT_DIR/game-service/.venv/bin/python" ]] || fail \
  "game-service/.venv is missing; complete the Wiki first-time setup"
[[ -f "$ROOT_DIR/minecraft-nodes/main-server/paper-1.21.11-132.jar" ]] || fail \
  "Paper jar is missing: minecraft-nodes/main-server/paper-1.21.11-132.jar"
[[ -f "$ROOT_DIR/minecraft-nodes/main-server/server.properties" ]] || fail \
  "server.properties is missing; complete the Wiki first-time setup"
[[ -f "$ROOT_DIR/minecraft-nodes/main-server/plugins/BetterHud/build.zip" ]] || fail \
  "BetterHud resource pack is missing: minecraft-nodes/main-server/plugins/BetterHud/build.zip"

cd "$ROOT_DIR"

echo "Starting PostgreSQL..."
docker compose up -d --wait postgres

if tmux_session_exists "$GAME_SERVICE_SESSION"; then
  echo "Game Service is already running in tmux: $GAME_SERVICE_SESSION"
else
  if curl -fsS --max-time 2 "$GAME_SERVICE_HEALTH_URL" >/dev/null 2>&1; then
    fail "port 8000 is already serving a Game Service outside tmux session $GAME_SERVICE_SESSION"
  fi

  tmux new-session -d -s "$GAME_SERVICE_SESSION" -c "$ROOT_DIR" \
    "set -a; . ./game-service/.env; set +a; exec ./scripts/start-game-service.sh"
  echo "Started Game Service in tmux: $GAME_SERVICE_SESSION"
fi

echo "Waiting for Game Service readiness..."
if ! wait_for_game_service; then
  show_game_service_diagnostics
  fail "Game Service did not become ready; initialize or migrate the database separately, then retry"
fi

if tmux_session_exists "$RESOURCE_PACK_SESSION"; then
  echo "Resource pack server is already running in tmux: $RESOURCE_PACK_SESSION"
else
  if curl -fsS --max-time 2 "$RESOURCE_PACK_URL" -o /dev/null 2>/dev/null; then
    fail "port 8164 is already serving a resource pack outside tmux session $RESOURCE_PACK_SESSION"
  fi

  tmux new-session -d -s "$RESOURCE_PACK_SESSION" \
    -c "$ROOT_DIR/minecraft-nodes/main-server/plugins/BetterHud" \
    "exec python3 -m http.server 8164 --bind 0.0.0.0"
  echo "Started resource pack server in tmux: $RESOURCE_PACK_SESSION"
fi

echo "Waiting for resource pack server..."
wait_for_resource_pack || fail \
  "resource pack server did not become available at $RESOURCE_PACK_URL"

if tmux_session_exists "$PAPER_SESSION"; then
  echo "Paper is already running in tmux: $PAPER_SESSION"
else
  paper_port_is_open && fail \
    "port 25549 is already in use outside tmux session $PAPER_SESSION"
  tmux new-session -d -s "$PAPER_SESSION" -c "$ROOT_DIR" \
    "exec ./scripts/start-paper-server.sh"
  echo "Started Paper in tmux: $PAPER_SESSION"
fi

echo "Waiting for Paper readiness..."
if ! wait_for_paper; then
  tail -n 80 "$ROOT_DIR/minecraft-nodes/main-server/logs/latest.log" >&2 || true
  fail "Paper did not become ready; inspect minecraft-nodes/main-server/logs/latest.log"
fi

echo
echo "ImmortalMC local services are running:"
echo "  PostgreSQL:   127.0.0.1:5432"
echo "  Game Service: http://127.0.0.1:8000"
echo "  Resource pack: $RESOURCE_PACK_URL"
echo "  Paper:        127.0.0.1:25549"
echo
echo "Attach to consoles with:"
echo "  tmux attach -t $GAME_SERVICE_SESSION"
echo "  tmux attach -t $RESOURCE_PACK_SESSION"
echo "  tmux attach -t $PAPER_SESSION"
