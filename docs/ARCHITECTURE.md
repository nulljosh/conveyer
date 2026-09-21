# Architecture

Claude plays Factorio via Factorio Learning Environment (FLE), not screenshots. An agentic loop feeds full game state as structured data to Claude, which responds with skill calls (deterministic Python functions), rather than raw code synthesis. No undo button, no forgiving physics: the model must observe outcomes and decide what to do next.

## Design principles

Factorio already exposes its state as structured data through FLE's Lua/RCON bridge. Throwing that away to make a vision model squint at pixels would be strictly worse engineering. Similarly, having Claude synthesize raw Python each turn leads to syntax and API mistakes on every turn, while small local models get stuck re-guessing broken code instead of fixing it. The solution is a fixed skill library: each skill is a small deterministic template built once on FLE's primitives, validates its own inputs, checks success against real game state (inventory/entity queries), and returns a structured result. Claude's only job is picking which skill to call and with what parameters (a JSON object). This separates the reasoning (what to do) from the execution (how to do it), where each layer can fail independently and be fixed without touching the other.

## How it runs

`agent.py` drives the main loop, connected to a headless Factorio server via FLE. Each turn: Claude observes the game state (inventory, placed entities, status messages), outputs a JSON skill call (e.g. `{"skill": "mine", "ore_type": "iron"}`), `agent.py` dispatches to that skill function, the skill executes against the live server and validates success against real game state, then returns the result as the next observation. `runner.py` manages agent process lifecycle and output. `skills.py` holds the deterministic skill library; each skill calls FLE primitives and verifies its own success.

## Files

| File | What it owns |
|---|---|
| `agent.py` | Main LLM loop. Takes observations, calls Claude API (or local Ollama), parses JSON skill calls, dispatches to `skills.py`, feeds results back. Runs against a live FLE environment. |
| `skills.py` | Skill library. Deterministic Python functions (mine, smelt, craft, place, build_power, auto_feed, belt, research, etc.), each validating inputs and verifying success via FLE's game state queries before returning a structured result. |
| `runner.py` | Persistent FLE environment manager. Loads the gym environment once, keeps it alive across turns to avoid re-registering Lua actions (~30 on every reset). Reads JSON commands from `runner_cmd.json`, dispatches skill calls, writes results to `runner_result.json`, bumps `runner_seq.txt` so callers can await the exact result they need instead of sleeping. |
| `bootstrap.py` | Batch orchestrator for running the full vanilla-to-iron-chain sequence end to end. Calls `step.sh` repeatedly with skill payloads, retries on known game logic failures. |
| `step.sh` | IPC bridge. Reads the sequence counter before writing a command to `runner_cmd.json`, then polls the counter until it changes, ensuring the caller gets *their* result, not a stale one from a prior turn. |
| `status_writer.py` | Sidecar status page generator. Watches `runner_seq.txt` and parses fresh results from `runner_result.json`, aggregates entity positions (regex over skill messages), plays milestone sounds, writes `status.json` for menu-bar app polling. |
| `scripts/tui.py` | Terminal UI for monitoring live runs: shows current skill, game state, recent history. |
| `scripts/progress_svg.py` | Chart generator (commit history progress line). |
| `scripts/cpu_guard.sh` + `scripts/watch.sh` | Process guardians (restart runner if it hangs, monitor resource usage). |
| `menubar/` | Menu-bar app scripts (`restart_runner.sh`, `restart_server.sh`, `stop_all.sh`, `build.sh`). Shortcuts for starting/stopping the cluster and agent from macOS menu bar. |
| `web/` | Landing page (`index.html`). Deployed to conveyer.heyitsmejosh.com. Shows project info, GitHub link, live Factorio game state (via v86 embedded emulator), usage instructions. No code required from visitors, just static HTML/CSS. |
| `.env` | Configuration. `FACTORIO_SERVER_ADDRESS`, `FACTORIO_SERVER_PORT`, `OLLAMA_ENDPOINT`. Hardcoded to work around colima's `docker inspect` limitation. |

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
