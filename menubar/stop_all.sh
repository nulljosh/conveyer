#!/bin/bash
# Stop everything: runner, status writer, and whichever Factorio server is up
# (stock cluster or the real-save container). Frees the RAM/CPU for the night.
cd "$(dirname "$0")/.."
pkill -f "runner.py" 2>/dev/null || true
pkill -f "status_writer.py" 2>/dev/null || true
rm -f runner.pid  # intentional stop: menu bar must not respawn it
docker stop conveyer-world >/dev/null 2>&1 || true
source .env 2>/dev/null || true
.venv/bin/fle cluster stop > /tmp/conveyer_cluster.log 2>&1 || true
