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

## How it works

<img src="architecture.svg" width="600">

Each turn: Claude gets the stdout/stderr from the last action as its observation and returns
a Python snippet. `agent.py` runs that snippet through FLE against the Factorio server
container and feeds the result back as the next observation.

## Setup

Needs a licensed copy of Factorio (≥2.0.73) and Docker Desktop (FLE's headless server runs in
containers it orchestrates — macOS has no native headless binary).

Runs against a local [Ollama](https://ollama.com) model by default — no API key. Pull a
code-capable model first: `ollama pull qwen2.5-coder:14b`. To use Claude instead, pass
`--model claude-sonnet-5` and set `ANTHROPIC_API_KEY` (needs swapping the client back in
`agent.py`).

```bash
pip install -r requirements.txt
fle cluster start                    # headless Factorio container(s)
python3 agent.py --list-envs         # see available tasks
python3 agent.py --env-id <task_id>  # run one; defaults to an iron-themed task
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
