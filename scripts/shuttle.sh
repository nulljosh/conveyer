#!/bin/bash
# Fast crude shuttle: barrels.py move every 6 s (keepbusy only moves once per ~20 s pass, which starved the refineries).
# Bounded: exits when runner.pid is gone. Run as a Claude background task.
cd "$(dirname "$0")/.."
while [ -f runner.pid ] && kill -0 "$(cat runner.pid)" 2>/dev/null; do
  .venv/bin/python scripts/barrels.py move >/dev/null 2>&1
  sleep 6
done
