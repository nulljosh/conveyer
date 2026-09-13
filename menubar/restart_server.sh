#!/bin/bash
# Full restart: Docker Factorio server + runner.py. Slow (~30-45s), use when
# the server itself is unresponsive, not for routine world resets.
set -e
cd "$(dirname "$0")/.."
pkill -f "runner.py" 2>/dev/null || true
pkill -f "status_writer.py" 2>/dev/null || true
source .env
.venv/bin/fle cluster restart -n 1 -s open_world > /tmp/conveyer_cluster.log 2>&1
sleep 5
rm -f runner_cmd.json runner_result.json runner_seq.txt status.json
nohup .venv/bin/python runner.py --env-id open_play > /tmp/conveyer_runner.log 2>&1 &
nohup .venv/bin/python status_writer.py > /tmp/conveyer_status_writer.log 2>&1 &
