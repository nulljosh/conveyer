#!/bin/bash
# Keep the player working: whenever labs sit out of packs, run a science cycle; top up fuel and the plastic plant.
# Bounded: exits when runner.pid is gone (same rule as snap.py). Usage: nohup scripts/keepbusy.sh &
# Refills when any lab holds under 15 of red or green, so research never hits zero (was: only once a lab was already idle).
# ponytail: polls every 60s over RCON; swap for a proper task queue when there's more than one job.
cd "$(dirname "$0")/.."
W=.venv/bin/python
i=0
while [ -f runner.pid ] && kill -0 "$(cat runner.pid)" 2>/dev/null; do
  idle=$($W - <<'PY'
import factorio_rcon as f
c=f.RCONClient("127.0.0.1",27000,"factorio",timeout=30)
print(c.send_command("/silent-command local n=0 for _,l in pairs(game.surfaces[1].find_entities_filtered{name='lab'}) do if l.electric_network_id then local i=l.get_inventory(defines.inventory.lab_input) if i.get_item_count('automation-science-pack')<15 or i.get_item_count('logistic-science-pack')<15 then n=n+1 end end end rcon.print(n)"))
PY
)
  # every 5th pass top up boilers and furnaces (the west outpost boiler starved six iron drills when this only ran on refills)
  i=$((i+1)); if [ $((i % 5)) -eq 1 ]; then $W scripts/withdraw.py coal 700 >/dev/null 2>&1; $W scripts/fuel.py >/dev/null 2>&1; $W scripts/journal.py snapshot >/dev/null 2>&1; $W scripts/oil.py >/dev/null 2>&1; $W scripts/queue.py >/dev/null 2>&1; $W scripts/power.py >/dev/null 2>&1; fi  # oil.py also tops up the plastic plant's coal
  $W scripts/planner.py step >> planner.log 2>&1   # keep the tiles supplied
  $W scripts/speed.py >> planner.log 2>&1            # CPU aware: game speed follows machine load
  echo "$(date +%H:%M:%S) idle labs: $idle"
  $W scripts/planner.py labs >/dev/null 2>&1; $W scripts/feedlabs.py >/dev/null 2>&1   # every pass: the idle test only watched red and green, so blue packs sat in the chest
  if [ "${idle:-0}" -gt 0 ]; then
    $W scripts/withdraw.py coal 300 >/dev/null 2>&1; $W scripts/fuel.py >/dev/null 2>&1
    $W scripts/planner.py labs; $W scripts/feedlabs.py   # packs come from the planner tiles now, not hand-crafting
    $W scripts/oil.py
  fi
  sleep 20   # at 10x game speed a tile outruns a 60 s refill
done
