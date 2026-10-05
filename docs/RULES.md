# Rules

What every session and every loop tick follows. Each rule is here because breaking it cost hours. The story behind each is in [LEARNINGS.md](LEARNINGS.md) and [HISTORY.md](HISTORY.md).

## Never

- **Never join the game with a real Factorio client.** A join forces a map save. FLE's Lua state cannot be saved, so the server dies and the world rolls back.
- **Never `pkill -f` a pattern that appears in your own command line.** Kill by PID.
- **Never write a wait loop without a deadline.** One waited 39 minutes on a file.
- **Never run two callers against `step.sh`.** Results shift by one and a stale read looks like success.
- **Never clear entities in the real save.** Fetch from the chests, mine only what they lack.
- **Never run an unfiltered `get_entities()`.** On the big base it reached 18 GB. Cap the radius at 30 tiles.
- **Never start autosave, Steam or the full game client** without checking RAM. Keep 40% free.
- **Never write raw code as the model.** The model picks a skill and JSON parameters. Skills validate and verify against game state.
- **Never push a commit that turns CI red.** Run the tests first.

## Stability

- **Every new build gets a replay script the same hour.** A crash reverts the world to the saved copy. Replay is the only defense.
- **Check the first link, not the last.** A stalled chain is usually one empty chest or one unfueled machine at the start of it. Read the producer's status, not just its output.
- **Fix power before adding load.** After any revert: fuel the boilers, power the pumpjacks, then everything else.
- **Cap buffers.** Chests hold 16 stacks. Give every producer an output chest.
- **No silent failures.** A script that hits an error prints one line and says what it skipped. Wrap long calls in a deadline.
- **Every feeder sleeps while nobody watches.** `.watching` older than 8 seconds means do nothing and hold no socket.
- **Measure CPU with deltas** (`top -l 2`), never `ps` on a young process. It averages over the process's whole life.

## Playing

- **Grade partial progress, not only the final item.** An assembler placed, an inserter touching a belt, an ingredient inside a machine all count. (Wittman's blueprint video.)
- **Build the lowest-tier missing ingredient first.** Small tiles keep mistakes cheap. (Uehlinger's self-expanding factory.)
- **Give the model calculators, not spatial reasoning.** Belt routing, machine input and output positions, recipe closure. Hand-build a working baseline first. Keep protected zones in a memory file. (factorioctl, FactoMCP.)
- **Defend the supply lines before scaling.** Turrets up front plus an ammo buffer. After a loss, rebuild with more of both. (The Astra rocket run.)
- **One long goal with persistent notes** beats many short scripted sessions. The handoff file is the notes.
- **Say "assisted" whenever console help was used.** Console-fed packs, scripted silo parts and `sweep.py` kills are all assisted. Never call a run legit unless nothing was fed in.
- **Steam achievements cannot be earned here.** They need the Steam client and a save with no console commands. Our saves run on RCON, so track the earnable ones in-game only.

## Changing the repo

- **One small chunk per tick.** Commit by exact path, never `git add -A`.
- **A fix gets a test, a new script gets a test.** Tests use `tests/fakes.py`, plain asserts, and print `ok`. CI runs every `tests/test_*.py` automatically.
- **Docs are short.** Plain words, no em dashes, no emojis. The handoff stays under 100 lines. Old state moves to HISTORY.md.
- **Version:** bump `VERSION` per fix, tag per milestone.
- **Usage:** read the usage line on every message. At 90% of the session or the week, checkpoint and stop. Do not kill a running subagent, let it finish.
- **Run long scripts as Claude background tasks**, not nohup children. They die with the tool call.
