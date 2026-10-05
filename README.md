<img src="icon.svg" width="80" style="border-radius:18px">

# Conveyer

![version](https://img.shields.io/badge/version-v2.1.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) [![GitHub](https://img.shields.io/badge/GitHub-nulljosh%2Fconveyer-black?logo=github)](https://github.com/nulljosh/conveyer)

An LLM plays Factorio. On a real save.

It reads the game as data, not pixels. Each turn it picks one move from a short list. The move checks its own result, and the game answers. [Live](https://conveyer.heyitsmejosh.com).

Built on [FLE](https://github.com/JackHopkins/factorio-learning-environment), the Factorio Learning Environment.

## Where it is

<!-- progress:start -->
**Road to the rocket: 100%** `####################` 44 of 44 techs the silo needs. Rockets launched: 2 (v1.0 assisted: purple and yellow science were console-fed; v2.0 with no console-fed parts).
<!-- progress:end -->

It plays a copy of a real 2,300 entity base and builds the rest itself: a planner lays out assembler tiles, a loop feeds them, and replay scripts rebuild everything after a crash. Two rockets have launched. The first was assisted. The second, at 20:45 on 2 October 2026, had no console-fed parts. A server crash later that night rolled the world back, so the video relaunch is labelled assisted.

<img src="progress.svg" width="480" alt="Techs researched and entities built over time">

## Run it

You need a licensed Factorio (2.0.73 or newer), Docker, and a token from [factorio.com/profile](https://www.factorio.com/profile). On a Mac, use [colima](https://github.com/abiosoft/colima) and keep the repo under `$HOME`.

```bash
# .env: FACTORIO_USERNAME=... FACTORIO_TOKEN=...
pip install -r requirements.txt
set -a; source .env; set +a
fle cluster start -n 1 -s open_world
python3 runner.py --env-id open_play
./step.sh '{"skill": "inspect", "params": {}}'
```

To play your own save, run `scripts/world.sh`. It boots the server on a copy and never touches the original. `scripts/world.sh back` returns to the test map. Then `python3 runner.py --env-id open_play --keep-world`.

## Watch it

- **Live window:** `menubar/build.sh`, then `ConveyerMonitor.app --open-live`. Map, machine status dots, the engineer, a terrain minimap, the key stock bar, an activity feed, and the rocket silo drawn with the game's own sprites (`scripts/silo_sprites.py`, from your Steam install, never committed). Ctrl+Option+P pins it, Ctrl+Option+H hides the research panel.
- **Video:** `scripts/record.sh` captures the screen, `scripts/make_video.py` cuts it.
- **Terminal:** `python3 scripts/tui.py`.
- **Never join with a real Factorio client.** It forces a map save, the save fails, and the server quits. See [docs/LEARNINGS.md](docs/LEARNINGS.md).

## Rules and tests

Every session follows [docs/RULES.md](docs/RULES.md). CI runs every test on each pull request.

## How it works

<img src="architecture.svg" width="600">

`runner.py` stays alive and reads a skill from `runner_cmd.json`. `skills.py` turns it into code FLE runs against the server, and the result comes back as the next observation. A planner builds and feeds assembler tiles on its own. Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), lessons in [docs/LEARNINGS.md](docs/LEARNINGS.md), training a model of our own in [docs/TRAINING.md](docs/TRAINING.md).

## License

MIT 2026, Joshua Trommel. Factorio is property of Wube Software. This project is unaffiliated and does not distribute the game.
