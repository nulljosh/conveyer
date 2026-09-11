<img src="icon.svg" width="80" style="border-radius:18px">

# Conveyer

![version](https://img.shields.io/badge/version-v0.1.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) [![GitHub](https://img.shields.io/badge/GitHub-nulljosh%2Fconveyer-black?logo=github)](https://github.com/nulljosh/conveyer)

An LLM plays Factorio. For real. On a real server.

Not a vision model squinting at pixels. It gets the actual game state, entities, inventories,
recipes, research, the works, as structured data, and writes Python back. Place a drill,
connect a belt, set a recipe. The game runs it. The game tells it what happened. It writes the
next line.

The hard part was already solved by [FLE](https://github.com/JackHopkins/factorio-learning-environment)
(Factorio Learning Environment), the Lua/RCON bridge, the Docker orchestration, the
structured observations. Conveyer is the loop on top: feed the model what happened, get back
what to do next, run it, repeat.

FLE's own [0.3.0 benchmark](https://jackhopkins.github.io/factorio-learning-environment/versions/0.3.0.html)
ranks Claude ahead of GPT, Gemini, and Grok at this, and still finds every frontier model
loses track of what it's actually built and leans on manual crafting instead of real
automation. That's the gap conveyer is trying to close, one working belt at a time.

## Status

It works. A model has placed a real mining drill on real iron ore inside a real running
Factorio server and kept building from there. Full base still in progress, see
[roadmap.md](roadmap.md) for exactly where things stand and what's next.

<img src="progress.svg" width="480" alt="Entities placed per run">

Real entity-placement counts pulled straight from `runs/`. Regenerate after a run:
`python3 scripts/progress_svg.py`.

## Watch it live

Two ways, cheapest first:

**Terminal (near-zero cost)**, `python3 scripts/tui.py` polls player/entity positions over
RCON every few seconds and draws an ASCII map. No game client, no extra load on an already
CPU-strained Box64 container. Also `scripts/watch.sh` for a raw text play-by-play of the
latest run's transcript, no game connection at all.

**Real Factorio client (expensive)**, the headless server is a normal Factorio multiplayer
server. Open your own client (Steam or otherwise), go to Multiplayer → Connect to address, and
connect in. A live connected client adds real CPU load on top of Box64 emulation, expect
"server not responding" hiccups on constrained hardware. Fine on real server space.

Two gotchas on colima specifically:

- **`127.0.0.1` doesn't reliably forward UDP** under colima's default (shared) networking, the game connection silently fails ("Could not establish network communication with
  server"). Fix: start colima with a routable VM address (`colima start --network-address`)
  and connect to that instead, `colima status` prints it (`address: ...`). Worked reliably at
  `192.168.64.2:34197`.
- **Versions must match exactly.** Factorio refuses to connect otherwise. Check your client's
  version (top-left of the main menu) and set FLE's cluster to the matching
  `factoriotools/factorio:<version>` image, it's hardcoded in `fle/cluster/docker-compose.yml`
  (and `run-envs.sh`/`run_envs.py`) inside the installed `fle` package, not something
  `agent.py` controls.

## How it works

<img src="architecture.svg" width="600">

Each turn: Claude gets the stdout/stderr from the last action as its observation and returns
a Python snippet. `agent.py` runs that snippet through FLE against the Factorio server
container and feeds the result back as the next observation.

## Setup

Needs a licensed copy of Factorio (≥2.0.73) and Docker, [colima](https://github.com/abiosoft/colima)
works fine on macOS (Apple Silicon included); FLE's headless server runs in containers it
orchestrates itself, since Factorio's official headless binary is Linux-only. **Run the repo
from somewhere under `$HOME`**, colima only mounts `$HOME` into its VM by default, and
anything under `/tmp` will silently break with permission/missing-file errors.

Runs against a local [Ollama](https://ollama.com) model by default, no API key. Pull the
default model: `ollama pull qwen3:8b`. To use Claude instead, pass `--model claude-sonnet-5`
and set `ANTHROPIC_API_KEY` (needs swapping the client back in `agent.py`).

You'll also need a Factorio.com account token (sign in with Steam if it's linked there, then
reveal the token at [factorio.com/profile](https://www.factorio.com/profile)), `fle cluster
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
`--model`, `--max-steps`, `--max-tokens` are overridable, see `--help`.

## Credit

Built on [FLE](https://github.com/JackHopkins/factorio-learning-environment)
(Hopkins, Bakler, Khan et al.), not a from-scratch RCON bridge. Why rebuild a task suite and a
benchmark harness that already exists and already works.

## License

MIT 2026, Joshua Trommel. Factorio is property of Wube Software; this project is unaffiliated
and does not distribute the game.
