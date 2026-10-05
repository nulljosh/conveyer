#!/usr/bin/env python3
"""gdt_play.py: a deterministic driver for Game Dev Tycoon over the conveyer-bridge mod (see games/gdt/README.md).
It reads the visible screen text from state.json, presses the routine buttons, starts the next game when the studio is idle, and
logs every decision to runs/gdt/<start>.jsonl. Screens it does not know are logged and left alone (the loop stops after a few in a row).
Assisted label: the policy reads only what the player sees on screen. It never edits cash, dates or saves.
  gdt_play.py [--minutes 30]"""
import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gdt

ROOT = Path(__file__).resolve().parent.parent
ROUTINE = ("ok", "continue", "next", "close", "done", "got it", "release", "yes", "no, thanks", "start development", "finish")


def press_routine(s):
    """The first routine button on screen, preferring a dialog button over the top bar."""
    for it in s["items"]:
        t = it["text"].strip().lower()
        if it["i"] > 2 and (t in ROUTINE or t.startswith("agree")): return it   # "Agree (receive 85K)" is the bank's bailout; "No (go bankrupt)" is never pressed
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--minutes", type=float, default=30); a = ap.parse_args()
    out = ROOT / "runs" / "gdt"; out.mkdir(parents=True, exist_ok=True)
    log = open(out / f"{int(time.time())}.jsonl", "a")
    end, unknown, last_sig = time.time() + a.minutes * 60, 0, None
    while time.time() < end:
        try: s = gdt.state()
        except (OSError, ValueError): time.sleep(1); continue
        if not gdt.alive(s): print("game not answering"); break
        sig = (s["gen"], s["text"][:200])
        if sig == last_sig: time.sleep(1.0); continue
        last_sig = sig
        it = press_routine(s)
        rec = {"t": round(time.time()), "screen": s["text"][:300].replace("\n", " | ")}
        if it:
            r = gdt.send("click", i=it["i"], gen=s["gen"]); rec.update(action="click " + it["text"], ok=r.get("ok")); unknown = 0
        elif len([l for l in s["text"].splitlines() if l.strip()]) <= 3 or "monthly costs" in s["text"]:
            rec.update(action="running"); unknown = 0   # only the top bar: the game is just running
        else:
            unknown += 1; rec.update(action="unknown", items=[(i["i"], i["text"][:30]) for i in s["items"] if i["i"] > 2][:12])
            if unknown >= 6: print("stuck on an unknown screen:", rec["screen"]); log.write(json.dumps(rec) + "\n"); break
        log.write(json.dumps(rec) + "\n"); log.flush()
        time.sleep(1.2)


if __name__ == "__main__":
    main()
