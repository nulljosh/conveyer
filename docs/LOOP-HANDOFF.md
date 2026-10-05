# Conveyer loop handoff

Updated 2026-10-05. v2.1.0. Loop paused. Read this file top to bottom. If you have time left, read [HISTORY.md](HISTORY.md).

## TLDR

- **The game is beaten.** v2.0.0 (2 Oct, 20:45) launched a rocket with nothing fed in by console. A crash rolled that world back, so the rocket in the video is labelled assisted.
- **Next goal: the live window.** Stream the game into `ConveyerMonitor` at 5 Hz or better while staying under 5% of one core. Watching costs nothing while the window is closed.
- **Hard rule: never join with a real Factorio client.** A join forces a map save, FLE's Lua state cannot be saved, the server dies and the world rolls back. The custom window is the only way to watch.

## Pick up in 60 seconds

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
2. **Deltas.** The Lua keeps the last machine statuses in `storage` and returns only the ones that changed, plus a full snapshot every 30 s. *Cloud-safe except the final check.*
3. **App reads one file, and only when it changes.** Swap the 0.2 s poll of 8 files for a `DispatchSource` file watch on `stream.json`. Run the 60 Hz ease timer only while the marker is moving. *Mac only (Swift build).*
4. **Tiled basemap.** Render 32x32 chunks, cache each chunk's PNG under the hash of its entities, and re-render only the chunks that changed, off the runner thread. This fixes the 28 s block. *Mac plus game.*
5. **Game speed follows load.** Run at 10x when the machine is idle and drop to 3x when it is hot (`scripts/speed.py`, `scripts/cpu_guard.sh`). *Mac plus game.*
6. **QA.** Take screenshots with `ConveyerMonitor --snapshot out.png --live` and measure CPU with `ps` with the window open and closed. Put the before and after numbers in the grades table below.

Done when: the window is open at 5 Hz or better and every feeder plus the app together stays under 5% of one core. With the window closed, idle cost is roughly 0.

### Live view grades

| When | QA | Efficiency | Notes |
|---|---|---|---|
| 2026-10-02 14:55 | A- | B+ | Window open: runner 0.1%, app 0 to 0.7%, livefeed 0.1%. Closed: near 0 |
| 2026-10-04 21:00 | B+ | A | Full screen, window open, measured with `top -l 2` deltas: stream.py 0.5%, app 0%, runner 0% between renders. Fixed: map change check watches the picture (was re-rendering constantly), dots line up (frame.json uses the real centre). Fixed later the same night: the picture is now centred on the view point (all tile rows visible). snap.py also saves a small JPEG every 10 minutes to shots/timelapse/ for a morning timelapse (ffmpeg line in snap.py) |

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
/loop Conveyer live window. Read docs/LOOP-HANDOFF.md. Each tick: cd ~/Documents/Code/conveyer, scripts/tick.sh, do the next unchecked step of "Live window: plan", measure CPU before and after, update the grades table, bump VERSION, tag, push. Keep the background tasks listed in the handoff running as Claude background tasks, refresh any older than 15 minutes. Any crash: scripts/health.sh --fix, then relaunch them. Never join with a real client. Hard stop at 90% usage.
```
