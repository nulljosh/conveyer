# Conveyer

Claude plays Factorio via [FLE](https://github.com/JackHopkins/factorio-learning-environment)
(Factorio Learning Environment), not a from-scratch RCON bridge. FLE already gives a Gym-style
Python API over Factorio's Lua mod API + RCON console, plus Docker orchestration of the
headless server(s). Don't rebuild that layer.

## Architecture

Claude API (Anthropic) → `agent.py` (REPL loop) → FLE (Python env, manages the Lua/RCON
bridge) → Factorio server (Docker, headless) → game state.

Each turn is code-synthesis, not discrete actions: Claude receives the previous action's
stdout/stderr as its observation and returns a Python snippet; `agent.py` executes that
snippet inside FLE and feeds the result back as the next observation. This mirrors FLE's own
eval harness pattern rather than inventing a new protocol.

## Platform gotchas

- **macOS has no native headless Factorio.** The official headless server binary is
  Linux-only. Docker Desktop (works fine on Apple Silicon) is the real path — don't try to run
  the macOS client in `--start-server` mode as a substitute for the Docker flow FLE expects.
- **A licensed copy of Factorio is required.** FLE's core play loop doesn't strictly depend on
  the game client, but assume ownership is needed — don't build around license bypass.
- **`agent.py` runs on local Ollama, not Anthropic.** No API key needed — swap the client back
  to Anthropic only if you want Claude driving instead of a local model.
- **`a2a-sdk` must be pinned to `0.2.16`.** FLE 0.4.3 imports `TextPart` from `a2a.types`,
  which the 1.x line of `a2a-sdk` dropped. `pip install -r requirements.txt` pulls the pin;
  installing FLE bare will break on `from a2a.types import ... TextPart`.
- **Auth is a Factorio.com token, not Steam credentials.** `fle cluster start` needs
  `FACTORIO_USERNAME`/`FACTORIO_TOKEN` env vars to download the headless server — get the
  token from factorio.com/profile (sign in with Steam if you own it there, then reveal the
  token). Steam login alone doesn't give Docker anything to pull.
- **This machine is memory-tight (16 GB).** Colima's VM + a live Factorio server + a browser +
  background agent sessions stacked at once caused a full OOM crash and reboot. Keep `fle
  cluster start -n 1`, close what you don't need running, and don't stack another heavy task
  (video encoding, more Docker containers) on top of a live run.

## Non-goals

- No vision/pixel-based control. Full game state is already exposed structurally; a vision
  model would be strictly worse engineering here.
- No general "beats the game like a pro" ambition yet. Start with bounded subgoals (automate
  iron plate production, hit a research milestone) — FLE's own benchmark shows LLM agents are
  weak at long-horizon strategic play, so scope tasks accordingly rather than assuming the
  loop can just "play well" unsupervised.

## Roadmap

See [roadmap.md](roadmap.md).
