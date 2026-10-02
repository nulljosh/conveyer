#!/usr/bin/env python3
"""speed.py: game speed follows CPU load. The Factorio server in the VM is the biggest cost (about 64% of a core at 10x),
so when the Mac is busy the game slows down and research just takes longer. One load-average read and at most one RCON call.
Targets: load per core under 0.6 -> 10x, under 0.8 -> 6x, under 1.0 -> 3x, above -> 2x. Moves one step per call (hysteresis).
Under 40% free RAM it drops straight to 2x: the Mac froze twice with other sessions stacked beside the game."""
import os, re, subprocess
import factorio_rcon as f

STEPS = [2, 3, 6, 10]
load = os.getloadavg()[0] / (os.cpu_count() or 1)
want = 10 if load < 0.6 else 6 if load < 0.8 else 3 if load < 1.0 else 2
free = int(re.search(r"(\d+)%", subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout.splitlines()[-1]).group(1))
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=10)
now = float(c.send_command("/silent-command rcon.print(game.speed)"))
cur = min(STEPS, key=lambda s: abs(s - now))
nxt = STEPS[max(0, min(len(STEPS) - 1, STEPS.index(cur) + (1 if want > cur else -1 if want < cur else 0)))]
if free < 40:
    nxt = 2  # ponytail: skip the hysteresis, RAM pressure is the crash path
if nxt != now:
    c.send_command(f"/silent-command game.speed={nxt}")
print(f"load/core {load:.2f}, ram free {free}%: speed {now:g} -> {nxt}")
