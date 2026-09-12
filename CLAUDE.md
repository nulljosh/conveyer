# Conveyer

Claude plays Factorio via [FLE](https://github.com/JackHopkins/factorio-learning-environment)
(Factorio Learning Environment), not a from-scratch RCON bridge. FLE already gives a Gym-style
Python API over Factorio's Lua mod API + RCON console, plus Docker orchestration of the
headless server(s). Don't rebuild that layer.

## Architecture (mid-refactor 2026-09-12, see roadmap.md)

Claude API (Anthropic) → `agent.py` (REPL loop) → **skill layer** → FLE (Python env, manages
the Lua/RCON bridge) → Factorio server (Docker, headless) → game state.

**The LLM no longer writes Python.** Old approach had the model synthesize a raw code
snippet every turn (see roadmap.md's 2026-09-12 local-model postmortem for why that failed:
small models get stuck re-guessing broken snippets instead of fixing them, and even
frontier models were pure surface-area for API/syntax mistakes). New approach, borrowed from
[AI Player v3](https://mods.factorio.com/mod/ai-player-v3): a fixed library of deterministic
Python skills (`mine()`, `smelt()`, `craft()`, `place()`, `build_power()`, ...) built once on
top of FLE's primitives, each validating its own inputs and verifying success against real
game state (inventory/entity checks via FLE) before returning. The LLM only picks a skill
name + structured JSON parameters each turn; it never emits code. `agent.py` parses that
JSON, dispatches to the matching skill function, and feeds the skill's structured result
(success/failure + reason, not raw stdout) back as the next observation.

Keep FLE itself untouched, it's still the only thing talking to the Lua/RCON bridge. The
skill layer is a thin dispatch table in front of it, not a replacement for it.

First goal for this architecture: reliably complete iron ore + coal → iron plate → iron gear,
end to end, driven entirely by skill calls (no raw code).

## Platform gotchas

- **macOS has no native headless Factorio.** The official headless server binary is
  Linux-only. Docker Desktop (works fine on Apple Silicon) is the real path, don't try to run
  the macOS client in `--start-server` mode as a substitute for the Docker flow FLE expects.
- **A licensed copy of Factorio is required.** FLE's core play loop doesn't strictly depend on
  the game client, but assume ownership is needed, don't build around license bypass.
- **`agent.py` runs on local Ollama, not Anthropic.** No API key needed, swap the client back
  to Anthropic only if you want Claude driving instead of a local model.
- **`a2a-sdk` must be pinned to `0.2.16`.** FLE 0.4.3 imports `TextPart` from `a2a.types`,
  which the 1.x line of `a2a-sdk` dropped. `pip install -r requirements.txt` pulls the pin;
  installing FLE bare will break on `from a2a.types import ... TextPart`.
- **Auth is a Factorio.com token, not Steam credentials.** `fle cluster start` needs
  `FACTORIO_USERNAME`/`FACTORIO_TOKEN` env vars to download the headless server, get the
  token from factorio.com/profile (sign in with Steam if you own it there, then reveal the
  token). Steam login alone doesn't give Docker anything to pull.
- **This machine is memory-tight (16 GB).** Colima's VM + a live Factorio server + a browser +
  background agent sessions stacked at once caused a full OOM crash and reboot. Keep `fle
  cluster start -n 1`, close what you don't need running, and don't stack another heavy task
  (video encoding, more Docker containers) on top of a live run.
- **Colima's `docker inspect` under-reports ports.** `NetworkSettings.Ports` comes back `{}`
  even though the mapping is real (`HostConfig.PortBindings` has it), a colima/VZ quirk.
  FLE's container auto-discovery (`fle/commons/cluster_ips.py`) reads the empty field and
  fails with "No Factorio containers available". Workaround: set `FACTORIO_SERVER_ADDRESS` and
  `FACTORIO_SERVER_PORT` explicitly (see `.env`) to skip discovery. RESOLVED 2026-09-11: the
  real issue was that the repo was under `/tmp`, which colima doesn't mount by default. Moved
  the repo to ~/Documents/Code/conveyer and the container boots clean.
- **Colima's default networking doesn't reliably forward UDP to `127.0.0.1`.** A real Factorio
  client trying to spectate the headless server got "Could not establish network communication
  with server" even though `nc -u -zv` "succeeded" (UDP is connectionless, that check doesn't
  prove a real round-trip works). Fixed by starting colima with `--network-address` for a real
  routable VM IP (`colima status` → `address:`) and connecting to that instead of `127.0.0.1`.
- **The Factorio image version is hardcoded in the installed `fle` package**, not `agent.py`. `fle/cluster/docker-compose.yml` (+ `run-envs.sh`/`run_envs.py`) pin
  `factoriotools/factorio:2.0.73`. A real Factorio client refuses to connect on any version
  mismatch, so watching live means sed-replacing that pin to match your client's exact version
  and restarting the cluster.

## Non-goals

- No vision/pixel-based control. Full game state is already exposed structurally; a vision
  model would be strictly worse engineering here.
- No general "beats the game like a pro" ambition yet. Start with bounded subgoals (automate
  iron plate production, hit a research milestone), FLE's own benchmark shows LLM agents are
  weak at long-horizon strategic play, so scope tasks accordingly rather than assuming the
  loop can just "play well" unsupervised.

## Roadmap

See [roadmap.md](roadmap.md).
