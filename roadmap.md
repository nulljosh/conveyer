# Roadmap

## Setup
- [ ] Install Docker Desktop, confirm FLE can spin up a headless Factorio cluster on macOS
- [ ] `pip install factorio-learning-environment`, run FLE's own example task to confirm the
      bridge works before writing any custom code
- [ ] Wire `ANTHROPIC_API_KEY` into FLE's eval harness config

## Agent loop
- [ ] `agent.py`: minimal REPL loop — send Claude's code to FLE, capture stdout/stderr, feed
      back as next observation
- [ ] Pick a first bounded task (e.g. automate iron plate production) rather than "just play"
- [ ] Logging: persist each turn's observation/action pair for later review

## Later
- [ ] Expand to FLE's broader task suite / benchmark comparison
- [ ] Guardrails on run length / API spend per session
