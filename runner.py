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

WIDE_R = 60  # half-width of the screenshot in tiles; the view is 2*WIDE_R x 68 tiles

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
    parser.add_argument("--keep-world", action="store_true",
                        help="real save: skip FLE's reset (it clears entities, resets research, regenerates ore)")
    args = parser.parse_args()

    if args.keep_world:
        # Real save. FLE's init would wipe it: reset() clears entities, resets research and
        # regenerates ore; create_agent_characters destroys every character and spawns one at 0,0;
        # peaceful deletes every enemy. Tools are loaded by file path, so patch them where
        # setup_tools binds them onto the namespace, before initialise() runs.
        from fle.env.instance import FactorioInstance
        from fle.env.lua_manager import LuaScriptManager
        ADOPT = (
            "/sc local c = nil "
            "for _, p in pairs(game.players) do if p.character and p.character.valid then c = p.character break end end "
            "if not c then for _, e in pairs(game.surfaces[1].find_entities_filtered{type='character'}) do c = e break end end "
            "if not c then c = game.surfaces[1].create_entity{name='character', position=game.players[1].position, force=game.forces.player} end "
            "storage.agent_characters = {c} player = c "
            "rcon.print('adopted character at ' .. c.position.x .. ',' .. c.position.y)"
        )
        orig_setup = LuaScriptManager.setup_tools

        def setup_tools(self, instance):
            orig_setup(self, instance)
            def adopt(*a, **k):
                print(f"[runner] {self.rcon_client.send_command(ADOPT)}", flush=True)
                return True
            for ns in instance.namespaces:
                ns._reset = lambda *a, **k: 1
                ns._create_agent_characters = adopt
                # Every observation calls get_entities() unfiltered at radius 1000, which
                # serialises and belt-groups the whole base. That was the 18 GB balloon.
                # ponytail: 30 tiles around the player; widen if the agent needs base-wide sight.
                full = ns.get_entities
                ns.get_entities = lambda entities=set(), position=None, radius=1000, _f=full: (
                    _f(entities, position, 30 if position is None and radius == 1000 else radius))

        LuaScriptManager.setup_tools = setup_tools
        orig_init = FactorioInstance.__init__
        FactorioInstance.__init__ = lambda self, *a, **k: orig_init(self, *a, **{**k, "peaceful": False})

    import os

    # One runner per command file: a second one (menu bar watchdog racing a restart) double-fires every step.
    import fcntl
    lock = open("runner.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("[runner] another runner.py holds runner.lock, exiting")

    Path("runner.pid").write_text(str(os.getpid()))

    # A real save can blow FLE up to 18 GB and fill swap. Dump where, then die, at 3 GB.
    import faulthandler, resource, threading
    def memory_guard():
        while True:
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 3 * 1024**3:
                print("[runner] over 3 GB, dumping stacks and exiting", flush=True)
                faulthandler.dump_traceback(all_threads=True)
                Path("runner.pid").unlink(missing_ok=True)  # no pid = menu bar won't respawn into the same balloon
                os._exit(3)
            time.sleep(0.2)
    threading.Thread(target=memory_guard, daemon=True).start()

    env_id = args.env_id or pick_default_env()
    print(f"[runner] environment: {env_id}", flush=True)
    env = gym.make(env_id, run_idx=0)
    env.unwrapped.pause_after_action = False  # a paused game freezes research and smelting between steps
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
                # ponytail: the shot is for people, not the model: no debug grid, no alert triangles
                from fle.env.tools.admin.render.renderer import Renderer
                Renderer._draw_grid = lambda self, *a, **k: None
                Renderer._render_alert_overlays = lambda self, *a, **k: None

            inst = env.unwrapped.instance
            render_tool = Render(inst.lua_script_manager, inst.namespaces[0])
            # Render's own `layers` kwarg is dead code upstream (accepted, never
            # read) — strip resources ourselves after fetching instead. One icon
            # per ore/coal tile in a patch, via the icon-fallback, is a dense
            # repeated grid, not useful signal. Character/entities/trees/water
            # are untouched.
            t0 = time.time()
            # Wide view (touch .wide to enable): 120 x 68 tiles = 1920 x 1088 px, 1:1 on a 1080p screen. It draws the whole base
            # (about 2,700 entities) and took 27.8 s a frame, so it stays off until the renderer is incremental.
            wide = Path(__file__).with_name(".wide").exists()
            R = WIDE_R if wide else 32
            renderer = render_tool.get_renderer_from_map(
                include_status=False, radius=WIDE_R if wide else 18, compression_level="binary",
                max_render_radius=R, position=None,
            )
            entity_names = sorted({e.name for e in renderer.entities})
            renderer.resources = []
            if wide:
                renderer.get_size = lambda: {"minX": -R, "minY": -34, "maxX": R, "maxY": 34, "width": 2 * R, "height": 68}
                image = renderer.render(2 * R * 16, 68 * 16, render_tool.image_resolver)
            else:
                image = renderer.render(1024, 1024, render_tool.image_resolver)
            image.save("preview.png")
            import resource
            print(f"[runner] frame {image.size[0]}x{image.size[1]} {len(renderer.entities)} entities {time.time() - t0:.1f}s peak {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1048576} MB", flush=True)
            print(f"[runner] screenshot entities: {entity_names}", flush=True)
        except Exception as e:  # noqa: BLE001 - periodic capture, never fatal
            print(f"[runner] periodic screenshot failed: {e}", flush=True)

    def live_interval(default: float) -> float:
        """The menu bar writes the chosen refresh to .live; never faster than 2 s."""
        try: return max(2.0, float(Path(__file__).with_name(".live").read_text()))
        except Exception: return default

    last_screenshot = 0.0
    seen_mtime = None
    while True:
        # Periodic screenshot, throttled to ~8s and only when idle (no command
        # mid-flight) so it never competes with an actual skill step.
        if not CMD_PATH.exists() or CMD_PATH.stat().st_mtime == seen_mtime:
            if time.time() - last_screenshot > live_interval(8.0):
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
