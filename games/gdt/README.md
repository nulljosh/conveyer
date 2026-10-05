# Game Dev Tycoon

An agent plays Game Dev Tycoon through `conveyer-bridge`, a mod with no network and no code execution.

Install: copy `conveyer-bridge/` into the game's `mods/` folder and add `conveyer-bridge` to `enabledMods` in the game's settings. The mod writes `state.json` and reads `cmd.json` in `~/Library/Application Support/conveyer-gdt/` (not under Documents, so macOS never prompts). `scripts/gdt.py` is the other end.

Measured 2026-10-05: the game clock runs at about 15 weeks a minute at normal speed, in front or behind another app. The game ends at Y35 M12 W4 and scores itself.
