# Conveyer loop handoff (2026-10-02, 14:20)

Read this first. Everything a fresh session needs is here and in git. Nothing lives only in a conversation.

## State

Goal: launch a rocket on Joshua's real save (a.zip copy). Rocket-silo path: 27 of 44 techs. Remaining: 4,350 red, 4,350 green, 3,350 blue, 1,600 purple, 1,000 yellow packs. Route and reasoning are in roadmap.md ("Route to the silo").
Built: refinery and plastic plant (scripts/oil.py), one advanced-circuit assembler (scripts/advcircuit.py), seven science tiles making red and green science (scripts/planner.py), a character armed with a submachine gun, heavy armor, 100 magazines, grenades.
Running: colima, the conveyer-world container, runner.py, research_status.py, snap.py (a map shot every 5 min into shots/), keepbusy.sh (keeps labs fed, boilers fueled, tiles supplied).

## The one rule that explains most of this repo

FLE's Lua state cannot be saved. An autosave kills the server. So any crash or restart reverts the world to the 10:55 copy, and everything built or researched since is gone. Defense is replay, not saves:
- research: scripts/journal.py (snapshot is automatic, restore re-marks techs researched)
- oil block: scripts/oil.py
- science tiles: scripts/planner.py replay (plan in .world/tiles.json)
- circuit assembler: scripts/advcircuit.py place
Every new build gets a replay script the same hour it is built.

- Live view: the menu bar popover has 2/5/10/30 s buttons and a Detach button that opens a resizable "Conveyer live" window. The choice is written to `.live`; runner.py captures and research_status.py repaints at that pace (floor 2 s, default 8 to 10 s). A 2 s setting costs about a second of CPU per frame, so leave it at 10 when nobody is watching. QA without clicking: `ConveyerMonitor --snapshot out.png [--live]`.

## Live preview plan (in progress, started 2026-10-02 14:40)

Goal: a truly live preview instead of refresh-every-x, super efficient. Done when it runs at 5 Hz or better under 5% of one core with the window open, and idle cost is near zero with it closed.
Design: a static basemap (terrain + entities) re-rendered only when the entity set changes, plus a tiny live overlay (character position, machine status dots, research %) from one cheap RCON call at 5 to 10 Hz, drawn by the menu bar app on top of the basemap. The basemap is centered on the character at capture time at 16 px per tile; frame.json records that center so overlay positions map to pixels.
Steps, one per tick, commit each:
1. Viewer heartbeat. The app touches `.watching` while the popover is open or the live window is visible. runner.py and research_status.py render only when it is fresh (under 8 s), otherwise once a minute. DONE when measured idle cost drops.
2. Change detection: hash the entity list from one RCON call; re-render the basemap only on change or every 60 s.
3. Overlay feed: scripts/livefeed.py writes live.json at 5 to 10 Hz (character x/y, working machines, research %, tick). The Swift app reads it and draws the marker.
4. CPU-aware: skip frames above 80% system CPU; game speed follows load (10 when idle, down to 3 when hot).
5. QA by screenshot and by `ps` CPU deltas; record before and after numbers here.
Baseline and results table:

- Blue science is now the research bottleneck (2026-10-02 14:40). Red and green only techs left: mining-productivity-1, weapon-shooting-speed-2, modular-armor, efficiency-module, explosives, bulk-inserter, circuit-network, landfill, fluid-wagon (queue them so labs never idle). Everything on the silo path from here needs chemical packs: add 'chemical-science-pack' to planner.py TARGETS. Needs engine units (steel, gear, pipe), advanced circuits (tile), and sulfur (a second chemical plant on the petroleum pipe, needs water; none in the east base yet).
- Wide screenshots (touch .wide) render the whole base, 2,700 entities, 28 s a frame. Off by default. The app shows the square map sharp at about 1:1 over a blurred copy instead of magnifying it. Real fix: incremental basemap (live preview plan, step 2).

## Tick (what the loop does every ~20 min)

1. `scripts/health.sh --fix`. Prints every moving part, starts what is down, and if the world reverted it replays journal, fuel, oil and tiles. Exit code is the number of open problems. If usage says 90% or more (session or weekly), run /checkpoint and stop the loop. No kill.
2. Read research.json. Keep the research queue on the silo path (RCON: `F.research_queue = {...}`), cheapest red and green techs first while blue is built.
3. Do ONE small chunk toward the next milestone. Order: automate blue science (sulfur plant, engine unit tile, advanced circuit tile, blue pack tile through planner.py), then purple, then yellow, then the silo.
4. At a milestone: `scripts/milestone.py NAME frame` around the build, `finish`, send the GIF, then `scripts/ship_landing.sh "<milestone>"`. Walk the character to the build first so the map centers on it. Stop keepbusy while recording (two step.sh callers shift results).
5. Commit and push by exact path. One TLDR line to Joshua.

## Gotchas that cost time

- step.sh takes one caller at a time. keepbusy, planner, oil, fuel, journal use RCON only and are safe beside it.
- Never `pkill -f` a pattern that appears in your own command line. Use the `[x]` trick or a PID.
- Every wait loop needs a deadline. A wait on a file's age ran 39 minutes once.
- A tool result that says "Cannot execute command ... must be used" means a bare function call in Lua. Lua here is 5.2: no `//`.
- Autosave, a second science runner, Steam and the full game client each caused trouble. Do not start any of them without a RAM check (health.sh prints it, keep 40% free).
- Screenshots: scripts/terrain.py paints ground under the FLE render; the renderer is patched in runner.py to drop the grid and alert triangles. scripts/realshot.sh is an experiment to get true-graphics shots from the real client.

## Files

health.sh, journal.py, oil.py, advcircuit.py, planner.py, keepbusy.sh, ship_landing.sh, milestone.py, world.sh, fuel.py, withdraw.py, feedlabs.py, terrain.py, snap.py, research_status.py (all in scripts/).

# History


## Every milestone

Run `scripts/ship_landing.sh "<milestone>"`. It repaints the map, rebuilds the landing page and README progress, commits, deploys to conveyer.heyitsmejosh.com and checks the live page. Open: the map centers on wherever the character stands (now the stone patch), not the main base. Walk the character to the hub before the shot.

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
