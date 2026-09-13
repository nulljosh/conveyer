#!/usr/bin/env python3
"""
Persistent FLE runner, driven by Claude directly (no local-model HTTP loop).

Claude writes a skill call to cmd.json, this process renders it via skills.py,
steps the FLE gym env once, and writes the result to result.json. Keeping the
env alive across turns avoids re-registering ~30 Lua actions (the slow part)
on every single skill call.

Usage: python3 runner.py [--env-id ID]
"""

import argparse
import importlib
import json
import re
import sys
import time
from pathlib import Path

import gym

from fle.env.gym_env.action import Action
from fle.env.gym_env.registry import list_available_environments

import skills

CMD_PATH = Path("runner_cmd.json")
RESULT_PATH = Path("runner_result.json")
SEQ_PATH = Path("runner_seq.txt")  # bumped after every result write, so callers can
# block until *their* command's result lands instead of racing a fixed sleep.
STATUS_PATH = Path("status.json")  # polled by the menu-bar app, cheap to read

# FLE's raw_text observation comes back as a Python-repr'd tuple with a line-number
# prefix, e.g. "9: ('SKILL_OK mine: placed ... IronOre',)" — not fit for display.
_RAW_TEXT_PREFIX = re.compile(r"^\d+:\s*")


def clean_message(raw: str) -> str:
    match = _RAW_TEXT_PREFIX.match(raw)
    if not match:
        return raw.strip()
    try:
        import ast

        parsed = ast.literal_eval(raw[match.end() :])
        parts = parsed if isinstance(parsed, tuple) else (parsed,)
        return "\n".join(str(p) for p in parts).strip()
    except (ValueError, SyntaxError):
        return raw[match.end() :].strip()


def write_status(step: int, skill: str, ok: bool, message: str) -> None:
    STATUS_PATH.write_text(
        json.dumps(
            {
                "step": step,
                "skill": skill,
                "ok": ok,
                "message": clean_message(message)[:300],
                "updated_at": time.time(),
            }
        )
    )


def pick_default_env() -> str:
    env_ids = list_available_environments()
    for env_id in env_ids:
        if "iron" in env_id.lower():
            return env_id
    return env_ids[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-id")
    args = parser.parse_args()

    import os

    Path("runner.pid").write_text(str(os.getpid()))

    env_id = args.env_id or pick_default_env()
    print(f"[runner] environment: {env_id}", flush=True)
    env = gym.make(env_id, run_idx=0)
    obs, info = env.reset(options={"game_state": None})
    print("[runner] ready, waiting for commands", flush=True)
    seq = 0
    RESULT_PATH.write_text(json.dumps({"ready": True, "observation": obs.get("raw_text", "")}))
    SEQ_PATH.write_text(str(seq))

    def capture_screenshot() -> None:
        try:
            from fle.env.tools.admin.render.client import Render
            from fle.env.tools.admin.render.image_resolver import ImageResolver

            if not getattr(ImageResolver, "_icon_fallback_patched", False):
                _orig_call = ImageResolver.__call__

                def _patched_call(self, name, shadow=False):
                    img = _orig_call(self, name, shadow=shadow)
                    if img is None and not shadow and not name.startswith("icon_"):
                        img = _orig_call(self, f"icon_{name}", shadow=False)
                    return img

                ImageResolver.__call__ = _patched_call
                ImageResolver._icon_fallback_patched = True

            inst = env.unwrapped.instance
            render_tool = Render(inst.lua_script_manager, inst.namespaces[0])
            # Render's own `layers` kwarg is dead code upstream (accepted, never
            # read) — strip resources ourselves after fetching instead. One icon
            # per ore/coal tile in a patch, via the icon-fallback, is a dense
            # repeated grid, not useful signal. Character/entities/trees/water
            # are untouched.
            renderer = render_tool.get_renderer_from_map(
                include_status=False, radius=18, compression_level="binary",
                max_render_radius=32, position=None,
            )
            entity_names = sorted({e.name for e in renderer.entities})
            renderer.resources = []
            size = renderer.get_size()
            from fle.env.tools.admin.render.constants import DEFAULT_SCALING
            width = min(1024, int(size["width"] * DEFAULT_SCALING))
            height = min(1024, int(size["height"] * DEFAULT_SCALING))
            image = renderer.render(width, height, render_tool.image_resolver)
            image.save("preview.png")
            print(f"[runner] screenshot entities: {entity_names}", flush=True)
        except Exception as e:  # noqa: BLE001 - periodic capture, never fatal
            print(f"[runner] periodic screenshot failed: {e}", flush=True)

    last_screenshot = 0.0
    seen_mtime = None
    while True:
        # Periodic screenshot, throttled to ~8s and only when idle (no command
        # mid-flight) so it never competes with an actual skill step.
        if not CMD_PATH.exists() or CMD_PATH.stat().st_mtime == seen_mtime:
            if time.time() - last_screenshot > 8:
                capture_screenshot()
                last_screenshot = time.time()
        if CMD_PATH.exists():
            mtime = CMD_PATH.stat().st_mtime
            if mtime != seen_mtime:
                seen_mtime = mtime
                try:
                    cmd = json.loads(CMD_PATH.read_text())
                    if cmd.get("quit"):
                        print("[runner] quit requested", flush=True)
                        break
                    if cmd.get("screenshot"):
                        try:
                            from fle.env.tools.admin.render.client import Render
                            from fle.env.tools.admin.render.image_resolver import (
                                ImageResolver,
                            )

                            # The downloaded sprite package only has inventory-style
                            # icons (icon_<name>.png), not full world-render sprites —
                            # fall back to the icon so entities actually draw instead
                            # of silently rendering nothing.
                            if not getattr(ImageResolver, "_icon_fallback_patched", False):
                                _orig_call = ImageResolver.__call__

                                def _patched_call(self, name, shadow=False):
                                    img = _orig_call(self, name, shadow=shadow)
                                    if img is None and not shadow and not name.startswith("icon_"):
                                        img = _orig_call(self, f"icon_{name}", shadow=False)
                                    return img

                                ImageResolver.__call__ = _patched_call
                                ImageResolver._icon_fallback_patched = True

                            inst = env.unwrapped.instance
                            render_tool = Render(inst.lua_script_manager, inst.namespaces[0])
                            image, renderer = render_tool(
                                radius=int(cmd.get("radius", 40)), return_renderer=True
                            )
                            image.save("preview.png")
                            n_entities = len(getattr(renderer, "entities", []) or [])
                            result = {
                                "ok": True,
                                "observation": f"screenshot saved, {n_entities} entities in renderer",
                            }
                        except Exception as e:  # noqa: BLE001
                            result = {"ok": False, "error": str(e)}
                        RESULT_PATH.write_text(json.dumps(result))
                        seq += 1
                        SEQ_PATH.write_text(str(seq))
                        print(f"[runner] screenshot -> ok={result.get('ok')}", flush=True)
                        continue
                    if cmd.get("reload"):
                        importlib.reload(skills)
                        result = {"ok": True, "observation": "skills.py reloaded, world untouched"}
                        RESULT_PATH.write_text(json.dumps(result))
                        seq += 1
                        SEQ_PATH.write_text(str(seq))
                        print("[runner] skills.py reloaded", flush=True)
                        continue
                    code = skills.render(cmd["skill"], cmd.get("params", {}))
                    action = Action(agent_idx=0, game_state=None, code=code)
                    obs, reward, terminated, truncated, info = env.step(action)
                    result = {
                        "ok": True,
                        "observation": obs.get("raw_text", ""),
                        "reward": reward,
                        "terminated": terminated,
                        "truncated": truncated,
                    }
                except Exception as e:  # noqa: BLE001 - surface any failure to the caller
                    result = {"ok": False, "error": str(e)}
                RESULT_PATH.write_text(json.dumps(result))
                seq += 1
                SEQ_PATH.write_text(str(seq))
                skill_name = cmd.get("skill", "?")
                print(f"[runner] {skill_name} -> ok={result.get('ok')}", flush=True)
                write_status(
                    seq,
                    skill_name,
                    result.get("ok", False),
                    result.get("observation") or result.get("error", ""),
                )
        time.sleep(0.5)

    env.close()


if __name__ == "__main__":
    sys.exit(main())
