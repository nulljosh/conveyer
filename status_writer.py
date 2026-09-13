#!/usr/bin/env python3
"""
Sidecar that watches runner_seq.txt and writes a clean status.json for the
menu-bar app, decoupled from runner.py so it can be restarted/fixed without
resetting the live game (which restarting runner.py itself would do).
"""

import ast
import json
import re
import subprocess
import time
from pathlib import Path

CMD_PATH = Path("runner_cmd.json")
RESULT_PATH = Path("runner_result.json")
SEQ_PATH = Path("runner_seq.txt")
STATUS_PATH = Path("status.json")
LOG_PATH = Path("status_log.json")  # rolling window of recent steps, newest first
LOG_MAX = 100
MAP_PATH = Path("map.json")  # entity positions, parsed out of skill messages —
# no extra game calls, just regex over text we already have.
MAP_MAX = 60

_POSITION = re.compile(r"placed (\w+) at x=(-?[\d.]+) y=(-?[\d.]+)")

# Real base-building milestones — not harvest/inspect/peek/feed noise. Different
# sound for a bigger step (auto_feed/belt = the automated-chain milestone).
_MILESTONE_SOUND = {
    "mine": "Tink.aiff",
    "smelt": "Tink.aiff",
    "craft": "Pop.aiff",
    "place_at": "Tink.aiff",
    "auto_feed": "Glass.aiff",
    "belt": "Glass.aiff",
    "research": "Hero.aiff",
}


def play_milestone_sound(skill: str, ok: bool) -> None:
    if not ok:
        return
    sound = _MILESTONE_SOUND.get(skill)
    if not sound:
        return
    try:
        subprocess.Popen(
            ["afplay", f"/System/Library/Sounds/{sound}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass

_RAW_TEXT_PREFIX = re.compile(r"^\d+:\s*")
# The skill label is already shown separately in the UI, so drop the
# "SKILL_OK <skill>: " / "SKILL_FAIL <skill>: " prefix from the message body.
_SKILL_TAG_PREFIX = re.compile(r"^SKILL_(?:OK|FAIL) \S+:\s*")


def clean_message(raw: str) -> str:
    match = _RAW_TEXT_PREFIX.match(raw)
    body = raw
    if match:
        try:
            parsed = ast.literal_eval(raw[match.end() :])
            parts = parsed if isinstance(parsed, tuple) else (parsed,)
            body = "\n".join(str(p) for p in parts).strip()
        except (ValueError, SyntaxError):
            body = raw[match.end() :].strip()
    else:
        body = raw.strip()
    return _SKILL_TAG_PREFIX.sub("", body)


def load_log() -> list:
    try:
        return json.loads(LOG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def load_map() -> list:
    try:
        return json.loads(MAP_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def main() -> None:
    seen = None
    step = 0
    log = load_log()
    entity_map = load_map()
    if log:
        step = log[0].get("step", 0)
    while True:
        if SEQ_PATH.exists():
            seq = SEQ_PATH.read_text().strip()
            if seq != seen:
                seen = seq
                step += 1
                try:
                    result = json.loads(RESULT_PATH.read_text())
                    cmd = json.loads(CMD_PATH.read_text()) if CMD_PATH.exists() else {}
                    skill = cmd.get("skill") or ("reload" if cmd.get("reload") else "?")
                except (json.JSONDecodeError, OSError):
                    time.sleep(0.5)
                    continue
                message = result.get("observation") or result.get("error", "")
                entry = {
                    "step": step,
                    "skill": skill,
                    "ok": result.get("ok", False),
                    "message": clean_message(message)[:300],
                    "updated_at": time.time(),
                }
                STATUS_PATH.write_text(json.dumps(entry))
                play_milestone_sound(skill, entry["ok"])
                # peek/reload are debug/introspection calls, not real progress —
                # keep them out of the history feed so it reads as a milestone log.
                if skill not in ("peek", "reload"):
                    log.insert(0, entry)
                    del log[LOG_MAX:]
                    LOG_PATH.write_text(json.dumps(log))

                for kind, x, y in _POSITION.findall(entry["message"]):
                    entity_map.append({"kind": kind, "x": float(x), "y": float(y), "step": step})
                if entity_map:
                    del entity_map[:-MAP_MAX]
                    MAP_PATH.write_text(json.dumps(entity_map))
        time.sleep(1)


if __name__ == "__main__":
    main()
