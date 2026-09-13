#!/bin/bash
# Restart runner.py only — resets the in-game world/character but keeps the
# Factorio server container running. Fast (~15s).
set -e
cd "$(dirname "$0")/.."
pkill -f "runner.py" 2>/dev/null || true
sleep 1
rm -f runner_cmd.json runner_result.json runner_seq.txt status.json
nohup .venv/bin/python runner.py --env-id open_play > /tmp/conveyer_runner.log 2>&1 &
