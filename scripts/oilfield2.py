#!/usr/bin/env python3
"""oilfield2.py: the north-west oil field, nine wells at about (-213,-410) with 1,440 percent yield together (the east field has 663 percent).
Pumpjacks on every well, outputs joined by a routed trunk, one barrel filler on the trunk (steel chests, 480 barrels each), and a pole chain from the
grid at (-17.5,-397.5), about 200 tiles east. Crude leaves the field in barrels like the east field: .world/fillers.json lists every filler and
scripts/barrels.py move shuttles them. Site freezes in .world/oilfield2.json; idempotent replay. Uses blocks.py. ponytail: one filler (about 180
crude a second); add a second filler on the trunk if pumpjacks back up."""
import json
from pathlib import Path
from blocks import Site

ROOT = Path(__file__).resolve().parent.parent
SITE, FIL = ROOT / ".world" / "oilfield2.json", ROOT / ".world" / "fillers.json"
s = Site(timeout=180)
# power first: chain poles west from the grid, 50 tiles per call
for x in (-70, -120, -170, -205):
    print("power", x, s.run("local p=power(%d,-400) rcon.print(p and ('pole '..p.position.x..','..p.position.y..' net '..tostring(p.electric_network_id)) or 'no pole')" % x))
wells = s.run("""local o={} for _,r in pairs(s.find_entities_filtered{name='crude-oil'}) do if r.position.x<-150 and r.position.y<-300 then o[#o+1]=r.position.x..','..r.position.y end end rcon.print(table.concat(o,';'))""")
W = [tuple(float(v) for v in w.split(",")) for w in wells.split(";") if w]
first = None
for (wx, wy) in W:
    r = s.run("""local e=s.find_entities_filtered{name='pumpjack',position={%g,%g},radius=1}[1]
if not e and s.can_place_entity{name='pumpjack',position={%g,%g},direction=d.north,force=F} then e=s.create_entity{name='pumpjack',position={%g,%g},direction=d.north,force=F} end
if not e then rcon.print('FAILED') return end local c=e.fluidbox.get_pipe_connections(1)[1] rcon.print(c.target_position.x..','..c.target_position.y)""" % ((wx, wy) * 3))
    if r == "FAILED": print("pumpjack failed at", wx, wy); continue
    ox, oy = [float(v) for v in r.split(",")]
    s.run("local p=power(%g,%g) rcon.print(p and p.electric_network_id or 'none')" % (wx, wy))  # a pole beside every pumpjack: the chain only reached the first three
    s.run("local x,y=%g,%g if not s.find_entities_filtered{name='pipe',position={x,y},radius=0.3}[1] and s.can_place_entity{name='pipe',position={x,y},force=F} then s.create_entity{name='pipe',position={x,y},force=F} end rcon.print('ok')" % (ox, oy))
    if first is None: first = (ox, oy)
    else: print("trunk", (wx, wy), s.pipe((ox, oy), first, box=40))
site = json.loads(SITE.read_text()) if SITE.exists() else None
if not site:
    cx = sum(w[0] for w in W) / len(W); cy = sum(w[1] for w in W) / len(W)
    r = s.free_spot(8, 6, (cx, cy + 10), maxr=40, step=2)
    X, Y = [float(v) for v in r.split(",")]
    site = {"fx": X + 4.5, "fy": Y + 3.5}
    SITE.write_text(json.dumps(site))
fx, fy = site["fx"], site["fy"]
out = s.run("""local fx,fy=%g,%g
put('assembling-machine-2',fx,fy,d.north,'crude-oil-barrel')
put('fast-inserter',fx-2,fy+1,d.west) put('steel-chest',fx-3,fy+1)
put('fast-inserter',fx+2,fy,d.west) put('steel-chest',fx+3,fy)
power(fx,fy+2)
rcon.print(table.concat(out,' | '))""" % (fx, fy))
print("filler:", out or "ok", "| input route:", s.pipe((fx, fy - 2), first, box=40))
fl = json.loads(FIL.read_text()) if FIL.exists() else [[264.5, 82.5]]
if [fx, fy] not in fl: fl.append([fx, fy]); FIL.write_text(json.dumps(fl))
print(s.run("""local fx,fy=%g,%g local fa=s.find_entities_filtered{name='assembling-machine-2',position={fx,fy},radius=0.5}[1] local c={} for _,e in pairs(s.find_entities_filtered{name='pumpjack',area={{-235,-430},{-195,-390}}}) do local k=st(e) c[k]=(c[k] or 0)+1 end local t={} for k,v in pairs(c) do t[#t+1]=k..'='..v end
local i1=s.find_entities_filtered{name='inserter',position={fx-2,fy+1},radius=0.3}[1] local i2=s.find_entities_filtered{name='inserter',position={fx+2,fy},radius=0.3}[1]
rcon.print('filler '..st(fa)..' crude '..(fa.fluidbox[1] and math.floor(fa.fluidbox[1].amount) or 0)..' inserters '..st(i1)..'/'..st(i2)..' | pumpjacks '..table.concat(t,','))""" % (fx, fy)))
