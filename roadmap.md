# Roadmap

## Setup
- [ ] Install Docker Desktop, confirm FLE can spin up a headless Factorio cluster on macOS
- [ ] `pip install factorio-learning-environment`, run FLE's own example task to confirm the
      bridge works before writing any custom code
- [ ] Wire `ANTHROPIC_API_KEY` into FLE's eval harness config

## Agent loop
- [x] `agent.py`: REPL loop over FLE's gym env — sends Claude's code, captures stdout/stderr,
      feeds it back as the next observation (untested against a live cluster — see below)
- [x] Logging: JSONL transcript per run in `runs/`
- [ ] Run it against a real local FLE cluster for the first time; fix whatever the real
      `Observation`/`Action` shapes don't match (written against FLE's source, not verified
      end-to-end since that needs Docker + a licensed Factorio copy)
- [ ] Pick a first bounded task deliberately (e.g. `--list-envs`, then an iron/circuit
      throughput task) rather than whatever `pick_default_env()` guesses

## Later
- [ ] Expand to FLE's broader task suite / benchmark comparison
- [ ] Guardrails on run length / API spend per session
