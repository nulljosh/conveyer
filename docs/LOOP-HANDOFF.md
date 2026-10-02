# Conveyer loop handoff (2026-10-02, afternoon)

## After any restart

The server cannot save (FLE state), so it always boots the 10:55 copy. Run `scripts/withdraw.py coal 600`, `scripts/fuel.py`, then `scripts/oil.py` (refinery + plastic, 100 plastic in under a minute). Script every new build the same way so a crash costs seconds.

## Latest: runs on the real save, memory fixed, goal is a rocket

Fixed: the 18 GB balloon was get_entities() scanning the whole base every observation. Runner caps it at 30 tiles; it idles at about 165 MB. Menu bar stays down after a stop or memory kill and only restarts while the server is up. `scripts/world.sh` puts the server on a copy of a.zip. `scripts/snap.py` copies a screenshot into shots/ and logs a benchmark row (entities, steps, ok, rss) to shots/bench.jsonl every 5 min, and stops when runner.pid is gone.

Base at start (benchmark baseline): 2316 entities, 39 techs researched, 3 labs, 36 assembler-2, 27 electric drills, 41 steel furnaces, 6 boilers, 10 engines. Researching flammables. Open: advanced-circuit, sulfur-processing, solar-energy, concrete. rocket-silo is not researched.

Goal: build a rocket and launch it. Order: keep labs fed so research never stalls, then oil (pumpjack exists), advanced circuits, plastic, sulfur, then utility and production science, then the silo. Do not clear anything in the base. Skills ask for direction as UP/DOWN/LEFT/RIGHT; harvest then mine places a drill; smelt needs the drill already there.

# (older) 2026-10-02 morning

## Latest: running on Joshua's real world (a.zip copy)

Done: smelt is idempotent and checks coal (bootstrap harvests 70 now). `scripts/world.sh` swaps the server onto a copy of the save (`scripts/world.sh back` returns to stock). `runner.py --keep-world` skips FLE's reset, adopts the save's character, keeps biters. runner.lock stops duplicate runners. Memory guard kills the runner at 3 GB and dumps stacks. Menu bar respawns at most every 10 min.

Broken: on the real base (2316 entities) the runner balloons to 18 GB during init and filled swap, which froze the Mac. The server is stopped (`docker stop conveyer-world`) and the menu bar is quit. Find what balloons (likely initialise: _generate_chunks radius 25, or score/entity serialisation over the whole base), fix it, then `scripts/world.sh` and run. Joshua's character is not in the save, so the agent spawns at his last position (-51,-35).

Goal: agent keeps building the base, mines iron and steel, fights biters with guns and grenades. Send Joshua logs and screenshots at milestones.

# (older) Conveyer loop handoff (2026-10-01, evening)

## What the loop is

Agent.py runs FLE's Factorio environment headless, controlled by local Ollama (qwen3:8b by default). Skills layer dispatches LLM picks (skill name plus JSON params) instead of raw code. Bootstrap chains ore-harvest to furnace to gear-wheel end to end.

## Where things stand

Stack crashed overnight (colima down, agent.py hung). Last episode tried to craft 16 iron gears with 0 plates, tripped repeat guard. Restarted everything. Bootstrap now passes via fallback (hand-feed coal into the furnace, not the smelt skill). Smelt skill's coal-insert failed in the retry path. Furnace ended up at x=2, y=2 after placement. Colima plus FLE server plus runner.py plus status_writer.py all running as of 20:00. ConveyerMonitor.app running. Normalize names (kebab to PascalCase) and reuse-inserter logic merged into b518162.

## Next, in order

1. Check why smelt skill coal insert failed. Make retry idempotent so placing-furnace-twice doesn't cascade. Hand-feed works; smelt needs its coal path fixed.
2. Load Joshua's existing world save at ~/Library/Application Support/factorio/saves/a.zip (Aug 23, Factorio 2.0.77). Swap FLE's open_world control.lua into it. Start with --start-server instead of --start-server-load-scenario to skip FLE's forced inventory and run on real terrain.
3. Craft error messages should name the next skill needed (e.g. "need plates, try: smelt" when gears fail). Call it "missing-ingredient naming".
4. Run agent.py episode headless on Joshua's world. Goal: build the base out progressively. Start with ore-to-gear, then expand.

## Restart prompt

```
/loop Conveyer: finish smelt coal fix, then load Joshua's world save and run agent ep 1. Check bootstrap log for coal error root cause, fix smelt retry idempotent. Swap control.lua, start --start-server. Run agent.py headless on a.zip. Grade via menu bar status.
```
