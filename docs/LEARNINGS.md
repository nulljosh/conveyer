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
- The character was unarmed. Now: submachine gun, 100 magazines, heavy armor, 10 grenades (crafted from base chests via RCON). Base has 11 gun turrets, 683 walls, 39 gates, 2 cars, 692 belts, 1 locomotive. No nests within 150 tiles, evolution 0.40.
- Prior art worth stealing (factorioctl by MarkMcCaskey, FactoMCP, jerome3o/factorio-mcp): give the model calculators instead of spatial reasoning (A* belt routing with undergrounds, correct machine input/output positions), hand-build a working baseline first, keep zones and protected ore in a memory file. Our skills.py plus scripts/oil.py already follow the same shape; the missing piece is a route_belt skill.
- Remaining silo-path science: 4,350 red, 4,350 green, 3,350 blue, 1,600 purple, 1,000 yellow. Hand-crafting that is about 30 refill cycles, so red and green assemblers come first.
- A real Factorio client cannot join the server: joining forces the server to save the map to send it over, and FLE's Lua state cannot be saved, so it crashes exactly like an autosave (2026-10-02, 4753 s into the run). Live watching in the game is not possible while FLE is loaded. Screenshots from the runner are the only view. Recovery is `scripts/health.sh --fix`.
- Video, "A.I. Learns to Optimize Factorio Blueprints" (Alex Wittman): a genetic algorithm over blueprints stalls on random entity grids, because almost no random design makes anything. Fix: score partial progress (has an assembler, inserter touching a belt or assembler, an ingredient or product inside a machine) so the search gets a gradient, then use wave function collapse to generate only valid designs and optimize cost and output. Takeaways for us: grade the agent on shaped partial progress, not only the final item; generate tiles from constraints (every recipe input needs an inserter, one output inserter) the way planner.py does. A GA over our tile layout is a possible later step; it was slow even for a green circuit.
- Video, "Factorio Automated: A 1000SPM self-expanding factory" (Chris Uehlinger): the tier-and-demand tile idea behind scripts/planner.py. Tier = lowest tier with none of its ingredients. Build the lowest-tier missing ingredient first. Small tiles keep mistakes cheap. Robot logistics replaces belts; we use RCON moves until robotics is researched.


## 2026-10-02 lessons
- A stalled chain is usually one empty chest. The plastic plant's coal chest ran dry and starved advanced circuits, blue science and purple for hours. Look at the machine status of the first link before theorizing about the last.
- Sixteen-slot chests fill up. Steel and circuits at 300 crafts filled the chests of the purple tiles and left no room for brick or advanced circuits. Cap the buffer per recipe.
- At 10x game speed a plant fills its output between passes. Give every producer an output chest.
- Background children die with the tool call. Run long scripts as Claude background tasks and refresh them every 20 minutes.
- Lua in Factorio 2.0 has no `//` operator, and a `--` comment in a joined RCON line silences the rest of the script.
- macOS ties a Documents permission to the code signature. Ad-hoc builds ask again after every rebuild. Sign with a stable identity.
- The player never moves when everything runs over RCON, so the live view looked frozen. A strolling player and status dots made it readable.
- Assisted is not legit. Console-fed packs and a scripted silo reached the launch, and the release says so. A legit launch needs advanced oil, cracking, sulfuric acid, lubricant, rocket fuel, about 1,300 processing units and 1,100 low density structures.

- Silent failure is the worst failure: fuel.py died on "count must be positive" whenever the bag held no coal, and keepbusy hid its errors, so the far copper furnaces sat at no_fuel with 49k coal in chests. It now draws from the storage chests and guards the empty bag. Check a producer's status, not just its chest.

- Measure the camera instead of eyeballing it: CV_DEBUG=1 ConveyerMonitor logs every frame to /tmp/cv_cam.log (player position, screen position, black margins). It showed 16% of frames with black margins because the map picture was 68 tiles tall and the tile column runs 70 tiles. The picture is now 92 tiles tall: 0 black frames in 4,018.

- An inserter's direction here is the side it picks from, not the side it drops to. Both acid inserters and all eight assembler inserters were backwards the first time. Always read pickup_position and drop_position after placing one.
