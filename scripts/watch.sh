#!/usr/bin/env bash
# Live play-by-play of the latest agent run — no game client needed.
cd "$(dirname "$0")/.."
latest=$(ls -t runs/*.jsonl 2>/dev/null | head -1)
if [ -z "$latest" ]; then
  echo "No runs yet."
  exit 1
fi
echo "watching: $latest"
tail -f -n +1 "$latest" | while read -r line; do
  step=$(echo "$line" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"[step {d['step']}] reward={d['reward']}\n  {d['observation'][:300]}\n\")")
  echo "$step"
done
