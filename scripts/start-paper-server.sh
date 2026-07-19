#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="$ROOT_DIR/minecraft-nodes/main-server"

java_major_version() {
  "$1" -version 2>&1 | awk -F '"' '
    /version/ {
      split($2, parts, ".")
      print parts[1] == "1" ? parts[2] : parts[1]
      exit
    }
  '
}

find_java_25() {
  local candidate
  local system_java
  local -a candidates=(
    "$HOME/.local/share/jdks/temurin-25/bin/java"
    "$HOME/.local/jdks/jdk-25/bin/java"
  )

  if [ -n "${JAVA_HOME:-}" ]; then
    candidates+=("$JAVA_HOME/bin/java")
  fi

  system_java="$(command -v java || true)"
  if [ -n "$system_java" ]; then
    candidates+=("$system_java")
  fi

  for candidate in "${candidates[@]}"; do
    if [ -x "$candidate" ] && [ "$(java_major_version "$candidate")" = "25" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

if ! JAVA_BIN="$(find_java_25)"; then
  echo "Java 25 is required; install it or point JAVA_HOME to a Java 25 JDK" >&2
  exit 1
fi

cd "$SERVER_DIR"

if [ ! -f "server.properties" ]; then
  echo "server.properties is missing; complete the Wiki first-time setup before starting" >&2
  exit 1
fi

exec "$JAVA_BIN" -Xms512m -Xmx2G -jar paper-1.21.11-132.jar --nogui
