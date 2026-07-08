#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="$ROOT_DIR/minecraft-nodes/main-server"
JAVA_BIN="${JAVA_HOME:-}/bin/java"

if [ ! -x "$JAVA_BIN" ]; then
  JAVA_BIN="/tmp/immortal-mc-tools/jdk-21/bin/java"
fi

if [ ! -x "$JAVA_BIN" ]; then
  JAVA_BIN="$(command -v java)"
fi

cd "$SERVER_DIR"

if [ ! -f "server.properties" ] && [ -f "server.properties.example" ]; then
  cp server.properties.example server.properties
fi

exec "$JAVA_BIN" -Xms512m -Xmx2G -jar paper-1.21.11-132.jar --nogui
