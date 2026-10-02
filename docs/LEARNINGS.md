# Learnings from the real save

Newest at the bottom. One line each.

- get_entities() with no filter scans the whole base every observation. On 2316 entities that was 18 GB. Cap the radius.
- Check the base before building anything. Joshua's chests hold 62k coal, 12k steel, 7k copper, 1.4k iron plate. Fetch from chests, do not mine from scratch.
- Research is the bottleneck: labs sit at missing_science_packs. Red is stocked, green (LogisticsSciencePack, with the s) is missing.
- Boilers are hand-fed with coal. Two of six are out of fuel. Fix fuel before adding load.
- place needs a direction (UP/DOWN/LEFT/RIGHT). smelt expects the drill to exist already. goto must come before collect on far chests.
- step.sh reads whatever result lands next, so never run two scripts against one runner at once. A stale read looked like success once.
- FLE get_entity breaks on a lab that already holds packs. scripts/feedlabs.py feeds labs over RCON instead. science.sh runs the whole cycle.
- Crafting 60+ packs outruns step.sh's old 30s wait and shifts every later result by one. Wait is 5 min now.
- Prior art: FLE itself (JackHopkins, 1.2k stars, the base we run on), Metta-AI/cogame-factorio, ProFrenchToast/FILE (FLE in Inspect AI), rsong9527/factorio-board (leaderboard), Eshan276/factorio-claude. No public fine-tune of a model on Factorio play found.
- Training idea: every runner step is already a (state, skill, result) row. Log them, keep the ok ones, fine-tune the local model on the picks.
- Iron stock in chests ran dry after ~1500 plates. scripts/withdraw.py pulls plates from furnace outputs over RCON (a shortcut, the character does not walk there). Real fix is automated iron into science.
- Game runs at ~7x real time and is not paused between steps, so labs finish units fast. Science pack supply is the limit, not lab count. Research queue held pack-wasting extras (fluid wagon, solar, defender); set a strict queue with force.research_queue.
- Cable chest ran dry. Hand-craft cable from copper plates instead (science.sh withdraws N*3 copper). SKIP_IRON=1 reuses plates already in the bag.
- The game was PAUSED between steps (FLE pause_after_action), so research and smelting froze whenever the player was not acting. runner.py now sets pause_after_action False. Check game.tick_paused first when research stalls with labs 'working'.
- A lab placed off the power grid keeps whatever you feed it (4 labs ate 152 green packs). feedlabs.py now skips labs with no electric network.
- Oil: the pipeline from the far pumpjack already reached the base. A train track crossed the pipe route, so it needed an underground pair. New buildings need a pole bridge to the grid (medium pole reach about 7.5 tiles). place_at ignores direction for plants, rotate over RCON.
- FLE's Lua state can't be saved: an autosave fails with 'scenario level caused a non-recoverable error' and kills the server. Every crash rolls back to the 10:55 copy. scripts/oil.py rebuilds the oil block in one command; rerun it after any restart.
