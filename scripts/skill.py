#!/usr/bin/env python3
"""skill.py: run one skill through a live runner.py and print what came back.
  skill.py find '{"resource": "IronOre"}'
Needs runner.py running (see docs/LOOP-HANDOFF.md). Writes runner_cmd.json, waits for runner_seq.txt to move, prints runner_result.json."""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CMD, RES, SEQ = ROOT / "runner_cmd.json", ROOT / "runner_result.json", ROOT / "runner_seq.txt"


def seq():
    try: return int(SEQ.read_text())
    except (OSError, ValueError): return -1


def run(skill, params, wait=240):
    before = seq()
    CMD.write_text(json.dumps({"skill": skill, "params": params}))
    end = time.time() + wait
    while time.time() < end:
        if seq() > before: return json.loads(RES.read_text())
        time.sleep(0.3)
    return {"ok": False, "error": f"no result after {wait}s"}


if __name__ == "__main__":
    r = run(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {})
    print(json.dumps(r, indent=1)[:3000])
