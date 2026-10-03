#!/usr/bin/env python3
"""concrete.py: one assembler making concrete (1 iron ore, 5 stone brick, 100 water into 10 concrete, 1,000 needed for the silo). It sits at the
end of the water network at (55.5,-5.5), a single short routed pipe, with an input chest on its west side and an output chest on its east side.
fuelsupply.py-style moves fill the input chest from stores. Site freezes in .world/concrete.json; idempotent replay. Uses blocks.py."""
import json
from pathlib import Path
from blocks import Site

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / ".world" / "concrete.json"
s = Site()
site = json.loads(SITE.read_text()) if SITE.exists() else None
if not site:
    r = s.free_spot(9, 8, (52, -14), maxr=40, step=2)
    if r == "none": print("no free spot"); raise SystemExit
    X, Y = [float(v) for v in r.split(",")]
    site = {"cx": X + 4, "cy": Y + 4}   # machine centers sit on .5 tiles; free_spot corners do too
    SITE.write_text(json.dumps(site))
cx, cy = site["cx"], site["cy"]
out = s.run("""local cx,cy=%g,%g
put('assembling-machine-2',cx,cy,d.north,'concrete')
put('inserter',cx-2,cy,d.west) put('wooden-chest',cx-3,cy)
put('inserter',cx+2,cy,d.west) put('wooden-chest',cx+3,cy)
power(cx,cy+2)
rcon.print(table.concat(out,' | '))""" % (cx, cy))
import json as _j
_adv = _j.loads((ROOT / ".world" / "advoil.json").read_text())
NEAR = """local best,bd for _,e in pairs(s.find_entities_filtered{name='pipe',position={%g,%g},radius=40}) do if e.fluidbox[1] and e.fluidbox[1].name=='water' then local dd=(e.position.x-(%g))^2+(e.position.y-(%g))^2 if not bd or dd<bd then best,bd=e,dd end end end rcon.print(best and (best.position.x..','..best.position.y) or 'none')"""
near = s.run(NEAR % (cx, cy, cx, cy))
gx, gy = [float(v) for v in near.split(",")]
print("placed:", out or "ok", "| nearest water pipe", near, "| route:", s.pipe((cx, cy - 2), (gx, gy), box=40))
print(s.run("""local cx,cy=%g,%g local a=s.find_entities_filtered{name='assembling-machine-2',position={cx,cy},radius=0.5}[1] local i1=s.find_entities_filtered{name='inserter',position={cx-2,cy},radius=0.3}[1] local i2=s.find_entities_filtered{name='inserter',position={cx+2,cy},radius=0.3}[1]
rcon.print('concrete '..st(a)..' water '..(a.fluidbox[1] and math.floor(a.fluidbox[1].amount) or 0)..' in-inserter '..st(i1)..' out-inserter '..st(i2))""" % (cx, cy)))
# move bricks and ore into the input chest
print(s.run("""local cx,cy=%g,%g local moved=0 local c=s.find_entities_filtered{name='wooden-chest',position={cx-3,cy},radius=0.3}[1]
for item,cap in pairs{['iron-ore']=100,['stone-brick']=600} do local inv=c.get_inventory(defines.inventory.chest) local missing=cap-inv.get_item_count(item)
  if missing>0 then for _,e in pairs(s.find_entities_filtered{type={'container','furnace'},force=F}) do if missing<=0 then break end if e~=c then local ei=(e.type=='furnace') and e.get_output_inventory() or e.get_inventory(defines.inventory.chest) local h=ei.get_item_count(item) if h>0 then local n=c.insert{name=item,count=math.min(h,missing)} if n>0 then ei.remove{name=item,count=n} missing=missing-n moved=moved+n end end end end end end
rcon.print('ore and brick moved '..moved)""" % (cx, cy)))
