# Architecture

Claude plays Factorio via Factorio Learning Environment (FLE), not screenshots. An agentic loop feeds full game state as structured data to Claude, which responds with skill calls (deterministic Python functions), rather than raw code synthesis. No undo button, no forgiving physics: the model must observe outcomes and decide what to do next.

## How it runs

`agent.py` drives the main loop, connected to a headless Factorio server via FLE. Each turn: Claude observes the game state (inventory, placed entities, status messages), outputs a JSON skill call (e.g. `{"skill": "mine", "ore_type": "iron"}`), `agent.py` dispatches to that skill function, the skill executes against the live server and validates success against real game state, then returns the result as the next observation. `runner.py` manages agent process lifecycle and output. `skills.py` holds the deterministic skill library; each skill calls FLE primitives and verifies its own success.

## Files

| File | What it owns |
|---|---|
| `agent.py` | Main LLM loop. Takes observations, calls Claude API (or local Ollama), parses JSON skill calls, dispatches to `skills.py`, feeds results back. Runs against a live FLE environment. |
| `skills.py` | Skill library. Deterministic Python functions (mine, smelt, craft, place, build_power, etc.), each validating inputs and verifying success via FLE's game state queries before returning a structured result. |
| `runner.py` | Agent process manager. Spawns `agent.py` as a subprocess, manages I/O, handles restarts and cleanup. |
| `bootstrap.py` | FLE cluster setup (start the headless Factorio server via Docker, verify connectivity). Env vars point to `FACTORIO_SERVER_ADDRESS` and `FACTORIO_SERVER_PORT`. |
| `status_writer.py` | Status page generator (Markdown or web). Tracks agent progress, game state snapshots. |
| `scripts/tui.py` | Terminal UI for monitoring agent runs live. |
| `scripts/progress_svg.py` | Chart generator for commit history. |
| `.env` | Factorio server address/port (hardcoded to skip colima's `docker inspect` quirk), Ollama endpoint. |
