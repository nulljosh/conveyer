#!/bin/sh
# Gate: score the adapter on the held-out run-split set, refuse to pass if skill name or params got worse than eval/baseline.json.
# Usage: scripts/gate.sh [adapter-path] [--update-baseline]
set -e
cd "$(dirname "$0")/.."
ADAPTER="${1:-$HOME/Documents/Code/turing/conveyer-adapter2}"
PY="$HOME/Documents/Code/turing/.venv/bin/python"
OUT=$($PY scripts/eval_picker.py --adapter "$ADAPTER" --label gate | tail -1)
echo "$OUT"
python3 scripts/bench_graph.py
python3 - "$OUT" "$2" <<'P'
import json, sys, os
new = json.loads(sys.argv[1]); p = "eval/baseline.json"
old = json.load(open(p)) if os.path.exists(p) else {"skill_name": 0, "params_exact": 0}
bad = [k for k in ("skill_name", "params_exact") if new[k] < old[k] - 0.02]
if bad: sys.exit("GATE FAIL: worse on " + ", ".join(bad))
if sys.argv[2] == "--update-baseline" or not os.path.exists(p):
    json.dump({k: new[k] for k in ("skill_name", "params_exact")}, open(p, "w"))
print("GATE PASS")
P
