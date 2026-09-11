# Roadmap

## Setup
- [x] Docker via colima (not Docker Desktop) — works on macOS, but this machine is 16 GB and
      colima + a live Factorio server + anything else heavy caused one full OOM/reboot. Keep
      `fle cluster start -n 1`.
- [x] `pip install -r requirements.txt` — must pin `a2a-sdk==0.2.16`, FLE 0.4.3 breaks on the
      1.x line (`TextPart` import removed). `fle --list-envs` confirmed 13+ registered
      throughput tasks.
- [x] No `ANTHROPIC_API_KEY` needed — `agent.py` runs on local Ollama (`qwen2.5-coder:14b`) by
      default.
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
- [ ] Confirm a full bounded run (a few steps) completes cleanly end to end.
- [ ] Pick a first bounded task deliberately (e.g. `iron_ore_throughput`) rather than whatever
      `pick_default_env()` guesses.

## Later
- [ ] Expand to FLE's broader task suite / benchmark comparison
- [ ] Guardrails on run length / API spend per session
