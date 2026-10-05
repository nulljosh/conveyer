# Game Dev Tycoon

An agent plays Game Dev Tycoon through `conveyer-bridge`, a mod with no network and no code execution.

Install: copy `conveyer-bridge/` into the game's `mods/` folder and add `conveyer-bridge` to `enabledMods` in the game's settings. The mod writes `state.json` and reads `cmd.json` in `~/Library/Application Support/conveyer-gdt/` (not under Documents, so macOS never prompts). `scripts/gdt.py` is the other end.

Measured 2026-10-05: the game clock runs at about 15 weeks a minute at normal speed, in front or behind another app. The game ends at Y35 M12 W4 and scores itself.

## Run log, 2026-10-05

**Correction.** The first run's write-up said development stalls while the window is hidden. That was wrong. The game waits for two button presses at the end of a game: the green **Finish** button under the top bar, then **Release Game** in the dialog that follows. The first driver pressed neither, so Game #1 sat at "Finishing..." for two game years until the studio went bankrupt. Whether the game keeps running while hidden is untested (the clock does: about 15 weeks a minute either way).

**Driver** (`scripts/gdt_play.py`): presses routine dialogs, the Finish and Release Game buttons, the bank bailout (Agree), picks our own studio's save slot only (slot 3 holds Joshua's real 2014 save and is never touched), then starts the next game with the least-used topic and genre and the cheapest platform it can afford. It logs every decision to `runs/gdt/` (gitignored).

**Traps found:** Steam must be running or the game never loads mods; the cloud settings file resets `enabledMods`, so enable the mod from the game's Mods menu; a newsletter popup sits in the page text but never on screen; review dialogs animate for about 20 seconds before their Close button appears; the studio burns about 8K a month from the start, so the first game has to ship fast.

**Labels:** unassisted by the rules in the driver's docstring (screen text and read-only state, no writes to cash, dates or saves). The character is a man named Joshua; the studio is Conveyer Games.
