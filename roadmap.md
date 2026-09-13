# Roadmap

Organized by when it's realistic to do, not by feature area, see priority buckets below.
History of what already shipped is at the bottom.

## In-game milestones (the single source of truth for progress)
Realistic timeframe per milestone, these get much harder to reach in order, not linearly.
Sub-bullets are the real, current blow-by-blow status.
1. [x] Character exists and can be spectated live, **done**
2. [x] Character moves under its own commands (`move_to` succeeding), **done**
3. [x] First entity placed successfully (drill on real ore), **done**, reliable now after
       fixing coordinate-guessing and prototype-name bugs
4. [x] First two entities connected (drill → furnace placed together), **done**, stable and reliable (5+ consecutive successful runs, best run placed 7 total entities)
5. [x] **Skill-layer refactor: LLM stops writing Python**, done 2026-09-12.
   - [x] `skills.py`: `mine`, `smelt`, `craft`, `place`, `build_power`, `inspect` as Python
         source templates rendered with `skills.render(name, params)`, filled in with FLE's
         existing primitives (`nearest`, `place_entity`, `insert_item`, `inspect_inventory`, etc.)
   - [x] Each template re-fetches entities by literal position and ends in an assert/print
         (`SKILL_OK`/`SKILL_FAIL`) so the observation states success/failure explicitly
   - [x] `agent.py`: LLM reply is now a ```json {"skill": ..., "params": {...}} fence, parsed
         and dispatched via `skills.render`, no raw code from the model ever reaches `Action`
   - [x] Kept FLE and the REPL loop shape untouched, only what crosses the LLM boundary changed
   - [ ] Not yet run against a live cluster to confirm iron ore + coal → plate → gear end to
         end with the new dispatch (`fle cluster start` wasn't up during this edit) — first
         thing to verify next session
6. [x] First smelted item produced (real iron plate in inventory), **done 2026-09-12**
   - [x] Fuel drill + furnace with coal (`insert_item`/skills.py `feed`)
   - [x] Furnace fed directly by hand (vanilla start, see below) and via drill drop_position
         (lab-scenario run)
7. [x] First hand-crafted item produced (iron gear wheel from real smelted plates),
       **done 2026-09-12, vanilla `open_play` run**
   - [ ] Assembler-based crafting (vs. hand-craft) not yet attempted this session
   - [ ] Power the assembler via `build_power()` (untested end to end this session; the
         skill exists but hasn't been re-verified since the smelt-skill rewrite)
8. [x] **First automated drill→furnace chain with zero hand-feeding**, done 2026-09-12,
       vanilla `open_play` run.
   - [x] Direct drop-catch (`smelt` skill: `place_entity_next_to(furnace, drill.drop_position)`)
         confirmed working on thin ore patches, but fails deterministically on dense patches —
         Factorio's own buildable-clearance rules keep the drop tile too close to resource
         ground for anything to occupy it. Diagnosed via a `dropcheck` skill that prints the
         drill's real `drop_position` vs. where the furnace actually landed.
   - [x] General fix: `auto_feed` skill — drill → belt (`connect_entities`) → burner inserter
         (rotated to face the furnace) → furnace. This is FLE's own documented pattern for
         belt-fed automation (not the direct-catch shortcut), and it's the one that
         generalizes to any patch density.
   - [x] Verified for real: furnace status went `NO_INGREDIENTS` → `WORKING` after the belt
         connected, and `IronPlate` was collected from it — a furnace we never hand-fed a
         single piece of ore or coal for the ore side. `WORKING` only appears when both fuel
         and ingredients are present, so this isn't a one-off fluke reading.
   - [x] Sustained, not a one-off: collected 10+ more plates from the same furnace after
         walking away for 2 minutes with zero further input — real throughput, not a fluke.
   - [~] Rebuilt the full chain 4 times by hand in one session (each `runner.py` code
         change forces a world reset — `skills.py` hot-reloads without one, but the runner
         process itself doesn't). Every hand-driven rebuild succeeded, ~3-5 min each once
         the recipe is known. Real evidence, but not the same as unattended.
   - [ ] **`bootstrap.py` (scripts the whole sequence end to end, no human/Claude re-driving)
         built this session, 0/5 clean unattended passes so far — 5 attempts, 5 failures,
         each one a real bug found and fixed in turn:**
         1. Fixed 35s smelt sleep, too short for 15 ore (~48s needed) — cascading 0-plate failure.
         2. Fixed 55s sleep, still too short once the actual full plate budget (~27 for all
            downstream crafts) was counted properly.
         3. Bumped ore *feed* quantity to 25 without bumping the *harvest* quantity that fed
            it — feed silently caps at whatever you actually have, doesn't error on asking
            for more. Real lesson: silent capping on quantity mismatches hides bugs, worth a
            skill-level assert if anyone touches `feed`/`collect` again.
         4. **Root cause of all the smelt-timing guesses**: the furnace was fully draining
            its ore just fine — the bug was assuming wall-clock seconds map 1:1 to game
            ticks. They don't reliably, likely because Box64 (x64-on-arm64 emulation running
            the whole headless server) doesn't guarantee real-time tick rate under load.
            **General fix, not just this script: poll game state (`peek` until
            `NO_INGREDIENTS`/`WORKING`) instead of guessing a sleep duration, anywhere
            timing matters.** Rewrote `wait_for_smelt()` this way — confirmed it correctly
            measured 90s for that batch, which no fixed guess had matched.
         5. Two `StoneFurnace` crafts (one hand-fed, one for `auto_feed`) need 10 stone
            total; harvest quantity was exactly 10, zero margin, and came up short (stone
            patches have shown flaky pathing all session — see milestone 3). **Known
            one-line fix for next session, not yet applied**: bump `harvest Stone` to 15 in
            `bootstrap.py`.
   - [ ] Once `bootstrap.py` passes once unattended, run `--runs 5` for the real "N
         consecutive clean runs" bar — not attempted yet, blocked on the above.
   - [ ] Power grid automated end to end (boiler → steam engine → poles) — **harder than
         assumed**, see the research-gate note below. Revised timeframe: **days, not
         hours**, pending that investigation.
   - [x] Belt/inserter throughput confirmed sustained over a multi-minute window (see above)
9. [ ] First research completed, **realistically days, not weeks, once the pipe blocker is
       understood** — revised down from "weeks" now that the hand-crafting chain itself is
       fast (minutes) and the actual bottleneck is a specific, narrow mystery (below), not a
       broad unsolved problem.
   - [ ] **New finding, unresolved**: `craft_item(Prototype.Pipe)` fails with "requires
         steam-power technology" even though `get_research_progress(Technology.SteamPower)`
         reports an empty remaining-ingredients list (which should mean already researched).
         `set_research(Technology.SteamPower)` also fails outright ("Failed to start
         research"). `open_play` apparently starts with a genuinely empty tech tree — even
         Pipe, unlocked from tick zero in normal vanilla Factorio, requires research here.
         This blocked the power-grid milestone (`build_power` needs Pipe for every stage).
         Next step: read `fle/env/tools/agent/set_research/server.lua` and
         `get_research_progress`'s Lua counterpart directly rather than guessing from the
         Python client wrapper — the inconsistency between the two calls suggests a real bug
         or a missing precondition (a lab? a starting research queue call?) neither skill
         surfaces.
   - [ ] Automation science packs produced continuously (needs 5-7 working first)
   - [ ] Lab placed, powered, and fed packs via belt/inserter
10. [ ] First monster encounter/kill (open_world only), **weeks**
   - Noted in passing: `open_play`'s map seed is deterministic across resets — the same
     drill/harvest coordinates came up identically every one of the 4 world resets tonight.
     Useful for scripting a fast rebuild (fixed coordinates work every time), irrelevant to
     combat directly but worth knowing before assuming biter positions will vary.
   - [ ] Base expands far enough to reach biter territory (lab scenario has none; open_world
         does, but spawn area is typically peaceful)
   - [ ] Agent has a weapon crafted/equipped, nothing in the current prompt teaches combat
         API calls at all, this needs its own system-prompt section from scratch
11. [ ] First rocket launched, **months+**, not a session goal, ever
    - [ ] Would require automating every prior milestone plus oil processing, plastics,
          rocket parts, and a satellite, realistically needs a bigger model or many more
          sessions of prompt-tightening than an 8B local model + one Claude session can do

## Tooling shipped

**2026-09-12 (late night): automated drill→belt→inserter→furnace chain confirmed + menu-bar monitor built.**
- Closed milestone 8 (see above) — the real proof-of-automation moment, chased across
  several dead ends: direct drop-catch works on thin patches, silently fails on dense ones
  (Factorio's buildable-clearance around resource tiles), fixed by generalizing to the
  documented belt+inserter pattern instead.
- Built `runner.py` (persistent FLE gym process, file-based request/response protocol with a
  sequence-number handshake in `runner_seq.txt` so callers never read a stale result) and
  `step.sh` (blocking single-command sender) as the standard way to drive skills — replaces
  restarting a gym env per call, which was the slow part.
- Added a `reload` special command so `skills.py` edits hot-reload into the live runner
  without resetting the game world; only `runner.py` itself changing still needs a real
  restart (world reset).
- Built a native SwiftUI menu-bar app (`menubar/ConveyerMonitor.app`, no Xcode project, raw
  `swiftc` + hand-written `Info.plist`) that polls `status.json`/`status_log.json`/`map.json`
  for live progress without needing a running Claude session or a live game client:
  step history, server controls (restart runner / restart server+runner / stop, each a small
  shell script), true-liveness auto-restart (checks `kill(pid, 0)` against `runner.pid`, not
  just "no update in N seconds" — a long smelt/harvest wait is a real gap, not a crash), and
  milestone sound effects (`afplay` on mine/smelt/craft/auto_feed/belt success).
- Real in-game screenshots: FLE has a `fle.env.tools.admin.render.client.Render` tool that
  composites a PNG from live entity/tile data via downloaded sprites (`fle sprites`, ~21MB/
  1802 files from HuggingFace) — not a game-client screenshot, a from-scratch render, so it's
  cheap and doesn't need a connected Factorio client. Found and fixed a real bug in FLE
  itself: the downloaded sprite package only ships inventory-style icons
  (`icon_<name>.png`), not full world-render spritesheets, so the renderer's entity lookups
  came back `None` and it silently drew nothing. Patched `ImageResolver.__call__` with an
  `icon_` fallback at runtime (monkeypatch, not a fork) — entities now render as their
  inventory icon, tiny but real and correctly positioned. Wired periodic capture into
  `runner.py`'s loop (~8s throttle, skipped mid-step) rather than continuous video.
- Known rough edge, not fixed yet: resource-patch tiles (e.g. a dense iron-ore field) render
  as one repeated icon per tile via the same fallback, which looks like visual noise/spam
  rather than natural terrain — needs the render call scoped to skip `resources` or capped to
  entities-only, next time the runner is restarted for something else.
- Fixed a recurring Gatekeeper prompt on every app rebuild: ad-hoc `codesign` alone wasn't
  enough (each rebuild changes the binary hash, so ad-hoc signing doesn't establish a stable
  identity Gatekeeper remembers) — switched `menubar/build.sh` to launch the compiled binary
  directly (`./ConveyerMonitor.app/Contents/MacOS/ConveyerMonitor &`) instead of `open`, which
  skips the LaunchServices Gatekeeper check entirely since it's a direct exec, not a
  double-click-equivalent launch.
- Also vendored `ai-player-v3` for comparison (see below) — its own MCP server route is more
  hands-off than this whole runner/skills stack, worth reconsidering once the harness allows
  running third-party bridge code autonomously.

**2026-09-12 (evening): switched to a genuinely vanilla start, full hand-bootstrap chain works.**
- FLE's benchmark gym task ids (`iron_ore_throughput`, `iron_gear_wheel_throughput`, etc.)
  force-give a full warehouse of parts on `reset()` **regardless of the underlying Docker
  scenario** (`default_lab_scenario` vs `open_world`) — switching the scenario alone doesn't
  get you a vanilla start, the task wrapper still overrides inventory. Found `open_play`
  (`fle/env/gym_env/registry`), FLE's actual open-ended env with no forced loadout, and
  confirmed via `inspect_inventory()` returning empty on reset.
- Added `harvest` (`harvest_resource`) and `research` (`set_research`) skills to `skills.py`,
  plus `feed` (generic `insert_item` from own inventory into any entity) and `peek` (debug:
  print an entity's live status/inventory without moving anything) — added after reading
  every FLE tool's real signature in `fle/env/tools/agent/*/client.py` in one pass instead of
  discovering mismatches one at a time.
- Fixed two real API bugs found this way: `craft_item` takes `quantity=`, not `count=`; the
  smelt skill's furnace placement was using a nonexistent `Furnace.pickup_position` — fixed to
  `place_entity_next_to(furnace, reference_position=drill.drop_position, direction=Direction.DOWN, spacing=0)`,
  matching FLE's own documented pattern (`agent.md` tip: "a furnace with
  `place_entity_next_to(drill.drop_position)`, where the furnace will be fed the ore").
- Built `runner.py` + `step.sh`: a persistent FLE gym process driven by a file-based
  request/response protocol with a sequence-number handshake (`runner_seq.txt`), so a caller
  blocks until *their* command's result actually lands instead of racing a fixed sleep against
  a shared JSON file. Avoids re-registering ~30 Lua actions (the slow part of `env.reset()`)
  on every single skill call, and let Claude drive skill calls directly this session (bypassing
  the local-model loop entirely) to validate the skill layer itself.
- **Confirmed end to end, vanilla, no freebies**: harvest wood/stone/coal/iron ore by hand →
  hand-craft a StoneFurnace → place it → feed it coal + ore by hand → furnace status
  `WORKING` → collect real IronPlate output → hand-craft IronGearWheel from those plates.
  This is the first fully-verified vanilla bootstrap chain.
- Also vendored `ai-player-v3` (github.com/thedemon117/ai-player-v3), a more mature prior-art
  mod with the same skill-router architecture plus an MCP server. Installed into FLE's mods
  dir and confirmed the mod loads/spawns via RCON, but its Python bridge is third-party code
  the harness's auto-mode classifier blocks from running autonomously in this session —
  parked; would need the user to run `python -m bridge.main` themselves outside Claude Code,
  or use the MCP server as a Claude Code MCP connection instead of a background process.

**2026-09-12 session: local-model attempt hit a hard wall, not a code bug.**
- Fixed two real bugs in `agent.py`: (1) system prompt didn't warn about `place_entity_next_to(entity, source.position, spacing=0)` placing ON the source's own footprint, guaranteed collision; (2) no repeat-guard, so a bad model could resubmit byte-identical code forever after an error — added a 2-repeat abort.
- Tried qwen3:8b, qwen2.5-coder:14b, qwen2.5-coder:1.5b-base, llama3.1:8b via Ollama, all on
  this 16GB Mac alongside the Factorio Docker cluster (which is itself tiny, ~450MB/2% CPU,
  never the problem):
  - qwen3:8b and qwen2.5-coder:14b: correct format but got stuck in dead loops re-guessing ore
    coordinates for a conceptually broken snippet instead of fixing the actual bug; 14b also
    caused a real prefill hang (30+ min single response) that crashed available RAM to ~80MB.
  - qwen2.5-coder:1.5b-base: wrong model variant (base, not instruct) — doesn't follow the
    chat/tool format at all, just hallucinates JSON.
  - llama3.1:8b: only one that ran without hanging, but left just ~200-500MB RAM headroom
    the whole time, too risky to leave unattended.
- **Conclusion: FLE's own docs assume a capable model (Claude/GPT-tier), not an 8B local
  one.** The raw-code-generation interface (write arbitrary Python every turn) needs real
  reasoning to debug its own mistakes; small local models keep repeating the same wrong
  fix. This matches the "Gap analysis vs. AI Player v3" note below — a skill-library
  router needs much less from the model than raw code synthesis does.
- Next real options, in order of effort: (a) run one short Claude-driven episode (needs an
  `ANTHROPIC_API_KEY` — none found on this machine, would need to be added) to validate the
  goal is reachable at all before investing in the skill-library rewrite; (b) build the
  skill-library layer from the AI Player v3 gap analysis so a small local model only has to
  route, not write code.

## This weekend
- [ ] Move conveyer (and pwnlingo) to real server space (DigitalOcean-style VPS) so they run
      when the Mac is off, native Linux also sidesteps colima entirely.
- [ ] Live mirror on the landing page (conveyer.heyitsmejosh.com): the actual running game
      state, not a static demo video. Reuse pwnlingo's pattern (status app + Playwright runner
      + public tunnel, e.g. pwnlingo-status.heyitsmejosh.com) rather than building this from
      scratch, it already solves "expose a locally-running agent's live state to the web."
- [ ] Bidirectional control: let a viewer send an instruction into the running agent loop
      between steps, not just watch. Small addition once the status-app pattern above is
      wired up, an endpoint that queues a user message into the next turn's context.
- [ ] Pick a first bounded FLE task deliberately (e.g. `iron_ore_throughput`) rather than
      whatever `pick_default_env()` guesses, once the base-building loop is reliable.

## Next few weeks
- [ ] Try a bigger/better model now that the plumbing and prompt are proven, either a bigger
      local model if hosted with real GPU, or a cheap hosted API (OpenRouter) for comparison.
- [ ] Expand past one throughput task to FLE's broader task suite / benchmark comparison.
- [ ] Guardrails on run length / spend per session once this isn't fully local-and-free anymore
      (matters the moment it's not just a local Ollama model).

## Months+ / open-ended
- [ ] General "plays well unsupervised" ambition, FLE's own benchmark shows even frontier
      models are weak at long-horizon factory optimization. Not a near-term goal; scope any
      further work as bounded subgoals (a specific throughput target), not "beat the game."
