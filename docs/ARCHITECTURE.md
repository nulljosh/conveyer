# Architecture

Conveyer is an AI that plays the factory-building game Factorio. Instead of looking at screenshots, it reads the game's real state (inventory, entities, research) as structured data and picks from a fixed list of moves, so it never has to guess pixels or write buggy code on the fly. It uses the Factorio Learning Environment (FLE), a bridge that exposes that structured game state and runs the game headless. No undo button, no forgiving physics: the model must observe outcomes and decide what to do next.

## Design principles

Factorio already exposes its state as structured data through FLE's Lua/RCON bridge. Throwing that away to make a vision model squint at pixels would be strictly worse engineering. Similarly, having Claude synthesize raw Python each turn leads to syntax and API mistakes on every turn, while small local models get stuck re-guessing broken code instead of fixing it. The solution is a fixed skill library: each skill is a small deterministic template built once on FLE's primitives, validates its own inputs, checks success against real game state (inventory/entity queries), and returns a structured result. Claude's only job is picking which skill to call and with what parameters (a JSON object). This separates the reasoning (what to do) from the execution (how to do it), where each layer can fail independently and be fixed without touching the other.

## How it runs

`agent.py` drives the main loop, connected to a headless Factorio server via FLE. Each turn: Claude observes the game state (inventory, placed entities, status messages), outputs a JSON skill call (e.g. `{"skill": "mine", "ore_type": "iron"}`), `agent.py` dispatches to that skill function, the skill executes against the live server and validates success against real game state, then returns the result as the next observation. `runner.py` manages agent process lifecycle and output. `skills.py` holds the deterministic skill library; each skill calls FLE primitives and verifies its own success.

## Files

| File | What it owns |
|---|---|
| `agent.py` | Main LLM loop. Takes observations, calls Claude API (or local Ollama), parses JSON skill calls, dispatches to `skills.py`, feeds results back. Runs against a live FLE environment. |
| `skills.py` | Skill library. Deterministic Python functions (mine, smelt, craft, place, build_power, auto_feed, belt, research, etc.), each validating inputs and verifying success via FLE's game state queries before returning a structured result. |
| `router.py` | Belt routing for the `route_belt` skill: A* between two tiles around obstacles, with underground hops supported in the router (tested) but off in the skill because FLE cannot observe undergrounds. Also builds the one-line RCON commands that scan free tiles and place the route. |
| `runner.py` | Persistent FLE environment manager. Loads the gym environment once, keeps it alive across turns to avoid re-registering Lua actions (~30 on every reset). Reads JSON commands from `runner_cmd.json`, dispatches skill calls, writes results to `runner_result.json`, bumps `runner_seq.txt` so callers can await the exact result they need instead of sleeping. |
| `bootstrap.py` | Batch orchestrator for running the full vanilla-to-iron-chain sequence end to end. Calls `step.sh` repeatedly with skill payloads, retries on known game logic failures. |
| `step.sh` | IPC bridge. Reads the sequence counter before writing a command to `runner_cmd.json`, then polls the counter until it changes, ensuring the caller gets *their* result, not a stale one from a prior turn. |
| `status_writer.py` | Sidecar status page generator. Watches `runner_seq.txt` and parses fresh results from `runner_result.json`, aggregates entity positions (regex over skill messages), plays milestone sounds, writes `status.json` for menu-bar app polling. |
| `scripts/tui.py` | Terminal UI for monitoring live runs: shows current skill, game state, recent history. |
| `scripts/progress_svg.py` | Chart generator (commit history progress line). |
| `scripts/cpu_guard.sh` + `scripts/watch.sh` | Process guardians (restart runner if it hangs, monitor resource usage). |
| `menubar/` | Menu-bar app scripts (`restart_runner.sh`, `restart_server.sh`, `stop_all.sh`, `build.sh`). Shortcuts for starting/stopping the cluster and agent from macOS menu bar. |
| `scripts/world.sh` | Boots the Factorio server on a copy of a real save (`world.sh back` restores the stock map). Original save is never touched. |
| `scripts/science.sh` | One hand-crafted science cycle: fetch plates from base chests, craft red and green, load labs. |
| `scripts/feedlabs.py` | Moves science packs from the character into every lab over RCON (FLE's get_entity fails on a lab that already holds packs). |
| `scripts/fuel.py` | Tops boilers and fuel-hungry furnaces up with coal over RCON. |
| `scripts/snap.py` | Every 5 min copies the live map into `shots/` and appends a benchmark row (entities, techs, steps, ok, memory) to `shots/bench.jsonl`. Stops when the runner stops. |
| `docs/LEARNINGS.md` | One-line lessons from the real save, newest last. |
| `docs/LOOP-HANDOFF.md` | Current session state and restart prompt. |
| `web/` | Landing page (`index.html`). Deployed to conveyer.heyitsmejosh.com. Shows project info, GitHub link, live Factorio game state (via v86 embedded emulator), usage instructions. No code required from visitors, just static HTML/CSS. |
| `.env` | Configuration. `FACTORIO_SERVER_ADDRESS`, `FACTORIO_SERVER_PORT`, `OLLAMA_ENDPOINT`. Hardcoded to work around colima's `docker inspect` limitation. |

## Real save mode

`runner.py --keep-world` patches FLE before it initialises: no reset, adopt the save's character, keep biters. A single `runner.lock` stops duplicate runners. `get_entities()` is capped at 30 tiles around the character so observations stay small, and a memory guard exits the runner at 3 GB and removes `runner.pid` so the menu bar does not restart it into the same problem. `skills.py` has a `goto` skill for walking to far chests.

## Storage and IPC

State flows through the filesystem:

- **`runner_cmd.json`**: Latest skill call, written by clients (agent, bootstrap, manual), read by `runner.py`.
- **`runner_result.json`**: Latest skill result (success/failure, observation, inventory state). Written by `runner.py`, read by `status_writer.py`, `bootstrap.py`, TUI.
- **`runner_seq.txt`**: Counter bumped after every result write. Clients poll this instead of sleeping, so they get notified when *their* exact result lands.
- **`status.json`**: Clean aggregated status for menu-bar app polling: current skill, game state, milestone sounds triggered.
- **`status_log.json`**: Rolling window of 100 recent steps (newest first), for history and replay.
- **`map.json`**: Entity positions (extracted from skill message text via regex), max 60 entities, no extra game calls.

No central database. Every state lives in JSON files, so the system is transparent (tail them, grep them) and recoverable (no lost connections, no sessions to manage).

## Platform notes

- **No native headless Factorio on macOS.** Docker Desktop (colima) provides a Linux VM; FLE orchestrates the container via docker-compose.
- **Factorio.com token required.** Not Steam credentials. Get the token from factorio.com/profile (after signing in with Steam if you own it there).
- **Memory-tight.** 16 GB machine + colima + Factorio server + browser + agent session can OOM. Keep the cluster at `--workers 1`.
- **UDP networking.** Colima's default bridged mode doesn't reliably forward UDP to `127.0.0.1`. Start colima with `--network-address` for a routable VM IP.


## Real save scripts (2026-10-02)

The agent plays Joshua's real save through a planner and a set of replay scripts, all under `scripts/`. Everything is Python over RCON, one persistent connection each, no daemons of ours (the loop runs them as Claude background tasks).

| Script | What it does |
|---|---|
| `planner.py` | Builds and feeds tiles (assembler, input chest, inserters, output chest). `step` places one tile per pass and feeds every chest, `labs` feeds the labs, `replay` rebuilds tiles after a crash. Recipes, buffers (`BUF`) and tile counts (`MULT`) live at the top. |
| `keepbusy.sh` | The 20 second loop: planner step, oil refill, speed governor, labs and lab feeding, fuel. Exits when `runner.pid` is gone. |
| `tick.sh`, `health.sh` | One compact report per loop tick. `health.sh --fix` starts what is down and, after a world revert, replays every build. |
| `speed.py`, `cpu.sh` | Game speed follows CPU load and free RAM (10, 6, 3, 2x). `cpu.sh` measures each process. |
| `queue.py` | Keeps the research queue on the rocket-silo path, prerequisites first, cheapest first. |
| `research_status.py`, `stream.py`, `livemap.py`, `snap.py` | The monitor's feeds. Research and labs (`research.json`), one RCON connection for position, machine status dots, combat, key stock and the silo (`stream.py`, tiered 10 Hz down to 0.5 Hz), the strolling player (`livemap.py`), benchmark rows (`shots/bench.jsonl`). All sleep unless the monitor touches `.watching`. `stream.py` backs off 1 to 30 s when the server is down. |
| `terrain.py` | Paints real ground under the FLE render, writes `preview_map.png`. |
| `oil.py`, `sulfur.py`, `advcircuit.py`, `power.py` | The oil block (refinery, plastic plant with an output chest and a coal chest refilled every pass), the sulfur plant with 90 tiles of underground water, one advanced circuit assembler, and steam power columns. All idempotent. |
| `acid.py` | Sulfuric acid plant beside the sulfur plant, an underground acid line to a free field, and four processing unit assemblers on it. `acid.py feed` moves iron, circuits and advanced circuits into their chests every pass. Idempotent replay. |
| `oilfield2.py`, `ledger.py`, `concrete.py`, `advoil.py`, `fuelsupply.py`, `blocks.py`, `fuelgas.py`, `refineries.py`, `barrels.py`, `coalfarm.py`, `pumpjacks.py` | The generic builder (place, read fluid ports, power chain, pipe router, free-spot search), more refineries each with a barrel emptier, crude by barrel from the four rich wells, ten coal drills dropping into chests (coal fell from 50,000 to 6,000 in two hours of steam power), and the pumpjack experiment kept for reference. |
| `ironfarm.py` | Drill, furnace, inserter, chest slots on the iron, copper or stone patch, plus a pole bridge back to the grid. Slot lists freeze in `.world/*farm.json`. |
| `labs.py`, `feedlabs.py`, `withdraw.py`, `fuel.py` | Lab grid, moving packs into labs, pulling items from chests and furnaces into the bag, filling boilers and furnaces. |
| `journal.py` | Snapshot, check and restore of the build list, because FLE's Lua state cannot be saved. |
| `assist.py`, `silo.py` | Assisted mode: tops the labs with every pack while `.assist` exists, and builds the rocket silo, rocket parts and satellite and launches. This is how v1.0.0 was reached, and it is labeled that way everywhere. |
| `milestone.py`, `ship_landing.sh`, `landing_sync.py`, `make_icon.py`, `statline.py`, `realshot.sh`, `oilprep.sh` | Proof GIFs, landing and README refresh and deploy, the icon, one detailed log line, a true graphics screenshot (needs a real client, crashes the server if left joined), and oil prep. |
| `export_training.py` | Turns `runs/*.jsonl` into `data/train.jsonl` and `data/valid.jsonl` for LoRA. See [TRAINING.md](TRAINING.md). |

## The monitor (`menubar/main.swift`)

A SwiftUI menu bar app signed with the Developer ID so macOS keeps its Documents permission across rebuilds. The popover shows the map, research and roadmap. The live window (`--open-live`, `--fullscreen` to opt in) floats above all windows by default (Ctrl+Option+P toggles), follows the player with a zoomed camera eased at 60 fps, draws the real Factorio engineer sprite (copied from the Steam install by `build.sh`, never into git), and pulses a dot on every machine (green working, amber waiting, red stuck). Ctrl+Option+H shows or hides the progress panel. The map picture only redraws when the runner steps, so new builds show as dots before they show as sprites.

## The live view (v2.1)

The menu bar app never talks to the game. It reads small files the loop writes, so a slow render or a crash cannot freeze it.

| File | Written by | What the window draws |
|---|---|---|
| `preview_map.png`, `frame.json` | `runner.py` | The map picture. `frame.json` records its real centre (the renderer's origin, which is where the engineer stood at render time), its size and 16 px per tile; every overlay maps world positions through it. It re-renders only when the entities inside the picture change (a hash of the picture area, not of the engineer's surroundings). |
| `live.json`, `live_status.json`, `engineer.json`, `stream.json` | `stream.py`, `livemap.py` | The engineer, the machine status dots, the line saying what he is doing (he patrols the four newest tiles). `stream.json` holds every part in one file. |
| `hotbar.json`, `silo.json` | `stream.py` | The key stock bar, and the silo (parts, status, rocket on the pad). |
| `events.json` | `events.py` | The activity feed: ledger moves, research, power, pumpjacks, launches. |
| `combat.json` | `stream.py` | Enemies, firing turrets. |
| `minimap.png`, `minimap.json` | `minimap.py` | The terrain minimap with base, oil and nests. |

The silo and rocket are the game's own sprites, composited by `scripts/silo_sprites.py` from the Steam install into `assets/silo/` (never committed).

## The launch path

`planner.py` builds low density structure tiles. The refinery and chemical plants make plastic and rocket fuel. `shuttle.sh` moves crude by barrel and runs `siloline.py`, which carries processing units, low density structure and rocket fuel from the base chests to three chests beside the silo. Fast inserters put them in, the silo crafts the 100 parts itself, and `siloline.py` calls `launch_rocket()` once the finished rocket stands on the pad. A `.hold` file pauses the launch, `.assist` disables it.

## Assisted tools (labelled as such)

`scripts/relaunch.py` puts the silo and a bank of parts back by console. `scripts/sweep.py` kills nests by console. The engineer is invulnerable on oil-field patrol. None of these count toward a legit launch.

## Never join with the real client

A client join forces a map save. FLE's Lua state cannot be saved, so the server quits and the world reverts. `scripts/realshot.sh` is disabled. See [LEARNINGS.md](LEARNINGS.md).

## CI and rules

`.github/workflows/test.yml` compiles every Python file, lints, runs every `tests/test_*.py` on Python 3.11 and 3.12 (including the stream Lua in a real Lua 5.2), typechecks the Swift app on macOS and checks doc links. `deploy.yml` publishes `web/` to Cloudflare after Tests pass on main. The rules every session follows are in [RULES.md](RULES.md).

## Video

`scripts/record.sh` captures the screen with ffmpeg avfoundation (`screencapture -v` writes nothing here). `scripts/make_video.py` cuts the take and the landing wallpaper.
