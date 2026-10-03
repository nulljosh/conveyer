<img src="icon.svg" width="80" style="border-radius:18px">

# Conveyer

![version](https://img.shields.io/badge/version-v1.6.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) [![GitHub](https://img.shields.io/badge/GitHub-nulljosh%2Fconveyer-black?logo=github)](https://github.com/nulljosh/conveyer)

An LLM plays Factorio. On a real save.

It reads the game as data, not pixels. Each turn it picks one move from a short list. The move checks its own result, and the game answers. [Live](https://conveyer.heyitsmejosh.com).

Built on [FLE](https://github.com/JackHopkins/factorio-learning-environment), the Factorio Learning Environment.

## Where it is

<!-- progress:start -->
**Road to the rocket: 100%** `####################` 44 of 44 techs the silo needs. Rockets launched: 1 (v1.0, assisted: purple and yellow science were console-fed).
<!-- progress:end -->

It plays a copy of a real 2,300 entity base. Red, green, blue and purple science run on their own. A rocket has launched once, with help: the last packs were fed to the labs by script and the silo was placed by script. Next is a launch with no help. The list is in [roadmap.md](roadmap.md), the numbers in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

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

- **Live window:** `menubar/build.sh`, then `ConveyerMonitor.app --open-live`. It follows the player and shows every machine as a dot. Ctrl+Option+P pins it above other windows, Ctrl+Option+H hides the progress panel.
- **Terminal:** `python3 scripts/tui.py`.
- **Do not join with a real Factorio client.** It crashes the server.

## How it works

<img src="architecture.svg" width="600">

`runner.py` stays alive and reads a skill from `runner_cmd.json`. `skills.py` turns it into code FLE runs against the server, and the result comes back as the next observation. A planner builds and feeds assembler tiles on its own. Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), lessons in [docs/LEARNINGS.md](docs/LEARNINGS.md), training a model of our own in [docs/TRAINING.md](docs/TRAINING.md).

## License

MIT 2026, Joshua Trommel. Factorio is property of Wube Software. This project is unaffiliated and does not distribute the game.
