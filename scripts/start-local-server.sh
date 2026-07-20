#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GAME_SERVICE_SESSION="immortal-game-service"
RESOURCE_PACK_SESSION="immortal-resource-pack"
PAPER_SESSION="immortal-paper"
GAME_SERVICE_HEALTH_URL="http://127.0.0.1:8000/health"
GAME_SERVICE_READY_URL="http://127.0.0.1:8000/ready"
RESOURCE_PACK_PORT=8164
RESOURCE_PACK_PUBLIC_URL="${RESOURCE_PACK_PUBLIC_URL:-}"
RESOURCE_PACK_HEALTH_URL="http://127.0.0.1:${RESOURCE_PACK_PORT}/build.zip"
RESOURCE_PACK_ZIP="$ROOT_DIR/minecraft-nodes/main-server/plugins/BetterHud/build.zip"
RESOURCE_PACK_PUBLIC_DIR="$ROOT_DIR/minecraft-nodes/main-server/.immortal-resource-pack"
SERVER_PROPERTIES="$ROOT_DIR/minecraft-nodes/main-server/server.properties"
GAME_SERVICE_WAIT_SECONDS=120
RESOURCE_PACK_WAIT_SECONDS=10
PAPER_WAIT_SECONDS=120
RESOURCE_PACK_PROPERTIES_CHANGED=0

fail() {
  echo "Error: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

derive_resource_pack_public_url() {
  local address

  address="$(hostname -I 2>/dev/null | awk '
    {
      for (index = 1; index <= NF; index++) {
        if ($index ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ && $index !~ /^127\./) {
          print $index
          exit
        }
      }
    }
  ')"
  [[ -n "$address" ]] || fail \
    "could not derive a client-reachable resource-pack address; set RESOURCE_PACK_PUBLIC_URL"
  printf 'http://%s:%s/build.zip\n' "$address" "$RESOURCE_PACK_PORT"
}

validate_resource_pack_public_url() {
  [[ "$RESOURCE_PACK_PUBLIC_URL" != *[[:space:]]* ]] || fail \
    "RESOURCE_PACK_PUBLIC_URL must not contain whitespace"
  [[ "$RESOURCE_PACK_PUBLIC_URL" != *\\* ]] || fail \
    "RESOURCE_PACK_PUBLIC_URL must not contain backslashes"
  if ! python3 - "$RESOURCE_PACK_PUBLIC_URL" <<'PY'
import sys
from urllib.parse import urlsplit

try:
    parsed = urlsplit(sys.argv[1])
    port = parsed.port
except ValueError:
    raise SystemExit(1)

valid = (
    parsed.scheme in {"http", "https"}
    and parsed.hostname is not None
    and parsed.username is None
    and parsed.password is None
    and parsed.query == ""
    and parsed.fragment == ""
    and parsed.path.endswith("/build.zip")
    and (port is None or 1 <= port <= 65535)
)
raise SystemExit(0 if valid else 1)
PY
  then
    fail "RESOURCE_PACK_PUBLIC_URL must be a valid HTTP(S) URL ending with /build.zip"
  fi
}

compute_resource_pack_sha1() {
  if command -v sha1sum >/dev/null 2>&1; then
    sha1sum "$RESOURCE_PACK_ZIP" | awk '{print $1}'
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 1 "$RESOURCE_PACK_ZIP" | awk '{print $1}'
    return
  fi
  fail "sha1sum or shasum is required"
}

sync_resource_pack_properties() {
  local sha1="$1"
  local temporary

  temporary="$(mktemp "${SERVER_PROPERTIES}.tmp.XXXXXX")"
  if ! awk \
    -v resource_pack_url="$RESOURCE_PACK_PUBLIC_URL" \
    -v resource_pack_sha1="$sha1" '
      BEGIN { url_written = 0; sha1_written = 0 }
      {
        property = $0
        sub(/^[[:space:]]*/, "", property)
      }
      property ~ /^resource-pack([[:space:]]*[:=]|[[:space:]]+)/ {
        if (!url_written) {
          print "resource-pack=" resource_pack_url
          url_written = 1
        }
        next
      }
      property ~ /^resource-pack-sha1([[:space:]]*[:=]|[[:space:]]+)/ {
        if (!sha1_written) {
          print "resource-pack-sha1=" resource_pack_sha1
          sha1_written = 1
        }
        next
      }
      { print }
      END {
        if (!url_written) print "resource-pack=" resource_pack_url
        if (!sha1_written) print "resource-pack-sha1=" resource_pack_sha1
      }
    ' "$SERVER_PROPERTIES" > "$temporary"; then
    rm "$temporary"
    fail "could not update resource-pack properties"
  fi

  if cmp -s "$SERVER_PROPERTIES" "$temporary"; then
    rm "$temporary"
    RESOURCE_PACK_PROPERTIES_CHANGED=0
  else
    chmod --reference="$SERVER_PROPERTIES" "$temporary"
    mv "$temporary" "$SERVER_PROPERTIES"
    RESOURCE_PACK_PROPERTIES_CHANGED=1
  fi
}

prepare_resource_pack_public_dir() {
  local unexpected

  mkdir -p "$RESOURCE_PACK_PUBLIC_DIR"
  unexpected="$(
    find "$RESOURCE_PACK_PUBLIC_DIR" -mindepth 1 -maxdepth 1 \
      ! -name build.zip -print -quit
  )"
  [[ -z "$unexpected" ]] || fail \
    "resource-pack public directory contains an unexpected file: $unexpected"
  ln -sfn "$RESOURCE_PACK_ZIP" "$RESOURCE_PACK_PUBLIC_DIR/build.zip"
  [[ "$(readlink -f "$RESOURCE_PACK_PUBLIC_DIR/build.zip")" == \
    "$(readlink -f "$RESOURCE_PACK_ZIP")" ]] || fail \
    "resource-pack public link does not resolve to the BetterHud ZIP"
}

configure_resource_pack() {
  local sha1

  if [[ -z "$RESOURCE_PACK_PUBLIC_URL" ]]; then
    RESOURCE_PACK_PUBLIC_URL="$(derive_resource_pack_public_url)"
  fi
  validate_resource_pack_public_url
  sha1="$(compute_resource_pack_sha1)"
  sync_resource_pack_properties "$sha1"

  echo "Configured BetterHud resource pack:"
  echo "  Client URL: $RESOURCE_PACK_PUBLIC_URL"
  echo "  SHA-1:      $sha1"
}

tmux_session_exists() {
  tmux has-session -t "=$1" 2>/dev/null
}

resource_pack_session_matches_contract() {
  local expected_command
  local pane_id
  local pane_ids
  local start_command

  pane_ids="$(
    tmux list-panes -s -t "=${RESOURCE_PACK_SESSION}" \
      -F '#{pane_id}' 2>/dev/null
  )" || return 1
  [[ -n "$pane_ids" && "$pane_ids" != *$'\n'* ]] || return 1
  pane_id="$pane_ids"
  start_command="$(
    tmux display-message -p -t "$pane_id" '#{pane_start_command}' 2>/dev/null
  )" || return 1
  printf -v expected_command \
    'exec python3 -m http.server %q --bind 0.0.0.0 --directory %q' \
    "$RESOURCE_PACK_PORT" "$RESOURCE_PACK_PUBLIC_DIR"
  [[ "$start_command" == "$expected_command" \
    || "$start_command" == "\"$expected_command\"" ]]
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
    if curl -fsS --max-time 2 "$RESOURCE_PACK_HEALTH_URL" -o /dev/null 2>/dev/null; then
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

main() {
  local resource_pack_command

  require_command docker
  require_command tmux
  require_command curl
  require_command python3
  require_command hostname
  require_command awk
  require_command cmp
  require_command chmod
  require_command find
  require_command ln
  require_command mkdir
  require_command mktemp
  require_command readlink

  [[ -f "$ROOT_DIR/game-service/.env" ]] || fail \
    "game-service/.env is missing; create it from game-service/.env.example"
  [[ -x "$ROOT_DIR/game-service/.venv/bin/python" ]] || fail \
    "game-service/.venv is missing; complete the Wiki first-time setup"
  [[ -f "$ROOT_DIR/minecraft-nodes/main-server/paper-1.21.11-132.jar" ]] || fail \
    "Paper jar is missing: minecraft-nodes/main-server/paper-1.21.11-132.jar"
  [[ -f "$SERVER_PROPERTIES" ]] || fail \
    "server.properties is missing; complete the Wiki first-time setup"
  [[ -s "$RESOURCE_PACK_ZIP" ]] || fail \
    "BetterHud resource pack is missing or empty: minecraft-nodes/main-server/plugins/BetterHud/build.zip"

  prepare_resource_pack_public_dir
  configure_resource_pack
  if ((RESOURCE_PACK_PROPERTIES_CHANGED)) && tmux_session_exists "$PAPER_SESSION"; then
    echo "Warning: resource-pack settings changed while Paper is already running." >&2
    echo "Restart Paper and reconnect clients before testing the new pack." >&2
  fi

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
    resource_pack_session_matches_contract || fail \
      "existing $RESOURCE_PACK_SESSION tmux session uses an old or unknown public root; stop that session and retry"
    echo "Resource pack server is already running in tmux: $RESOURCE_PACK_SESSION"
  else
    if curl -fsS --max-time 2 "$RESOURCE_PACK_HEALTH_URL" -o /dev/null 2>/dev/null; then
      fail "port $RESOURCE_PACK_PORT is already serving a resource pack outside tmux session $RESOURCE_PACK_SESSION"
    fi

    printf -v resource_pack_command \
      'exec python3 -m http.server %q --bind 0.0.0.0 --directory %q' \
      "$RESOURCE_PACK_PORT" "$RESOURCE_PACK_PUBLIC_DIR"
    tmux new-session -d -s "$RESOURCE_PACK_SESSION" \
      -c "$ROOT_DIR" \
      "$resource_pack_command"
    echo "Started resource pack server in tmux: $RESOURCE_PACK_SESSION"
  fi

  echo "Waiting for resource pack server..."
  wait_for_resource_pack || fail \
    "resource pack server did not become available at $RESOURCE_PACK_HEALTH_URL"

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
  echo "  PostgreSQL:            127.0.0.1:5432"
  echo "  Game Service:          http://127.0.0.1:8000"
  echo "  Resource pack health:  $RESOURCE_PACK_HEALTH_URL"
  echo "  Resource pack clients: $RESOURCE_PACK_PUBLIC_URL"
  echo "  Paper:                 127.0.0.1:25549"
  echo
  echo "Attach to consoles with:"
  echo "  tmux attach -t $GAME_SERVICE_SESSION"
  echo "  tmux attach -t $RESOURCE_PACK_SESSION"
  echo "  tmux attach -t $PAPER_SESSION"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
