<img src="icon.svg" width="80" style="border-radius:18px">

# Conveyer

![version](https://img.shields.io/badge/version-v0.1.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) [![GitHub](https://img.shields.io/badge/GitHub-nulljosh%2Fconveyer-black?logo=github)](https://github.com/nulljosh/conveyer)

Claude plays Factorio.

Conveyer is an agent loop that puts Claude in control of a real Factorio game through the
game's own Lua mod API and RCON console — no pixels, no vision model, just full structured
game state (entities, inventories, recipes, research, logistics) in and Python code out.

It's built on [FLE](https://github.com/JackHopkins/factorio-learning-environment) (Factorio
Learning Environment), an existing open-source Gym-style environment that already solved the
hard plumbing: the Lua/RCON bridge, Docker orchestration of headless Factorio servers, and
structured observations. Conveyer is the agent loop on top: it feeds Claude the environment's
output as an observation, gets back a Python snippet as the next action, executes it, and
repeats.

## Status

`agent.py` runs the loop end to end against any registered FLE task. Not yet run against a
live cluster on this machine — see [roadmap.md](roadmap.md).

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
(Hopkins, Bakler, Khan et al.) rather than a from-scratch RCON bridge — it already has the
task suite, benchmark harness, and native Anthropic support that would otherwise need
rebuilding.

## License

MIT 2026, Joshua Trommel. Factorio is property of Wube Software; this project is unaffiliated
and does not distribute the game.
