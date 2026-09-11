# Roadmap

## Setup
- [x] Docker via colima (not Docker Desktop) — works on macOS, but this machine is 16 GB and
      colima + a live Factorio server + anything else heavy caused one full OOM/reboot. Keep
      `fle cluster start -n 1`.
- [x] `pip install -r requirements.txt` — must pin `a2a-sdk==0.2.16`, FLE 0.4.3 breaks on the
      1.x line (`TextPart` import removed). `fle --list-envs` confirmed 13+ registered
      throughput tasks.
- [x] No `ANTHROPIC_API_KEY` needed — `agent.py` runs on local Ollama. `qwen2.5-coder:14b` was
      too heavy (CPU-only, laggy machine) and `1.5b-base` is a base model with no instruction
      tuning (produces incoherent garbage). Settled on `qwen3:8b` — but its "thinking" mode
      silently burns the whole token budget on hidden reasoning via the OpenAI-compat endpoint;
      had to switch `agent.py` to Ollama's native `/api/chat` with `think: false` to get it to
      actually answer.
- [x] `FACTORIO_USERNAME`/`FACTORIO_TOKEN` from factorio.com/profile (sign in with Steam if
      linked there, then reveal the token) — `fle cluster start` needs this to pull the
      headless server, Steam login alone doesn't cover it.
- [x] `fle cluster start -n 1` — pulled `factoriotools/factorio:2.0.73`, container
      `cluster-factorio_0-1` running.

## Agent loop
- [x] `agent.py`: REPL loop over FLE's gym env — sends the model's code, captures
      stdout/stderr, feeds it back as the next observation.
- [x] Logging: JSONL transcript per run in `runs/`
- [x] First live run against the real cluster surfaced a real bug: FLE 0.4.3's
      `make_factorio_env` requires `run_idx` — `gym.make(env_id, run_idx=0)`, not
      `gym.make(env_id)`. Fixed.
- [x] Container auto-discovery fails under colima (`NetworkSettings.Ports` comes back empty) —
      worked around with explicit `FACTORIO_SERVER_ADDRESS`/`FACTORIO_SERVER_PORT` in `.env`.
- [x] Factorio container crash-loops under colima's bind mounts — RESOLVED 2026-09-11: root
      cause was repo under `/tmp` (colima doesn't mount /tmp by default). Moved to
      ~/Documents/Code/conveyer, container boots clean now.
- [x] **Verified end to end 2026-09-11**: model writes real FLE API code (not hallucinated
      Lua), it executes against the live server, errors come back from the actual game
      ("Cannot place burner-mining-drill at x=0 y=0 — terrain unplaceable"), and the model
      reads them and retries with a different position each step. The full loop — model →
      FLE → RCON → live Factorio → error → model → retry — works.
- [x] Coordinate-guessing fix worked: model used `nearest(Resource.IronOre)` and successfully
      placed a real `BurnerMiningDrill` on real ore (x=16, y=71).
- [x] Found + fixed: model tried `Prototype.Furnace` (doesn't exist, should be
      `Prototype.StoneFurnace`) and, worse, restarted from scratch each step instead of
      continuing on what it already placed. Added explicit rules for both.
- [ ] Actual base — drill → furnace → assembler chain producing real iron plates, not just one
      entity placed — this is model capability, not plumbing. FLE's own benchmarks show even
      frontier models are weak at this; an 8B local model will need many iterations.
- [ ] Pick a first bounded task deliberately (e.g. `iron_ore_throughput`) rather than whatever
      `pick_default_env()` guesses.

## Later
- [ ] Live mirror on the landing page (conveyer.heyitsmejosh.com) showing the actual running
      game, not the canned terminal-transcript demo — needs the local game state exposed to
      the public web (screenshots/video pushed somewhere, or a small backend). Planned for
      this weekend alongside moving conveyer + pwnlingo to real server space so they can run
      when the Mac is off.
- [ ] Expand to FLE's broader task suite / benchmark comparison
- [ ] Guardrails on run length / API spend per session
