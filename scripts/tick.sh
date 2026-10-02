#!/bin/bash
# One call per loop tick: bring everything up, then print one compact report and what changed since the last tick.
# Usage: scripts/tick.sh      (read the output, do ONE chunk of work, commit)
cd "$(dirname "$0")/.."
W=.venv/bin/python
echo "== health"; scripts/health.sh --fix 2>&1 | grep -vE "^(memory|disk|usage)" | awk '{printf "%s%s", (NR>1?" | ":""), $0} END{print ""}' | sed 's/  */ /g'
echo "== speed"; $W scripts/speed.py
echo "== state"; $W scripts/statline.py tick | sed 's/^[^|]*| tick | //' | tr ' ' '\n' | grep -E "^(techs|research|pct|queue|labs|lab_packs|sci_stock|entities|evolution)=" | tr '\n' ' '; echo
echo "== silo path"; $W - <<'PY'
import json
r=json.load(open('research.json')); print(f"{r.get('silo_done')} of {r.get('silo_total')} techs, now {r['current']} {r['percent']}%, labs {r['labs_working']}/{r['labs']}, moving={r.get('moving')}")
PY
echo "== tiles"; $W scripts/planner.py tiles 2>&1 | cut -c1-100
echo "== usage"; bash ~/.claude/scripts/usage.sh 2>/dev/null || echo "unknown, read the usage line on the user's message; stop at 90%"
echo "== changed since last tick"; $W - <<'PY'
import json, re, subprocess
from pathlib import Path
st = Path('.world/tick_state.json'); old = json.loads(st.read_text()) if st.exists() else {}
r = json.load(open('research.json'))
now = {"silo_done": r.get('silo_done'), "techs": r.get('techs'), "tiles": len(json.loads(Path('.world/tiles.json').read_text())) if Path('.world/tiles.json').exists() else 0,
       "commit": subprocess.run(["git","rev-parse","--short","HEAD"],capture_output=True,text=True).stdout.strip()}
if not old: print("first tick recorded")
else:
    ch = [f"{k}: {old.get(k)} -> {v}" for k, v in now.items() if old.get(k) != v]
    print("; ".join(ch) or "nothing")
    if now["silo_done"] and old.get("silo_done") and now["silo_done"] > old["silo_done"]: print("MILESTONE: silo path advanced, consider ship_landing.sh")
st.write_text(json.dumps(now))
PY
