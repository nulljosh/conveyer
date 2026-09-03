#!/usr/bin/env python3
"""
Claude plays Factorio through FLE's gym environment.

Each turn: Claude gets the last action's stdout/stderr as an observation and
returns a Python snippet. That snippet is executed inside the FLE gym env
(which runs it against the Lua/RCON bridge in the Factorio server container),
and the result becomes the next observation. Repeats until the task
terminates, truncates, or --max-steps is hit.

Requires a running FLE cluster (`fle cluster start`) and ANTHROPIC_API_KEY set.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import gym
from anthropic import Anthropic

from fle.env.gym_env.action import Action
from fle.env.gym_env.registry import list_available_environments, get_environment_info
from fle.commons.models.game_state import GameState

SYSTEM_PROMPT = """You are an AI agent playing Factorio. You interact with the game through a \
Python REPL: your messages are Python programs, and what you receive back is the stdout/stderr \
from running them against the live game.

Rules:
- Reply with a short plan in plain text, then exactly one ```python code fence with the code to run.
- Keep each snippet small and focused (roughly 30 lines or fewer) so failures are easy to localize.
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
    parser.add_argument("--model", default="claude-sonnet-5", help="Anthropic model id")
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
    print(f"[conveyor] environment: {env_id}")
    print(f"[conveyor] model: {args.model}")

    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{int(time.time())}-{env_id}.jsonl"
    log_file = log_path.open("w")

    client = Anthropic()
    env = gym.make(env_id)

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
            response = client.messages.create(
                model=args.model,
                max_tokens=args.max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            reply_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
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
                print(f"[conveyor] episode ended at step {step}")
                break
    except KeyboardInterrupt:
        print("\n[conveyor] interrupted")
    finally:
        log_file.close()
        env.close()
        print(f"[conveyor] transcript: {log_path}")


if __name__ == "__main__":
    sys.exit(main())
