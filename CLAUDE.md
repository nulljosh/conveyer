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
- **Provider is Claude, not FLE's default.** FLE's eval harness natively supports OpenAI,
  Anthropic, Together, and OpenRouter. Point it at Anthropic (`ANTHROPIC_API_KEY`) explicitly
  rather than whatever the harness defaults to.

## Non-goals

- No vision/pixel-based control. Full game state is already exposed structurally; a vision
  model would be strictly worse engineering here.
- No general "beats the game like a pro" ambition yet. Start with bounded subgoals (automate
  iron plate production, hit a research milestone) — FLE's own benchmark shows LLM agents are
  weak at long-horizon strategic play, so scope tasks accordingly rather than assuming the
  loop can just "play well" unsupervised.

## Roadmap

See [roadmap.md](roadmap.md).
