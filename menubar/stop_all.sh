#!/bin/bash
# Stop everything: runner, status writer, and the Docker Factorio server —
# frees the RAM/CPU the cluster holds when you're done for the night.
cd "$(dirname "$0")/.."
pkill -f "runner.py" 2>/dev/null || true
pkill -f "status_writer.py" 2>/dev/null || true
source .env 2>/dev/null || true
.venv/bin/fle cluster stop > /tmp/conveyer_cluster.log 2>&1 || true
