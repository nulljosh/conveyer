# Conveyer loop handoff (2026-10-01, evening)

## What the loop is

Agent.py runs FLE's Factorio environment headless, controlled by local Ollama (llama3.1:8b). Skills layer dispatches LLM picks (skill name plus JSON params) instead of raw code. Bootstrap chains ore-harvest to furnace to gear-wheel end to end. Agent loop runs 20-episode restarts unattended, refining on each failure.

## Where things stand

Stack crashed overnight (colima down, agent.py hung). Last episode tried to craft 16 iron gears with 0 plates, tripped repeat guard. Restarted everything. Bootstrap now passes via fallback (hand-feed iron into furnace, not the smelt skill). Smelt skill's coal-insert failed in the retry path. Furnace ended up at x=2, y=2 after placement. Colima plus FLE server plus runner.py plus status_writer.py all running as of 20:00. ConveyerMonitor.app running. Normalize names (kebab to PascalCase) and reuse-inserter logic merged into b518162.

## Next, in order

1. Check why smelt skill coal insert failed. Make retry idempotent so placing-furnace-twice doesn't cascade. Hand-feed works; smelt needs its coal path fixed.
2. Load Joshua's existing world save at ~/Library/Application Support/factorio/saves/a.zip (Aug 23, Factorio 2.0.77). Swap FLE's open_world control.lua into it. Start with --start-server instead of --start-server-load-scenario to skip FLE's forced inventory and run on real terrain.
3. Craft error messages should name the next skill needed (e.g. "need plates, try: smelt" when gears fail). Call it "missing-ingredient naming".
4. Run agent.py episode headless on Joshua's world. Goal: build the base out progressively. Start with ore-to-gear, then expand.

## Restart prompt

```
/loop --agent haiku --timeout 15m "Conveyer: finish smelt coal fix, then load Joshua's world save and run agent ep 1. Check bootstrap log for coal error root cause, fix smelt retry idempotent. Swap control.lua, start --start-server. Run agent.py headless on a.zip. Grade via menu bar status."
```
