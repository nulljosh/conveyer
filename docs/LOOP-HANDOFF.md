# Loop handoff

Written 2026-10-01 at 91% session usage. Pick this up after the reset (Thu 20:10).

## Where it stands

Everything is down. Colima isn't running, so Docker, the FLE Factorio server, runner.py and
agent.py are all dead. That matches the 2026-10-01 note in roadmap.md: the server keeps going
down once the Claude session closes.

The last agent episode (`runs/1789370257-iron_gear_wheel_throughput.jsonl`) failed the same
way small models always fail here. It tried `craft IronGearWheel x16` with zero iron plates,
got "requires 32 iron-plate", then called `inspect` three times in a row and tripped the
repeat guard. It never went back to mine and smelt. Inventory had 455 coal, 49 drills, 9
furnaces, so materials were never the problem, planning was.

Committed this session (not yet run live):
- `auto_feed` folded into `smelt`. `smelt` now always builds the furnace clear of the ore
  patch with a burner inserter and belt, the version that actually works on dense patches.
  bootstrap.py and the milestone sounds follow the rename.
- `belt` and `place_inserter` reuse an inserter that already exists instead of stacking a
  second one, and `belt` can pull from a furnace output (extraction inserter).
- Kebab-case names from the model (`iron-plate`, `stone_furnace`) are normalized to FLE's
  `IronPlate` before rendering, instead of crashing the episode.
- `peek` no longer crashes on electric entities with no fuel slot.

## Steps, in order

1. Bring the stack up:
   ```
   colima start
   cd ~/Documents/Code/conveyer && ./menubar/restart_server.sh
   ```
   Check `/tmp/conveyer_cluster.log` and `/tmp/conveyer_runner.log`. Runner should log
   `peek -> ok=True`.
2. Verify the committed skill changes live: run `./bootstrap.py` once. Pass = it reaches
   `SKILL_OK smelt` without the hand-feed fallback and ends with iron plates. If it fails,
   fix that before anything else; this is the unverified part.
3. Fix the planning failure from the last episode. When `craft` fails on a missing
   ingredient, the error text should tell the model the next skill to call (`harvest` ore,
   then `smelt`) rather than leaving it to guess. Smallest fix lives in the `craft` template's
   exception message in skills.py, not a new planner.
4. Run one agent episode headless and read the transcript:
   ```
   .venv/bin/python agent.py --env-id iron_gear_wheel_throughput --max-steps 50
   ```
   Pass = it produces at least one gear without a repeat-guard stop.
5. Commit and push each passing step on its own.

## Ground rules

- Keep it headless. No Factorio client window, no Chrome.
- `skills.py` hot-reloads; editing `runner.py` forces a world reset.
- Don't leave a watchdog or cron behind to keep it alive (house rule, see ~/CLAUDE.md). The
  "keeps going down" roadmap item is solved by a real server (VPS, roadmap "This weekend"),
  not a local daemon.
- Stop at 90% usage and update this file before you go.
