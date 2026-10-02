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
