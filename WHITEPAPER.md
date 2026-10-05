# Conveyer Technical Whitepaper

**v2.1.0** | October 2026

An AI plays Factorio on a real save and launches a rocket. No screenshots, no vision model. Factorio already
exposes its state as data, so Conveyer reads that and acts on it. On 2 October 2026 it launched a second rocket
with no console-fed parts. That is the claim, and the proof is one number: `rockets_launched` went from 1 to 2.

## The mechanic

The model never writes code. It picks a skill and gives it parameters. A skill is a small Python function
(`mine`, `smelt`, `craft`, `place`) that checks its own inputs and checks the game afterward. If it worked, it says
so. If not, it says why. That one rule ended the dead loops where a small model kept re-guessing a broken snippet.

Above the skills sits a planner. It reads the recipe tree from the game, works out what the launch needs, and builds
assembler tiles one at a time. A loop feeds them. Nothing in the plan is hand-placed.

## The ledger

The launch is a short list: 1,000 processing units, 1,000 low density structures, 1,000 rocket fuel. A ledger script
counts them from the game, not from memory. The silo has its own feed line: three chests, three inserters. The
silo crafts the parts itself and the launch fires when part 100 lands. We read the real recipe from the game
first. It cut the plan: no second silo, no satellite. A rocket with an empty hold still wins.

## Why a crash is cheap

The game's Lua state cannot be saved here. An autosave kills the server. So any crash puts the world back to an
old copy. The defense is replay, not saves. Every build has a script that rebuilds it in seconds, and one health
check brings the whole stack back. The loop itself restarts from a checklist in the repo.

## What is assisted

The first launch, on the same day, was assisted: the last science packs were fed through the console and the silo
was placed by script. The release said so. The second launch was not. No `.assist` file, no console parts.
Two things since then are assisted and labeled that way: the oil-field engineer cannot die, and the nest sweep
that cleared every monster was console kills. Real nest clearing needs military science, tanks and flamethrowers.
That is next.

## What you can watch

A menu bar app shows the base live: machine status, the engineer, a minimap, the key stock, and a feed of what
just happened. It follows one rule. It reads files the loop writes, and it never talks to the game itself.

## License

MIT 2026, Joshua Trommel. Factorio is property of Wube Software; this project is unaffiliated
and does not distribute the game.
