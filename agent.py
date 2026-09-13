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

import skills

SYSTEM_PROMPT = f"""You are an AI agent playing Factorio. You do NOT write Python. Each turn, \
pick exactly one skill from the list below and reply with a short plan in plain text, then \
exactly one ```json fence containing {{"skill": "<name>", "params": {{...}}}}.

Available skills:
{skills.catalog_text()}

Notes on params:
- Positions are strings like "x=1.0,y=2.0" (no `Position(...)` wrapper, no parens).
- Prototype/Resource/Direction names are bare strings matching FLE's enums, e.g. "IronOre", \
"BurnerMiningDrill", "StoneFurnace", "IronGearWheel", "UP".
- Every skill re-fetches entities by the position you give it — it does not remember entities \
from earlier turns. Reuse the positions printed in past observations (a `SKILL_OK` line \
always prints the real position of what it placed).
- If a skill fails, its observation says why (assert message or traceback). Fix the param that \
caused it and retry the same skill — don't switch to a different skill to work around a bug.
- Use "inspect" whenever you're unsure what you already have.
"""

JSON_FENCE = re.compile(r"```json\s*(.*?)```", re.DOTALL)


def extract_skill_call(text: str) -> dict:
    match = JSON_FENCE.search(text)
    raw = match.group(1).strip() if match else text.strip()
    return json.loads(raw)


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
    parser.add_argument("--model", default="qwen3:8b", help="Ollama model tag (ollama list to see available)")
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

        last_code = None
        repeat_count = 0
        for step in range(1, args.max_steps + 1):
            try:
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
                    timeout=300,
                ).json()
            except httpx.ConnectError:
                raise SystemExit(
                    f"Could not reach Ollama at {ollama_url} — is `ollama serve` running?"
                )
            except httpx.TimeoutException:
                # ponytail: a huge/growing context can make CPU prefill take arbitrarily
                # long; trimming history is cheaper than a bigger timeout. Drop the oldest
                # turn (keep the first, which carries the goal) and retry once.
                print("[conveyer] Ollama timed out, trimming history and retrying")
                if len(messages) > 3:
                    messages = [messages[0]] + messages[3:]
                continue
            if "message" not in response:
                raise SystemExit(f"Ollama error: {response.get('error', response)}")
            reply_text = response["message"]["content"]
            messages.append({"role": "assistant", "content": reply_text})

            try:
                call = extract_skill_call(reply_text)
                code = skills.render(call["skill"], call.get("params", {}))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"[conveyer] bad skill call, feeding error back: {e}")
                messages.append({"role": "user", "content": f"SKILL_FAIL: {e}"})
                continue

            # ponytail: local models sometimes ignore the "don't repeat" prompt rule and
            # resubmit the exact same skill call after a failure, forever. Enforce it in
            # code instead of hoping the model follows the instruction.
            if call == last_code:
                repeat_count += 1
            else:
                repeat_count = 0
            last_code = call
            if repeat_count >= 2:
                print(f"[conveyer] same skill call repeated {repeat_count + 1}x, stopping episode")
                break

            print(f"\n--- step {step}: {call['skill']}({call.get('params', {})}) ---")

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
                        "skill": call["skill"],
                        "params": call.get("params", {}),
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
