# Roadmap

Organized by when it's realistic to do, not by feature area, see priority buckets below.
History of what already shipped is at the bottom.

## In-game milestones (the single source of truth for progress)
Realistic timeframe per milestone, these get much harder to reach in order, not linearly.
Sub-bullets are the real, current blow-by-blow status.
1. [x] Character exists and can be spectated live, **done**
2. [x] Character moves under its own commands (`move_to` succeeding), **done**
3. [x] First entity placed successfully (drill on real ore), **done**, reliable now after
       fixing coordinate-guessing and prototype-name bugs
4. [x] First two entities connected (drill → furnace placed together), **done**, stable and reliable (5+ consecutive successful runs, best run placed 7 total entities)
5. [x] **Skill-layer refactor: LLM stops writing Python**, done 2026-09-12.
   - [x] `skills.py`: `mine`, `smelt`, `craft`, `place`, `build_power`, `inspect` as Python
         source templates rendered with `skills.render(name, params)`, filled in with FLE's
         existing primitives (`nearest`, `place_entity`, `insert_item`, `inspect_inventory`, etc.)
   - [x] Each template re-fetches entities by literal position and ends in an assert/print
         (`SKILL_OK`/`SKILL_FAIL`) so the observation states success/failure explicitly
   - [x] `agent.py`: LLM reply is now a ```json {"skill": ..., "params": {...}} fence, parsed
         and dispatched via `skills.render`, no raw code from the model ever reaches `Action`
   - [x] Kept FLE and the REPL loop shape untouched, only what crosses the LLM boundary changed
   - [ ] Not yet run against a live cluster to confirm iron ore + coal → plate → gear end to
         end with the new dispatch (`fle cluster start` wasn't up during this edit) — first
         thing to verify next session
6. [ ] First smelted item produced (real iron plate in inventory), **this weekend**
   - [ ] Fuel drill + furnace with coal (`insert_item`), not yet reached in a clean run
   - [ ] Connect drill → furnace (belt, or entity at drop position), not reached
7. [ ] First assembled item produced (iron gear wheel via assembler), **this weekend**
   - [~] Place assembler + set recipe (`RecipeName.X` enum), reached once, not stable
   - [ ] Craft the assembler item before placing it, found 2026-09-11, `place_entity` needs
         the item in inventory first; fix applied, not yet re-verified
   - [ ] Connect furnace → assembler, not reached
   - [ ] Power the assembler via `build_power()`, untested; needs electricity, not burner
         fuel, and nothing has set up a power grid yet
   - [ ] Verify real output via `inspect_inventory()`, the actual "smelted+assembled" finish
         line
8. [ ] First full automated loop running unattended, no manual prompt fixes, **weeks**
   - [ ] N consecutive clean runs with zero prompt intervention (target: 5), this is the real
         bar, not one lucky run
   - [ ] Power grid automated end to end (boiler → steam engine → poles), not just placed once
   - [ ] Belt/inserter throughput actually sustained over a multi-minute window, not just
         "placed and connected"
9. [ ] First research completed, **weeks**
   - [ ] Automation science packs produced continuously (needs 5-7 working first)
   - [ ] Lab placed, powered, and fed packs via belt/inserter
   - [ ] `set_research(...)` called and progress observed via `get_research_progress()`
10. [ ] First monster encounter/kill (open_world only), **weeks**
   - [ ] Base expands far enough to reach biter territory (lab scenario has none; open_world
         does, but spawn area is typically peaceful)
   - [ ] Agent has a weapon crafted/equipped, nothing in the current prompt teaches combat
         API calls at all, this needs its own system-prompt section from scratch
11. [ ] First rocket launched, **months+**, not a session goal, ever
    - [ ] Would require automating every prior milestone plus oil processing, plastics,
          rocket parts, and a satellite, realistically needs a bigger model or many more
          sessions of prompt-tightening than an 8B local model + one Claude session can do

## Tooling shipped

**2026-09-12 session: local-model attempt hit a hard wall, not a code bug.**
- Fixed two real bugs in `agent.py`: (1) system prompt didn't warn about `place_entity_next_to(entity, source.position, spacing=0)` placing ON the source's own footprint, guaranteed collision; (2) no repeat-guard, so a bad model could resubmit byte-identical code forever after an error — added a 2-repeat abort.
- Tried qwen3:8b, qwen2.5-coder:14b, qwen2.5-coder:1.5b-base, llama3.1:8b via Ollama, all on
  this 16GB Mac alongside the Factorio Docker cluster (which is itself tiny, ~450MB/2% CPU,
  never the problem):
  - qwen3:8b and qwen2.5-coder:14b: correct format but got stuck in dead loops re-guessing ore
    coordinates for a conceptually broken snippet instead of fixing the actual bug; 14b also
    caused a real prefill hang (30+ min single response) that crashed available RAM to ~80MB.
  - qwen2.5-coder:1.5b-base: wrong model variant (base, not instruct) — doesn't follow the
    chat/tool format at all, just hallucinates JSON.
  - llama3.1:8b: only one that ran without hanging, but left just ~200-500MB RAM headroom
    the whole time, too risky to leave unattended.
- **Conclusion: FLE's own docs assume a capable model (Claude/GPT-tier), not an 8B local
  one.** The raw-code-generation interface (write arbitrary Python every turn) needs real
  reasoning to debug its own mistakes; small local models keep repeating the same wrong
  fix. This matches the "Gap analysis vs. AI Player v3" note below — a skill-library
  router needs much less from the model than raw code synthesis does.
- Next real options, in order of effort: (a) run one short Claude-driven episode (needs an
  `ANTHROPIC_API_KEY` — none found on this machine, would need to be added) to validate the
  goal is reachable at all before investing in the skill-library rewrite; (b) build the
  skill-library layer from the AI Player v3 gap analysis so a small local model only has to
  route, not write code.

## This weekend
- [ ] Move conveyer (and pwnlingo) to real server space (DigitalOcean-style VPS) so they run
      when the Mac is off, native Linux also sidesteps colima entirely.
- [ ] Live mirror on the landing page (conveyer.heyitsmejosh.com): the actual running game
      state, not a static demo video. Reuse pwnlingo's pattern (status app + Playwright runner
      + public tunnel, e.g. pwnlingo-status.heyitsmejosh.com) rather than building this from
      scratch, it already solves "expose a locally-running agent's live state to the web."
- [ ] Bidirectional control: let a viewer send an instruction into the running agent loop
      between steps, not just watch. Small addition once the status-app pattern above is
      wired up, an endpoint that queues a user message into the next turn's context.
- [ ] Pick a first bounded FLE task deliberately (e.g. `iron_ore_throughput`) rather than
      whatever `pick_default_env()` guesses, once the base-building loop is reliable.

## Next few weeks
- [ ] Try a bigger/better model now that the plumbing and prompt are proven, either a bigger
      local model if hosted with real GPU, or a cheap hosted API (OpenRouter) for comparison.
- [ ] Expand past one throughput task to FLE's broader task suite / benchmark comparison.
- [ ] Guardrails on run length / spend per session once this isn't fully local-and-free anymore
      (matters the moment it's not just a local Ollama model).

## Months+ / open-ended
- [ ] General "plays well unsupervised" ambition, FLE's own benchmark shows even frontier
      models are weak at long-horizon factory optimization. Not a near-term goal; scope any
      further work as bounded subgoals (a specific throughput target), not "beat the game."
