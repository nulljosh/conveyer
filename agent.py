#!/usr/bin/env python3
"""
Claude plays Factorio through FLE's gym environment.

Each turn: Claude gets the last action's stdout/stderr as an observation and
returns a Python snippet. That snippet is executed inside the FLE gym env
(which runs it against the Lua/RCON bridge in the Factorio server container),
and the result becomes the next observation. Repeats until the task
terminates, truncates, or --max-steps is hit.

Requires a running FLE cluster (`fle cluster start`) and Ollama running locally.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import gym
import httpx

from fle.env.gym_env.action import Action
from fle.env.gym_env.registry import list_available_environments, get_environment_info
from fle.commons.models.game_state import GameState

# FLE exposes a fixed Python API (place_entity, connect_entities, Prototype.*, ...), not the
# raw Lua `game.surfaces[...]` API — a model that hasn't seen it will hallucinate the wrong
# syntax. fle/env/tools/agent.md is FLE's own reference for that API; ship it as-is instead of
# re-describing it and drifting out of sync with whatever FLE version is installed.
_AGENT_MD = Path(__file__).resolve()
for _p in Path(__import__("fle").__file__).parent.rglob("agent.md"):
    if _p.parent.name == "tools":
        _AGENT_MD = _p
        break

SYSTEM_PROMPT = f"""You are an AI agent playing Factorio. You interact with the game through a \
Python REPL: your messages are Python programs, and what you receive back is the stdout/stderr \
from running them against the live game.

You have a fixed set of tool functions and types available in every snippet — do NOT use the \
raw Lua `game.surfaces[...]` / `game.players[...]` API, it does not exist here. Use functions \
like `place_entity`, `place_entity_next_to`, `connect_entities`, `get_entity`, `get_entities`, \
`nearest`, `nearest_buildable`, `move_to`, `craft_item`, `insert_item`, `extract_item`, \
`inspect_inventory`, `rotate_entity`, `harvest_resource`, `set_entity_recipe`, `sleep`, `print`, \
and the `Prototype`, `Direction`, `Position`, `BuildingBox`, `RecipeName` types. Reference and \
worked examples:

{_AGENT_MD.read_text() if _AGENT_MD.name == "agent.md" else "(agent.md not found — check the FLE install)"}

Rules:
- Reply with a short plan in plain text, then exactly one ```python code fence with the code to run.
- Write code as TOP-LEVEL statements that execute immediately, not function definitions you \
never call. If you do wrap something in a function for clarity, call it in the same snippet. \
A snippet that only defines things and prints nothing produces an empty, useless observation.
- Keep each snippet small and focused (roughly 30 lines or fewer) so failures are easy to localize.
- Never guess a raw (x, y) for `place_entity`. Find a real position first — `nearest(Resource.\
IronOre)` for ore patches, `nearest_buildable(Prototype.X, building_box, near_position)` for \
open, buildable ground — then place there. A guessed coordinate is very likely on unplaceable \
terrain or already occupied.
- `nearest(...)` returns a `Position` directly — it does NOT have a `.position` attribute. \
Use its return value as-is: `pos = nearest(Resource.IronOre)`, then `place_entity(..., \
position=pos)`, never `pos.position`. Only actual entities (what `place_entity`/`get_entity` \
return) have a `.position` attribute.
- `nearest_buildable(...)` returns a bounding-box-like object with a `.center` attribute — it \
is NOT itself a `Position`. You MUST use `.center`: `box = nearest_buildable(...)` then \
`place_entity(..., position=box.center)`, never `place_entity(..., position=box)` directly. \
If you see "position argument must be a Position object", this is almost always the bug. This \
also applies to the `near_position` argument of `nearest_buildable` itself — pass \
`furnace.position` (the placed entity's real position), never the `nearest_buildable` box you \
got it from.
- If your last snippet errored, do not resubmit the exact same code again. Change the specific \
line the traceback points to before rerunning.
- There is no `Prototype.Furnace` — use `Prototype.StoneFurnace` (or SteelFurnace/\
ElectricFurnace).
- `set_entity_recipe(entity, recipe)` takes a `RecipeName` enum member, NEVER a raw string. \
`set_entity_recipe(assembler, "iron-gear-wheel")` fails with "Invalid entity type" — use \
`set_entity_recipe(assembler, RecipeName.IronGearWheel)` instead.
- After an error, do NOT start over by re-finding a new ore patch and placing a second drill \
elsewhere — that wastes the base you already have. Look up what you already placed with \
`get_entity(Prototype.X, position=...)` at its known position (print positions so you have \
them to reuse), fix only the failing line, and keep building on it.
- A Python variable from an earlier step can be `None` if that line errored (a caught \
exception still leaves the assignment as `None`) or the step just isn't guaranteed to persist. \
NEVER assume a variable like `drill` is still a real entity — before using it, re-fetch it \
fresh with `get_entity(Prototype.X, position=Position(x=.., y=..))` using a coordinate you \
printed earlier, and check it isn't `None` before proceeding.
- Use print() and assert to inspect state and verify results — you cannot see the screen, only \
what your code prints or raises.
- Don't repeat the previous snippet after an error; read the traceback, fix the specific problem, \
and continue from the current game state.
- Prefer automated solutions (belts, inserters, assemblers) over one-off manual actions once a \
pattern repeats.
"""

CODE_FENCE = re.compile(r"```python\s*(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    match = CODE_FENCE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def pick_default_env() -> str:
    env_ids = list_available_environments()
    if not env_ids:
        raise SystemExit("No FLE environments registered — is FLE installed correctly?")
    for env_id in env_ids:
        if "iron" in env_id.lower():
            return env_id
    return env_ids[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-id", help="FLE gym environment id (default: an iron-themed task, or the first registered one)")
    parser.add_argument("--model", default="qwen2.5-coder:14b", help="Ollama model tag (ollama list to see available)")
    parser.add_argument("--ollama-host", default="http://localhost:11434/v1", help="Ollama's OpenAI-compatible endpoint")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--list-envs", action="store_true", help="List available environments and exit")
    parser.add_argument("--log-dir", default="runs", help="Where to write the per-run JSONL transcript")
    args = parser.parse_args()

    if args.list_envs:
        for env_id in list_available_environments():
            info = get_environment_info(env_id)
            print(f"{env_id}\n    {info['description']}")
        return

    env_id = args.env_id or pick_default_env()
    print(f"[conveyer] environment: {env_id}")
    print(f"[conveyer] model: {args.model}")

    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{int(time.time())}-{env_id}.jsonl"
    log_file = log_path.open("w")

    ollama_url = args.ollama_host.replace("/v1", "") + "/api/chat"
    env = gym.make(env_id, run_idx=0)

    try:
        obs, info = env.reset(options={"game_state": None})
        goal = (obs.get("task_info") or {}).get("goal_description", "")
        observation_text = obs.get("raw_text", "")
        messages = [
            {
                "role": "user",
                "content": f"Goal: {goal}\n\nInitial state:\n{observation_text}",
            }
        ]

        for step in range(1, args.max_steps + 1):
            response = httpx.post(
                ollama_url,
                json={
                    "model": args.model,
                    "think": False,  # qwen3 etc. burn the whole token budget on hidden
                    # reasoning otherwise, leaving nothing in the response
                    "stream": False,
                    "options": {"num_predict": args.max_tokens},
                    "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
                },
                timeout=180,
            ).json()
            reply_text = response["message"]["content"]
            code = extract_code(reply_text)
            messages.append({"role": "assistant", "content": reply_text})

            print(f"\n--- step {step} ---\n{code}\n")

            game_state = GameState.from_instance(env.instance)
            action = Action(agent_idx=0, game_state=game_state, code=code)
            obs, reward, terminated, truncated, info = env.step(action)
            observation_text = obs.get("raw_text", "")

            print(f"[reward={reward} terminated={terminated} truncated={truncated}]")
            print(observation_text[-2000:])

            log_file.write(
                json.dumps(
                    {
                        "step": step,
                        "code": code,
                        "observation": observation_text,
                        "reward": reward,
                        "terminated": terminated,
                        "truncated": truncated,
                    }
                )
                + "\n"
            )
            log_file.flush()

            messages.append(
                {
                    "role": "user",
                    "content": f"Reward: {reward}\n\n{observation_text}",
                }
            )

            if terminated or truncated:
                print(f"[conveyer] episode ended at step {step}")
                break
    except KeyboardInterrupt:
        print("\n[conveyer] interrupted")
    finally:
        log_file.close()
        env.close()
        print(f"[conveyer] transcript: {log_path}")


if __name__ == "__main__":
    sys.exit(main())
