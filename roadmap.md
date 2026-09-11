# Roadmap

Organized by when it's realistic to do, not by feature area — see priority buckets below.
History of what already shipped is at the bottom.

## Today (remaining usage this session)
- [ ] Get the model to actually finish a drill → furnace → assembler chain instead of erroring
      out partway (currently: real drill placed on real ore, then a wrong-prototype-name error
      broke the rest of the chain — fix applied, re-verifying now).
- [ ] Once a chain completes once, let a longer run (15-20 steps) try to hit real iron-plate
      output — the actual "we have a base" bar.

## This weekend
- [ ] Move conveyer (and pwnlingo) to real server space (DigitalOcean-style VPS) so they run
      when the Mac is off — native Linux also sidesteps colima entirely.
- [ ] Live mirror on the landing page (conveyer.heyitsmejosh.com): the actual running game
      state, not the canned terminal-transcript demo. Needs the server's game state exposed to
      the public web — screenshots/video pushed somewhere, or a small backend endpoint.
- [ ] Pick a first bounded FLE task deliberately (e.g. `iron_ore_throughput`) rather than
      whatever `pick_default_env()` guesses, once the base-building loop is reliable.

## Next few weeks
- [ ] **Gap analysis vs. [AI Player v3](https://mods.factorio.com/mod/ai-player-v3)** (found
      2026-09-11 researching similar projects) — the closest comparable to conveyer, worth
      adopting from rather than reinventing:
  - Their architecture: a fixed library of deterministic skills (mine, build, defend, etc.)
    plus primitive actions, with a small LLM acting only as a *router* choosing which skill
    and parameters to use. Conveyer generates raw Python from scratch every turn — far more
    surface area for syntax/API mistakes (most of this session was patching exactly that).
  - Their LLM only classifies/picks — can be much smaller/cheaper than a model that has to
    write correct code every time. Explains why their approach is more reliable per-step.
  - They likely have skills for combat/defense already; conveyer has none (currently pinned to
    the peaceful `default_lab_scenario`, no biters to worry about).
  - Plan: fork/vendor their skill library as an alternative or complementary action layer —
    keep FLE's raw-code path for flexibility, add their skills as a fallback/primary path when
    reliability matters more than generality.
- [ ] Try a bigger/better model now that the plumbing and prompt are proven — either a bigger
      local model if hosted with real GPU, or a cheap hosted API (OpenRouter) for comparison.
- [ ] Expand past one throughput task to FLE's broader task suite / benchmark comparison.
- [ ] Guardrails on run length / spend per session once this isn't fully local-and-free anymore
      (matters the moment it's not just a local Ollama model).

## Months+ / open-ended
- [ ] General "plays well unsupervised" ambition — FLE's own benchmark shows even frontier
      models are weak at long-horizon factory optimization. Not a near-term goal; scope any
      further work as bounded subgoals (a specific throughput target), not "beat the game."

## Shipped
- [x] Landing page live at conveyer.heyitsmejosh.com, repo renamed conveyor → conveyer to match.
- [x] No `ANTHROPIC_API_KEY` needed — runs on local Ollama. Settled on `qwen3:8b` after
      `qwen2.5-coder:14b` (too heavy, laggy machine) and `1.5b-base` (non-instruct, produced
      garbage) both failed. qwen3's "thinking" mode silently burns the token budget through the
      OpenAI-compat endpoint — switched `agent.py` to Ollama's native `/api/chat` with
      `think: false`.
- [x] `a2a-sdk` pinned to `0.2.16` — FLE 0.4.3 breaks on the 1.x line (`TextPart` import gone).
- [x] `gym.make(env_id, run_idx=0)` — FLE 0.4.3 requires `run_idx`, agent.py didn't pass it.
- [x] Colima only mounts `$HOME` by default — repo was under `/tmp`, causing every bind-mount
      permission/missing-file error and a crash loop. Moved to `~/Documents/Code/conveyer`;
      resolved outright.
- [x] `FACTORIO_USERNAME`/`FACTORIO_TOKEN` from factorio.com/profile (Steam-linked account,
      reveal the token) — needed to pull the headless server via `fle cluster start`.
- [x] **Verified end to end**: model writes real FLE API code (not hallucinated Lua), it
      executes against the live server, real game errors come back, model reads and retries.
- [x] Model successfully placed a real `BurnerMiningDrill` on real iron ore after a rule
      against guessing raw coordinates (use `nearest()`/`nearest_buildable()` instead).
- [x] Fixed a wrong `Prototype.Furnace` reference (real name: `StoneFurnace`) and a
      restart-from-scratch pattern where the model abandoned its own placed entities after any
      error instead of continuing to build on them.
