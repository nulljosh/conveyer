# Conveyer loop handoff (2026-10-05, afternoon)

## What the loop is

Find a game an agent can beat, play it, and log honestly how far it got. Factorio is beaten (v2.0.0, 2 Oct). The loop now plays **Game Dev Tycoon** through a small mod and keeps the Factorio benchmark runs going on the side.

## Where things stand

- **Game Dev Tycoon: playing, not beaten.** The third run was at Year 4, month 8 with 93K cash at 13:45 on 5 Oct. The first two went bankrupt in Year 3. The game ends and scores itself at Y35 M12 W4. That is the win.
- **How it plays.** `games/gdt/conveyer-bridge/` is a mod with no network and no code execution: it writes the screen to `~/Library/Application Support/conveyer-gdt/state.json` and takes a fixed list of button presses from `cmd.json`. `scripts/gdt_play.py` is the driver. It logs every decision to `runs/gdt/` (gitignored) and restarts after a bankruptcy.
- **Labels.** Unassisted play: the driver reads screen text and read-only state and never writes cash, dates or saves. Topic and genre pairs come from a public guide table, so say "assisted by guide data" for those.
- **Never touch save slot 3.** It is Joshua's real 2014 save. Our studio (Conveyer Games) plays in slot 5. A backup of his saves is in `.gdt-save-backup/` (gitignored).
- **Factorio benchmark.** Claude passed `iron_plate_throughput` by hand through the skill layer (17 a minute against a quota of 16). The trained picker plays the opening (12 of 13 calls) and then repeats one belt call. It needs data from runs that go past the belt.
- **Other games.** FEZ and Papers, Please launch but have no bridge. Don't Starve will not open on this macOS. The ranked list is in `roadmap.md` under Next games.
- **Factorio live window.** Steps 1 to 3 done (5.7% of a core), step 4 held because it needs a runner restart. Details below.

## Next, in order

1. Keep the Game Dev Tycoon run alive to Year 35. Each tick: `scripts/gdt.py show`, driver pid, `/tmp/gdt_play.out`, the log tail. Fix stalls in the driver, restart it, log bankruptcies and review scores.
2. Better games, so the studio stops scraping by: per-genre development sliders (catch a "Development Stage" dialog and read the slider items), then research.
3. Factorio picker: collect skill runs that continue past the first belt (`scripts/skill.py` plays one skill at a time), retrain, re-run `iron_plate_throughput`.
4. FEZ: the HAT mod loader is the way in if a third game is wanted.

Starting Game Dev Tycoon: Steam must be running, then `open steam://run/239820`. If no fresh `state.json` appears, enable Conveyer Bridge in the game's Mods menu and restart the game. The game needs its window on a display that is awake (`caffeinate -d`).

## Factorio: pick up in 60 seconds

| You are | Do |
|---|---|
| On the Mac, game down | `scripts/health.sh --fix`, then the background tasks below, then `open -n menubar/ConveyerMonitor.app --args --open-live` |
| On the Mac, game up | `scripts/tick.sh` and read what it prints |
| In a cloud session (no game, no Mac) | Python feeders, unit tests, Lua strings, docs. See "Cloud-safe work" |
| Back after a Claude crash | The server survives a Claude crash but the workers die with the session. Start with `scripts/tick.sh`, then relaunch the tasks below |

Background tasks: run each one as a Claude background task, never with nohup, and refresh any that are older than 15 minutes:
`scripts/keepbusy.sh`, `.venv/bin/python scripts/livemap.py`, `.venv/bin/python scripts/stream.py`, `scripts/snap.py`, `scripts/research_status.py`, `scripts/shuttle.sh`.
`stream.py` replaces `livefeed.py` and `combat.py`. Don't run them alongside it. If the window looks wrong, stop `stream.py` and go back to those two; `livemap.py` picks its dots up again on its own within 3 s.

## Live window: where it stands

What feeds the window today (Mac app `menubar/main.swift`, Python feeders in `scripts/`):

| Piece | What it does | Cost / problem |
|---|---|---|
| `runner.py` basemap | FLE renders the base to a PNG at 16 px per tile. It re-renders only when the base signature changes | 21 to 28 s per render, and the render blocks the runner |
| `livefeed.py` | Character x/y at 5 Hz; hotbar and silo every 2 s | Opens its own RCON connection |
| `livemap.py` | Machine status dots at 1 Hz | Opens its own RCON connection |
| `combat.py` | Enemies and firing turrets at 2 Hz | Opens its own RCON connection |
| App `MarkerModel` | `stat`s 8 JSON files every 0.2 s and runs a 60 Hz ease timer | The timer keeps firing even when nothing moves |
| Factorio VM | 10x game speed | About 64% CPU. The biggest single cost. Game speed does not follow load yet |

Every feeder already sleeps unless `.watching` is fresh (touched less than 8 s ago), so the cost with the window closed is near zero. Last measured grade: QA A-, efficiency B+.

## Live window: plan (one step per tick, commit each)

1. **One feeder.** DONE and verified 2026-10-04 on the live game (10 minutes clean, no errors). Wrote `scripts/stream.py` to replace livefeed, livemap and combat. It uses one RCON connection and one Lua call per frame, with tiered rates: position at 10 Hz, dots at 1 Hz, combat at 2 Hz, hotbar and silo at 0.5 Hz. It writes a single `stream.json` atomically. Keep the old files written until the app reads only the new one. *Cloud-safe: write it with a fake RCON client and tests.*
2. **Deltas.** DONE 2026-10-05 (v2.1.1, verified on the live game: 54 machines, full read then deltas). The Lua keeps the last machine statuses in `storage` and returns only the ones that changed, plus a full snapshot every 30 s. *Cloud-safe except the final check.*
3. **App reads one file, and only when it changes.** DONE 2026-10-05 (v2.1.2, typechecks and runs; CPU did not move, see the grades table). The app now wakes on `stream.json` through a file watch, the 0.2 s poll drops to 1 s while stream.json is fresh, and the 60 Hz ease timer only runs while the marker is moving. Original plan: Swap the 0.2 s poll of 8 files for a `DispatchSource` file watch on `stream.json`. Run the 60 Hz ease timer only while the marker is moving. *Mac only (Swift build).*
3b. **Cut the redraw cost.** DONE 2026-10-05 (v2.1.4): the eased position now lives in its own `Glide` object, so only the camera, marker and minimap redraw at 60 Hz; the hotbar, feed, dots and silo no longer observe it. About 10% to 5.5%. Earlier notes (v2.1.3): found by bisecting the overlays (`sample`, then adding them back one at a time). The hotbar decoded 10 PNGs from disk on every redraw, and it redraws at 60 Hz while the engineer walks because it observes the whole marker model. An icon cache took the window from 30% to about 10%. Still over the 5% goal. What is left, measured: easing at 30 Hz instead of 60 saves about 1.7 points; the rest is the 6 animated TimelineViews and every overlay re-running its body on each marker publish (split the model so the hotbar, feed and minimap stop observing the position). Original notes: The window costs about 30% of a core fullscreen while the marker moves, far over the 5% goal. Find what redraws per frame (`sample <pid> 3`), then try: `drawingGroup()` or a Canvas for the dots and enemies, redraw the map layer only when its picture changes, and cap the marker to 30 fps. Measure with `top -l 4 -s 20 -pid` before and after. *Mac only.*
4. **Tiled basemap.** HELD 2026-10-05: it means rewriting `capture_screenshot` in `runner.py` around FLE's renderer internals, and the only way to load it is a runner restart, which rolls the world back to the 10:55 copy (FLE state cannot be saved). Do it only when a restart is needed anyway, then run `scripts/health.sh --fix`. The window works without it: the render only blocks the runner, not the window. Render 32x32 chunks, cache each chunk's PNG under the hash of its entities, and re-render only the chunks that changed, off the runner thread. This fixes the 28 s block. *Mac plus game.*
5. **Game speed follows load.** DONE (already in place: `keepbusy.sh` calls `speed.py` every cycle, `tick.sh` too; 10x idle, 2x under memory pressure; checked 2026-10-05, load 0.32 per core, 10x). Run at 10x when the machine is idle and drop to 3x when it is hot (`scripts/speed.py`, `scripts/cpu_guard.sh`). *Mac plus game.*
6. **QA.** DONE 2026-10-05, see the last grades row. Take screenshots with `ConveyerMonitor --snapshot out.png --live` and measure CPU with `ps` with the window open and closed. Put the before and after numbers in the grades table below.

Done when: the window is open at 5 Hz or better and every feeder plus the app together stays under 5% of one core. With the window closed, idle cost is roughly 0.

### Live view grades

| When | QA | Efficiency | Notes |
|---|---|---|---|
| 2026-10-02 14:55 | A- | B+ | Window open: runner 0.1%, app 0 to 0.7%, livefeed 0.1%. Closed: near 0 |
| 2026-10-04 21:00 | B+ | A | Full screen, window open, measured with `top -l 2` deltas: stream.py 0.5%, app 0%, runner 0% between renders. Fixed: map change check watches the picture (was re-rendering constantly), dots line up (frame.json uses the real centre). Fixed later the same night: the picture is now centred on the view point (all tile rows visible). snap.py also saves a small JPEG every 10 minutes to shots/timelapse/ for a morning timelapse (ffmpeg line in snap.py) |
| 2026-10-05 00:40 | B | C | Honest re-measure, fullscreen, window open, engineer walking, `top -l` deltas: app 29% before step 3, 30% after. stream.py 0.6%. The cost is SwiftUI/Core Animation redrawing the whole view every frame while the engineer moves (`sample` shows layout and CA commit, not file reads). Last night's 0% was an idle view. Next: cut the redraw cost (step 3b) |
| 2026-10-05 01:20 | B+ | B | Same setup after the hotbar icon cache: app about 10% (was 30%). Bisect: map only 3%, plus the animated layers about 9%, plus hotbar 32% before the fix. stream.py 0.6% |
| 2026-10-05 01:50 | B+ | A- | After splitting the eased position into `Glide`: app 5.4 to 5.5% (was 10%), stream.py 0.6%, total about 6.1%. Goal is under 5%: remaining cost is the animated layers (6 TimelineViews, 10 to 30 Hz) |
| 2026-10-05 02:40 | A- | B+ | Final QA, fullscreen, window open, engineer walking, `top -l 3` deltas: app 5.0%, stream.py 0.5%, livemap 0.2%, runner 0.0%. Total 5.7% of one core, goal was under 5%. Missed by 0.7. Cheapest remaining lever: ease timer 60 to 30 Hz saves about 1.7 points but makes the glide choppier, so not taken. Window closed: feeders sleep (designed near zero, not re-measured) |

## Cloud-safe work (no game, no Mac)

- `scripts/stream.py` plus tests with a fake RCON client (plan steps 1 and 2).
- Pure-function tests for `planner.py` (`tests/` has three test files so far).
- Docs and roadmap pruning.
- Not possible: Swift builds, anything that needs RCON, screenshots, CPU numbers.

## CI/CD

- **Tests** (`.github/workflows/test.yml`, every PR and push to main):
  - lint: compile every `.py`, ruff errors only, shellcheck errors only
  - every `tests/test_*.py` on Python 3.11 and 3.12. A new test file runs automatically.
  - the stream Lua runs in a real Lua 5.2 against a fake game
  - fails if a test wrote over a tracked file
  - the Swift app typechecks on macOS
  - doc and landing-page links resolve
- **Deploy** (`.github/workflows/deploy.yml`): after Tests pass on main, publishes `web/` to Cloudflare, but only when `web/` or the wrangler config changed, then checks the live page. Needs the repo secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. Without them it skips with a notice.
- Writing tests: `tests/fakes.py` has `install_rcon()` (a fake `factorio_rcon`, so scripts that connect at import still load) and `FakeRCON` (scripted replies, records every command). Plain asserts, print `ok`, no pytest needed.

## Rules that explain most of the repo

- **FLE state cannot be saved.** Every crash rolls the world back to the 10:55 copy. The defense is replay scripts, not saves: `scripts/health.sh --fix` runs all of them. Every new build gets its own replay script the same hour it is built.
- **`step.sh` takes one caller at a time.** Two callers shift every later result by one. The RCON-only scripts are safe to run alongside it.
- **Never `pkill -f` a pattern that also appears in your own command line.** Kill by PID.
- **Every wait loop needs a deadline.**
- **RAM: keep 40% free** (`health.sh` prints it). Never start autosave, Steam or the full game client.
- **Lua is 5.2:** no `//` operator. A `--` comment inside a joined RCON line silences the rest of it.
- **Assisted is not legit.** Say "assisted" whenever console help was involved.

## Restart prompt

```
/loop until we find a game we can beat today. Read docs/LOOP-HANDOFF.md and games/gdt/README.md. Each tick: check the Game Dev Tycoon run (python3 scripts/gdt.py show, pgrep -f gdt_play, /tmp/gdt_play.out, the tail of the newest runs/gdt log); fix stalls in scripts/gdt_play.py and restart it with .venv/bin/python scripts/gdt_play.py --minutes 600; never touch save slot 3; log bankruptcy dates and review scores honestly. Win: the game reaches Y35 M12 W4 and scores itself. Label play unassisted and topic/genre choice assisted by guide data. Hard stop at 90% usage.
```
