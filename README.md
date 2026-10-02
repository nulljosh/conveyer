<img src="icon.svg" width="80" style="border-radius:18px">

# Conveyer

![version](https://img.shields.io/badge/version-v0.1.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) [![GitHub](https://img.shields.io/badge/GitHub-nulljosh%2Fconveyer-black?logo=github)](https://github.com/nulljosh/conveyer)

An LLM plays Factorio. On a real save.

It reads the game as data, not pixels. Each turn it picks one move from a short list. The move checks its own result, and the game answers. [Live](https://conveyer.heyitsmejosh.com).

Built on [FLE](https://github.com/JackHopkins/factorio-learning-environment), the Factorio Learning Environment.

## Where it is

<!-- progress:start -->
**Road to the rocket: 84%** `################----` 37 of 44 techs the silo needs. Rockets launched: 0.
<!-- progress:end -->

Plays on a copy of a real 2,300 entity base. Research is at chemical science. The refinery runs and makes plastic. Next: sulfur, advanced circuits, then the rocket. [Roadmap](roadmap.md).

<img src="progress.svg" width="480" alt="Entities placed per run">

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

## Your own save

`scripts/world.sh` boots the server on a copy of your save. The original is never touched. `scripts/world.sh back` returns to the test map. Then run `python3 runner.py --env-id open_play --keep-world`.

## Watch it

- **Menu bar:** `menubar/build.sh`. Shows the live map, research, and the next milestones.
- **Terminal:** `python3 scripts/tui.py`.
- **Screenshots and benchmark:** `scripts/snap.py` saves a frame and a row to `shots/` every 5 minutes.
- **Your own Factorio client:** connect to the server address. The version must match exactly. Under colima, start it with `--network-address` so UDP works.

## How it works

<img src="architecture.svg" width="600">

`runner.py` stays alive and reads a skill from `runner_cmd.json`. `skills.py` turns it into code FLE runs against the server. The result comes back as the next observation. Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Lessons so far in [docs/LEARNINGS.md](docs/LEARNINGS.md).

## License

MIT 2026, Joshua Trommel. Factorio is property of Wube Software. This project is unaffiliated and does not distribute the game.
