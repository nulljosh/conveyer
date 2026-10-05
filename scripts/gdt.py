#!/usr/bin/env python3
"""gdt.py: talk to Game Dev Tycoon through the conveyer-bridge mod (files in ~/Library/Application Support/conveyer-gdt, no network).
The mod writes state.json there a few times a second: the visible text and every pressable thing with an index.
  gdt.py show                 print the visible text and the pressable things
  gdt.py click N              press item N from the last show
  gdt.py at X Y               click a point in the game window (for the office picture)
  gdt.py slider N VALUE       move slider N
  gdt.py text N VALUE         type into input N
  gdt.py key NAME             press a key, for example Escape
  gdt.py inspect PATH         read-only look at a game object, for example GameManager.company"""
import json, sys, time, uuid
from pathlib import Path

DIR = Path.home() / "Library" / "Application Support" / "conveyer-gdt"   # the mod cannot write under Documents without a macOS prompt
STATE, CMD = DIR / "state.json", DIR / "cmd.json"


def state():
    return json.loads(STATE.read_text())


def alive(s=None):
    s = s or state()
    return time.time() - s["t"] / 1000 < 5


def send(type_, wait=6.0, **kw):
    cid = uuid.uuid4().hex[:8]
    tmp = CMD.with_suffix(".tmp"); tmp.write_text(json.dumps({"id": cid, "type": type_, **kw})); tmp.replace(CMD)
    end = time.time() + wait
    while time.time() < end:
        try:
            last = state().get("last") or {}
            if last.get("id") == cid: return last
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    return {"ok": False, "error": "no answer from the game (is it running, or frozen in the background?)"}


def show(s=None):
    s = s or state()
    print(f"age {time.time() - s['t'] / 1000:.1f}s gen {s['gen']} window {s['w']}x{s['h']}")
    print(s["text"])
    for it in s["items"]:
        extra = f" ={it['value']}" if "value" in it else ""
        print(f"[{it['i']}] {it['kind']} ({it['x']},{it['y']}) {it['text'] or it['id'] or it['cls']}{extra}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "show": show()
    elif a[0] == "click": print(send("click", i=int(a[1]), gen=state()["gen"]))
    elif a[0] == "at": print(send("clickAt", x=int(a[1]), y=int(a[2])))
    elif a[0] == "slider": print(send("slider", i=int(a[1]), value=float(a[2]), gen=state()["gen"]))
    elif a[0] == "text": print(send("text", i=int(a[1]), value=" ".join(a[2:]), gen=state()["gen"]))
    elif a[0] == "key": print(send("key", key=a[1]))
    elif a[0] == "inspect": print(json.dumps(send("inspect", path=a[1], max=int(a[2]) if len(a) > 2 else 120), indent=1))
