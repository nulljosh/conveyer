<img src="icon.svg" width="80" style="border-radius:18px">

# Conveyer

![version](https://img.shields.io/badge/version-v0.1.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) [![GitHub](https://img.shields.io/badge/GitHub-nulljosh%2Fconveyer-black?logo=github)](https://github.com/nulljosh/conveyer)

An LLM plays Factorio. For real. On a real server.

Not a vision model squinting at pixels. It gets the actual game state — entities, inventories,
recipes, research, the works — as structured data, and writes Python back. Place a drill,
connect a belt, set a recipe. The game runs it. The game tells it what happened. It writes the
next line.

The hard part was already solved by [FLE](https://github.com/JackHopkins/factorio-learning-environment)
(Factorio Learning Environment) — the Lua/RCON bridge, the Docker orchestration, the
structured observations. Conveyer is the loop on top: feed the model what happened, get back
what to do next, run it, repeat.

## Status

It works. A model has placed a real mining drill on real iron ore inside a real running
Factorio server and kept building from there. Full base still in progress — see
[roadmap.md](roadmap.md) for exactly where things stand and what's next.

<img src="progress.svg" width="480" alt="Entities placed per run">

Real entity-placement counts pulled straight from `runs/`. Regenerate after a run:
`python3 scripts/progress_svg.py`.

## Watch it live

The headless server is a normal Factorio multiplayer server — you don't need any custom
render pipeline to watch. Open your own Factorio client (Steam or otherwise), go to
Multiplayer → Connect to address, and enter `127.0.0.1:34197`. Client version has to match the
server's (`factoriotools/factorio:2.0.73`).

## How it works

<img src="architecture.svg" width="600">

Each turn: Claude gets the stdout/stderr from the last action as its observation and returns
a Python snippet. `agent.py` runs that snippet through FLE against the Factorio server
container and feeds the result back as the next observation.

## Setup

Needs a licensed copy of Factorio (≥2.0.73) and Docker — [colima](https://github.com/abiosoft/colima)
works fine on macOS (Apple Silicon included); FLE's headless server runs in containers it
orchestrates itself, since Factorio's official headless binary is Linux-only. **Run the repo
from somewhere under `$HOME`** — colima only mounts `$HOME` into its VM by default, and
anything under `/tmp` will silently break with permission/missing-file errors.

Runs against a local [Ollama](https://ollama.com) model by default — no API key. Pull the
default model: `ollama pull qwen3:8b`. To use Claude instead, pass `--model claude-sonnet-5`
and set `ANTHROPIC_API_KEY` (needs swapping the client back in `agent.py`).

You'll also need a Factorio.com account token (sign in with Steam if it's linked there, then
reveal the token at [factorio.com/profile](https://www.factorio.com/profile)) — `fle cluster
start` needs it to download the headless server. Put it in a `.env` (gitignored):

```
FACTORIO_USERNAME=your-username
FACTORIO_TOKEN=your-token
```

```bash
pip install -r requirements.txt
set -a; source .env; set +a           # load Factorio credentials
fle cluster start -n 1                # headless Factorio container(s)
python3 agent.py --list-envs          # see available tasks
python3 agent.py --env-id <task_id>   # run one; defaults to an iron-themed task
```

Each run writes a JSONL transcript (code, observation, reward per step) to `runs/`.
`--model`, `--max-steps`, `--max-tokens` are overridable — see `--help`.

## Credit

Built on [FLE](https://github.com/JackHopkins/factorio-learning-environment)
(Hopkins, Bakler, Khan et al.), not a from-scratch RCON bridge. Why rebuild a task suite and a
benchmark harness that already exists and already works.

## License

MIT 2026, Joshua Trommel. Factorio is property of Wube Software; this project is unaffiliated
and does not distribute the game.
