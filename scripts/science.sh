#!/bin/bash
# One science cycle: fetch plates/cable/belts from the base chests, hand-craft N red + N green,
# walk to the labs and split them. Usage: scripts/science.sh [N=60]. Run alone: one runner, one caller.
cd "$(dirname "$0")/.."
N=${1:-60}
s(){ ./step.sh "$1" | python3 -c "import json,sys; d=json.load(sys.stdin); print(str(d.get('observation',d))[:160])"; }
get(){ s "{\"skill\":\"goto\",\"params\":{\"position\":\"$2\"}}" >/dev/null; s "{\"skill\":\"collect\",\"params\":{\"item_prototype\":\"$1\",\"source_position\":\"$3\",\"quantity\":$4}}"; }
[ -n "$SKIP_IRON" ] || .venv/bin/python scripts/withdraw.py iron-plate $((N*8))
.venv/bin/python scripts/withdraw.py copper-plate $((N*3))  # cable is crafted from plate on the way
get TransportBelt -90,-46 -90.5,-48.5 $N
s "{\"skill\":\"craft\",\"params\":{\"item_prototype\":\"AutomationSciencePack\",\"count\":$N}}"
s "{\"skill\":\"craft\",\"params\":{\"item_prototype\":\"LogisticsSciencePack\",\"count\":$N}}"
.venv/bin/python scripts/feedlabs.py
