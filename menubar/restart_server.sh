#!/bin/bash
# Full restart: Docker Factorio server + runner.py. Slow (~30-45s), use when
# the server itself is unresponsive, not for routine world resets.
# Stays on the real save if scripts/world.sh put us there.
set -e
cd "$(dirname "$0")/.."
pkill -f "runner.py" 2>/dev/null || true
pkill -f "status_writer.py" 2>/dev/null || true
source .env
if [ -f .world/active ]; then
  docker restart conveyer-world > /tmp/conveyer_cluster.log 2>&1
else
  .venv/bin/fle cluster restart -n 1 -s open_world > /tmp/conveyer_cluster.log 2>&1
fi
sleep 5
nohup .venv/bin/python status_writer.py > /tmp/conveyer_status_writer.log 2>&1 &
exec "$(dirname "$0")/restart_runner.sh"
