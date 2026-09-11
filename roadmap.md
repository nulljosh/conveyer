# Roadmap

Organized by when it's realistic to do, not by feature area — see priority buckets below.
History of what already shipped is at the bottom.

## In-game milestones (the single source of truth for progress)
Realistic timeframe per milestone — these get much harder to reach in order, not linearly.
Sub-bullets are the real, current blow-by-blow status.
1. [x] Character exists and can be spectated live — **done**
2. [x] Character moves under its own commands (`move_to` succeeding) — **done**
3. [x] First entity placed successfully (drill on real ore) — **done**, reliable now after
       fixing coordinate-guessing and prototype-name bugs
4. [x] First two entities connected (drill → furnace placed together) — **done once**, not
       yet stable run-to-run
5. [ ] First smelted item produced (real iron plate in inventory) — **this weekend**
   - [ ] Fuel drill + furnace with coal (`insert_item`) — not yet reached in a clean run
   - [ ] Connect drill → furnace (belt, or entity at drop position) — not reached
6. [ ] First assembled item produced (iron gear wheel via assembler) — **this weekend**
   - [~] Place assembler + set recipe (`RecipeName.X` enum) — reached once, not stable
   - [ ] Craft the assembler item before placing it — found 2026-09-11, `place_entity` needs
         the item in inventory first; fix applied, not yet re-verified
   - [ ] Connect furnace → assembler — not reached
   - [ ] Power the assembler — untested; needs electricity, not burner fuel, and nothing has
         set up a power grid yet
   - [ ] Verify real output via `inspect_inventory()` — the actual "smelted+assembled" finish
         line
7. [ ] First full automated loop running unattended, no manual prompt fixes — **weeks**
   - [ ] N consecutive clean runs with zero prompt intervention (target: 5) — this is the real
         bar, not one lucky run
   - [ ] Power grid automated end to end (boiler → steam engine → poles), not just placed once
   - [ ] Belt/inserter throughput actually sustained over a multi-minute window, not just
         "placed and connected"
8. [ ] First research completed — **weeks**
   - [ ] Automation science packs produced continuously (needs 5-7 working first)
   - [ ] Lab placed, powered, and fed packs via belt/inserter
   - [ ] `set_research(...)` called and progress observed via `get_research_progress()`
9. [ ] First monster encounter/kill (open_world only) — **weeks**
   - [ ] Base expands far enough to reach biter territory (lab scenario has none; open_world
         does, but spawn area is typically peaceful)
   - [ ] Agent has a weapon crafted/equipped — nothing in the current prompt teaches combat
         API calls at all, this needs its own system-prompt section from scratch
10. [ ] First rocket launched — **months+**, not a session goal, ever
    - [ ] Would require automating every prior milestone plus oil processing, plastics,
          rocket parts, and a satellite — realistically needs a bigger model or many more
          sessions of prompt-tightening than an 8B local model + one Claude session can do

## Tooling shipped
- [x] `scripts/tui.py`: cheap ASCII live view over RCON (positions only, no render/screenshot
      load) — real drill/furnace/character positions confirmed showing correctly.
- [x] `scripts/watch.sh`: raw play-by-play tail of the latest run transcript, no game
      connection needed at all.
2-4 more fix cycles is a reasonable guess once past the unreached steps above.

## This weekend
- [ ] Move conveyer (and pwnlingo) to real server space (DigitalOcean-style VPS) so they run
      when the Mac is off — native Linux also sidesteps colima entirely.
- [ ] Live mirror on the landing page (conveyer.heyitsmejosh.com): the actual running game
      state, not a static demo video. Reuse pwnlingo's pattern (status app + Playwright runner
      + public tunnel, e.g. pwnlingo-status.heyitsmejosh.com) rather than building this from
      scratch — it already solves "expose a locally-running agent's live state to the web."
- [ ] Bidirectional control: let a viewer send an instruction into the running agent loop
      between steps, not just watch. Small addition once the status-app pattern above is
      wired up — an endpoint that queues a user message into the next turn's context.
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
