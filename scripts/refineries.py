#!/usr/bin/env python3
"""refineries.py [N=2]: N more basic-oil refineries, each fed crude by its own barrel emptier directly under its crude port, and each gas output
routed into the existing petroleum gas network. One refinery makes 9 gas a second; plastic alone can use 20, so gas was the next wall after the
crude fix. Uses scripts/blocks.py (free-spot search, power chain, pipe router). Sites freeze in .world/refineries.json, idempotent replay.
Crude arrives by barrel: new emptiers are appended to .world/emptiers.json, which scripts/barrels.py reads."""
import json, sys
from pathlib import Path
from blocks import Site

ROOT = Path(__file__).resolve().parent.parent
SITES, EMPT = ROOT / ".world" / "refineries.json", ROOT / ".world" / "emptiers.json"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
s = Site()
sites = json.loads(SITES.read_text()) if SITES.exists() else []
while len(sites) < n:
    ref = s.free_spot(12, 16, (-45, 14))
    if ref == "none": print("no free spot"); break
    X, Y = [float(v) for v in ref.split(",")]
    # reserve the spot by placing right away so the next search sees it
    sites.append({"rx": X + 3.5, "ry": Y + 4.5})
    out = s.run("""local rx,ry=%g,%g
put('oil-refinery',rx,ry,d.north,'basic-oil-processing') put('pipe',rx+1,ry+3)
local ex,ey=rx+1,ry+5
put('assembling-machine-2',ex,ey,d.south,'empty-crude-oil-barrel')
put('inserter',ex-1,ey+2,d.south) put('wooden-chest',ex-1,ey+3) put('inserter',ex+1,ey+2,d.north) put('wooden-chest',ex+1,ey+3)
power(ex+2,ey+3) power(rx-3,ry) power(rx+3,ry-3)
rcon.print(table.concat(out,' | '))""" % (X + 3.5, Y + 4.5))
    print("placed", sites[-1], out)
    SITES.write_text(json.dumps(sites))
    emp = json.loads(EMPT.read_text()) if EMPT.exists() else [[-37.5, 3.5], [-33.5, 3.5]]
    e = [sites[-1]["rx"] + 1, sites[-1]["ry"] + 5]
    if e not in emp: emp.append(e); EMPT.write_text(json.dumps(emp))
for st in sites:
    print("gas", s.pipe((st["rx"] + 2, st["ry"] - 3), (-36.5, -6.5)))
    print(s.run("""local rx,ry=%g,%g local r=s.find_entities_filtered{name='oil-refinery',position={rx,ry},radius=0.5}[1] local e=s.find_entities_filtered{name='assembling-machine-2',position={rx+1,ry+5},radius=0.5}[1]
local i1=s.find_entities_filtered{name='inserter',position={rx,ry+7},radius=0.3}[1] local i2=s.find_entities_filtered{name='inserter',position={rx+2,ry+7},radius=0.3}[1]
rcon.print('refinery '..st(r)..' emptier '..st(e)..' in-inserter '..st(i1)..' out-inserter '..st(i2))""" % (st["rx"], st["ry"])))
