#!/bin/bash
# Send one skill call to runner.py and block until its result actually lands
# (compares runner_seq.txt instead of a fixed sleep, so no more stale reads).
set -euo pipefail
cd "$(dirname "$0")"

payload="$1"
before=$(cat runner_seq.txt 2>/dev/null || echo 0)
echo "$payload" > runner_cmd.json

for _ in $(seq 1 60); do
  after=$(cat runner_seq.txt 2>/dev/null || echo 0)
  if [ "$after" != "$before" ]; then
    cat runner_result.json
    exit 0
  fi
  sleep 0.5
done
echo '{"ok": false, "error": "timed out waiting for runner"}'
exit 1
