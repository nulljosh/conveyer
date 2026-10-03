#!/bin/bash
# Fast loop (6 s): the crude barrel shuttle, the silo feed (refills the three silo chests and fires the launch once part 100 lands, never with .assist),
# and every ~5 min the oil-field turret top-up. keepbusy only does these once per ~20 s pass, which starved the refineries.
# Bounded: exits when runner.pid is gone. Run as a Claude background task.
cd "$(dirname "$0")/.."
i=0
while [ -f runner.pid ] && kill -0 "$(cat runner.pid)" 2>/dev/null; do
  .venv/bin/python scripts/barrels.py move >/dev/null 2>&1
  i=$((i+1))
  [ $((i % 3)) -eq 0 ] && .venv/bin/python scripts/siloline.py >> siloline.log 2>&1
  [ $((i % 50)) -eq 0 ] && .venv/bin/python scripts/defend.py >> defend.log 2>&1
  sleep 6
done
