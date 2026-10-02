#!/bin/bash
# Keep the player working: whenever labs sit out of packs, run a science cycle; top up fuel and the plastic plant.
# Bounded: exits when runner.pid is gone (same rule as snap.py). Usage: nohup scripts/keepbusy.sh &
# ponytail: polls every 60s over RCON; swap for a proper task queue when there's more than one job.
cd "$(dirname "$0")/.."
W=.venv/bin/python
while [ -f runner.pid ] && kill -0 "$(cat runner.pid)" 2>/dev/null; do
  idle=$($W - <<'PY'
import factorio_rcon as f
c=f.RCONClient("127.0.0.1",27000,"factorio",timeout=30)
print(c.send_command("/silent-command local n=0 for _,l in pairs(game.surfaces[1].find_entities_filtered{name='lab'}) do if l.electric_network_id and l.status==defines.entity_status.missing_science_packs then n=n+1 end end rcon.print(n)"))
PY
)
  echo "$(date +%H:%M:%S) idle labs: $idle"
  if [ "${idle:-0}" -gt 0 ]; then
    $W scripts/withdraw.py coal 300 >/dev/null 2>&1; $W scripts/fuel.py >/dev/null 2>&1
    scripts/science.sh 150
    $W scripts/oil.py
  fi
  sleep 60
done
