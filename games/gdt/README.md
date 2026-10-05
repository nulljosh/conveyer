# Game Dev Tycoon

An agent plays Game Dev Tycoon through `conveyer-bridge`, a mod with no network and no code execution.

Install: copy `conveyer-bridge/` into the game's `mods/` folder and add `conveyer-bridge` to `enabledMods` in the game's settings. The mod writes `state.json` and reads `cmd.json` in `~/Library/Application Support/conveyer-gdt/` (not under Documents, so macOS never prompts). `scripts/gdt.py` is the other end.

Measured 2026-10-05: the game clock runs at about 15 weeks a minute at normal speed, in front or behind another app. The game ends at Y35 M12 W4 and scores itself.

## First run, 2026-10-05: bankrupt in year 3 (not beaten, and the cause is the screen)

The driver (`scripts/gdt_play.py`) pressed the routine dialogs and the studio went bankrupt at Y3 M3 with Game #1 never released: its design and technology points sat at 11 and 11 for two game years. The week counter kept running (about 15 a minute, in front or behind another app) but development did not move while the game window was hidden. Development progress is tied to the rendered office, not only to the clock. So **Game Dev Tycoon only progresses while it is visible on a screen**, and a run needs the Mac's display for about two hours at normal speed (35 years is 1,680 weeks; 15 a minute is 112 minutes). The fast-forward key needs a supporter flag, so there is no speed-up.

Not beaten. Unassisted label for the driver: it reads only the visible screen text, and read-only game state (`GameManager.state`) for the idle check. It never writes cash, dates or saves. The bank's bailout (Agree) is a normal in-game choice.

Open: a visible-screen run (a second display or an overnight run with the screen awake) and a smarter first game. Needs Joshua's say-so because it takes over the screen.
