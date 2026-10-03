#!/usr/bin/env python3
"""sweep.py: ASSISTED clearing of every enemy nest, worm and biter, nearest first from the oil field. These are console kills (entity.die),
not combat and not a tech win: real nest clearing needs military science, tanks and flamethrowers (see roadmap). Labelled assisted everywhere.
The engineer jumps to 12 tiles from each nest (he is invulnerable on patrol), units and worms die first, then the nest, with a short pause
for the nearest ones so the live window shows it; the rest go fast and the minimap shows the red dots vanishing. livemap.py stands still
while .sweep exists. Progress in sweep.json; events.py turns nest counts into feed lines. `sweep.py` runs it, `sweep.py near` stops after the
nests within 150 tiles of the oil field.
ponytail: console kills in a nearest-neighbour tour; swap for real turret creep once the military techs are researched."""
import json, math, sys, time
from pathlib import Path
import factorio_rcon as f

ROOT = Path(__file__).resolve().parent.parent
FX, FY = -213.0, -408.0   # the oil field, where the engineer already stands
NEAR_R, DWELL = 150, 1.5   # nests this close to the field are shown slowly
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=60)
run = lambda l: c.send_command(" ".join(l.split("\n")))
STAND = "/silent-command local c=game.surfaces[1].find_entities_filtered{type='character'}[1] if c then c.teleport({%g,%g}) end rcon.print('ok')"
KILL = ("/silent-command local s=game.surfaces[1] local F=game.forces.player local n=0 "
        "for _,e in pairs(s.find_entities_filtered{position={%g,%g},radius=36,force='enemy',type=%s}) do if e.valid then e.die(F) n=n+1 end end rcon.print(n)")


def left():
    return int(run("/silent-command rcon.print(game.surfaces[1].count_entities_filtered{type='unit-spawner',force='enemy'})"))


raw = run("/silent-command local o={} for _,e in pairs(game.surfaces[1].find_entities_filtered{type='unit-spawner',force='enemy'}) do "
          "o[#o+1]=string.format('%.0f,%.0f',e.position.x,e.position.y) end rcon.print(table.concat(o,';'))")
nests = [tuple(float(v) for v in p.split(",")) for p in raw.split(";") if p]
total = len(nests)
order, cur = [], (FX, FY)
while nests:   # nearest neighbour from the oil field outward
    nxt = min(nests, key=lambda q: (q[0] - cur[0]) ** 2 + (q[1] - cur[1]) ** 2); nests.remove(nxt); order.append(nxt); cur = nxt
near_only = len(sys.argv) > 1 and sys.argv[1] == "near"
(ROOT / ".sweep").write_text("1")
try:
    prev, done = (FX, FY), 0
    for (x, y) in order:
        slow = math.hypot(x - FX, y - FY) <= NEAR_R
        if near_only and not slow: break
        dx, dy = prev[0] - x, prev[1] - y; d = math.hypot(dx, dy) or 1
        run(STAND % (x + dx / d * 12, y + dy / d * 12))   # stand 12 tiles out on the side he came from
        run(KILL % (x, y, "{'unit','turret'}"))
        if slow: time.sleep(DWELL)
        run(KILL % (x, y, "{'unit-spawner'}"))
        if slow: time.sleep(DWELL)
        prev, done = (x, y), done + 1
        if done % 5 == 0 or slow:
            (ROOT / "sweep.json").write_text(json.dumps({"assisted": True, "cleared": done, "total": total, "t": time.time()}))
    stray = run("/silent-command local n=0 for _,e in pairs(game.surfaces[1].find_entities_filtered{force='enemy',type={'unit','turret','unit-spawner'}}) do if e.valid then e.die(game.forces.player) n=n+1 end end rcon.print(n)") if not near_only else "skipped"
    run(STAND % (FX, FY))
    print("assisted sweep done: cleared", done, "of", total, "nests; stray enemies killed:", stray, "; nests left:", left())
finally:
    (ROOT / ".sweep").unlink(missing_ok=True)
