#!/usr/bin/env python3
"""fuelgas.py [N=3]: N chemical plants making solid fuel from the petroleum gas surplus. Three refineries make 27 gas a second and plastic, sulfur
and acid use under 10, so the rest backed the refineries up. Solid fuel (12 MJ) is both a gas sink and the main input of rocket fuel (10 solid fuel
plus 10 light oil each, 1,050 needed). Each plant takes gas through a routed pipe and drops solid fuel into a chest by an inserter.
Sites freeze in .world/fuelgas.json; idempotent replay. Uses blocks.py (read ports from the game, check every inserter status)."""
import json, sys
from pathlib import Path
from blocks import Site

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / ".world" / "fuelgas.json"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
s = Site()
sites = json.loads(SITE.read_text()) if SITE.exists() else []
if len(sites) < n:
    r = s.free_spot(4 * n + 2, 8, (-30, 6))
    if r == "none": print("no free spot"); raise SystemExit
    X, Y = [float(v) for v in r.split(",")]
    sites = [{"px": X + 2.5 + 4 * i, "py": Y + 3.5} for i in range(n)]
    SITE.write_text(json.dumps(sites))
for st in sites:
    px, py = st["px"], st["py"]
    out = s.run("""local px,py=%g,%g
put('chemical-plant',px,py,d.north,'solid-fuel-from-petroleum-gas')
put('inserter',px,py+2,d.north) put('wooden-chest',px,py+3)
power(px+2,py+2)
rcon.print(table.concat(out,' | '))""" % (px, py))
    print("plant", px, py, out, "| gas", s.pipe((px - 1, py - 2), (-36.5, -6.5)))
    print(s.run("""local px,py=%g,%g local e=s.find_entities_filtered{name='chemical-plant',position={px,py},radius=0.5}[1] local i=s.find_entities_filtered{name='inserter',position={px,py+2},radius=0.3}[1]
local fl='-' if e.fluidbox[1] then fl=e.fluidbox[1].name..math.floor(e.fluidbox[1].amount) end rcon.print('solid fuel plant '..st(e)..' gas '..fl..' inserter '..st(i))""" % (px, py)))
