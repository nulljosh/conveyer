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
- Video, "AI vs Factorio" (https://youtu.be/abrWwpGX_6U): GPT-6 Astra in Codex launched a rocket in vanilla Factorio with enemies on, 43h40m game time, about 4.5 days on the Codex /goal clock, about $4,500 in API cost. Harness: a client-side Lua mod reads game state and exposes input actions as MCP tools, plus an occasional screenshot. After biters broke its line it rebuilt with more turrets up front and a big ammo buffer. Takeaways for us: same shape as FLE plus skills.py (structured state, bounded actions), so no reason to switch to pixels; one long-running goal with persistent notes beat short scripted sessions; a frontier model at this cost is the ceiling, the claimed 50x saving came from offloading routine work to a cheaper model, which is our local-model plan; enemies are a real failure mode, so defend the supply lines (turrets plus an ammo buffer) before scaling. Transcript was not reachable here, summary is from search results and coverage.


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

- An unpowered inserter hid the whole oil problem for hours. A medium pole powers 3.5 tiles each way, so an inserter 4 tiles from the pole sits at no_power and silently stalls its machine. The emptier looked "full_output" and the refinery "fluid_ingredient_shortage", and I chased fluid theories for an afternoon. After one pole the refinery went from 21% to 102% duty. Read every placed inserter status once, not just the machine. Barrels (scripts/barrels.py) stay as the crude route because joined pumpjacks on the old pipe still failed.

- Coal is a flow, not a stock. Ten steam boilers at 10x game speed ate 44,000 coal in two hours and the plastic plant, which uses coal too, starved on an empty chest. The old coal drills sat blocked on a jammed belt. New drills that drop straight into chests (scripts/coalfarm.py) fixed it, but a new pole island is not on the grid until a pole bridges it: read the network id of anything you power.

- Pipe routers contaminate. A breadth-first pipe route laid through tank port tiles and next to another fluid's pipes sent 24,000 water into the heavy oil tank. Rules that worked: build every machine and its own pipes first, route the long water pipe last, keep the planned tiles of other fluids reserved, and join machines with a single pipe on the shared port tile instead of routing. Check the fluid in every tank and port pipe after a route.

- A negative number after a minus sign is a Lua comment: x-%g with %g = -12.5 became x--12.5 and silently ate the rest of the joined line. Wrap substituted numbers in parentheses.

## Never join the server with the real Factorio client (2026-10-02)
A client join makes the server save the map for the transfer. The game state cannot be saved (the scenario's `on_save` errors), so the server quits
("Cannot save map ... scenario level caused a non-recoverable error") and the world reverts to the last copy. It happened once, at 21:11: the live
view had just reached its third rocket. The map preview exists for exactly this reason: it reads the game over RCON and never joins. `scripts/realshot.sh`
now refuses to run. A true-graphics view needs the save problem fixed first (find what the FLE Lua helpers put in `storage` that cannot be serialized).
- FLE cannot parse underground belts: while one exists near the engineer every skill call returns "Error getting entities while getting observation" (even a harmless one), and it clears when the undergrounds are removed. Tested 2026-10-04 on the real save. router.py still supports undergrounds (tested, and the pair links correctly in game), but route_belt uses belts only until FLE is fixed.
- FLE's can_place_entity reads every tile as blocked unless the engineer holds the item, so route_belt asks the game directly (router.scan_lua) and places with create_entity (router.place_lua), like the planner.

## 2026-10-05: first live runs of the trained picker, and a second game

- **The picker plays the opening for real.** On a fresh `iron_plate_throughput` map it found iron, mined with burner drills, smelted, placed an assembler and an inserter, and connected belts: 12 of 13 calls ran, reward 15. It then repeats `belt` forever. The retry (temperature 0.8) and a "that already worked, pick the next step" nudge in the prompt changed nothing, because the picker is greedy and was never trained on what comes after the first belt. The fix is data, not a louder prompt: runs that continue past the belt, or a planner that takes over after the opening.
- **mlx_lm.server trap.** A request whose `model` is anything other than `default_model` loads the plain base model without the adapter. The base model answered with a made-up skill ("Crafting"). Pass `--model default_model`.
- **macOS 27 refuses Don't Starve** ("damaged") even after re-signing and clearing the attributes. Uninstalled. FEZ and Papers, Please launch.
- **Game Dev Tycoon runs through a no-network mod** (`games/gdt/`), and its development only progresses while the window is visible, so a run needs the screen for about two hours. Details in `games/gdt/README.md`.
- **Colima wedges** after long sessions: the CLI says the daemon is not running while the host agent is alive. `colima stop --force` then `colima start` fixes it, and the Factorio container comes back with it.

### Claude passes `iron_plate_throughput` through the skill layer (2026-10-05)

Claude picked the skill calls by hand (`scripts/skill.py` against a live `runner.py`) on a clean `iron_plate_throughput` map: find iron, then mine, smelt and collect with burner drills and a furnace. The environment's own check returned **reward 17.0, terminated True** against a quota of 16 iron plates per 60 game seconds. No console help, only the skills in `skills.py`. The starting inventory is the benchmark's normal lab-play kit. The transcript is `runs/claude-iron-plate-pass-2026-10-05.jsonl` (about 8 calls).

What this is and is not: one easy task of FLE's 24 (the 16 a minute iron plate task), passed by Claude, not by the trained model. The trained model stops after the first belt. This run shows the next moves it never learned: more drills into the same furnace, then `collect` from the furnace. Throughput held only while the furnace had room (its output filled at 50 plates and dropped to 0 until I collected), so the pass is a moment, not a steady factory.
