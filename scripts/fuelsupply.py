#!/usr/bin/env python3
"""fuelsupply.py: the remote item moves for the fuel chain, every keepbusy pass. Solid fuel from every plant chest goes to the rocket fuel
assemblers' input chests (300 each), steel plates and the like are left to the planner. Mirrors the planner's supply: a chest is filled from any
other container that holds the item, never from the chests it is meant to fill. Reads the complex site from .world/advoil.json."""
import json
from pathlib import Path
from blocks import Site

ROOT = Path(__file__).resolve().parent.parent
site = json.loads((ROOT / ".world" / "advoil.json").read_text()) if (ROOT / ".world" / "advoil.json").exists() else None
if not site: raise SystemExit("no advoil site yet")
rx, ry = site["rx"], site["ry"]
s = Site()
print(s.run("""local rx,ry=%g,%g local moved=0
local function ch(x,y) return s.find_entities_filtered{name='wooden-chest',position={x,y},radius=0.3}[1] end
local fill={} for _,ax in ipairs{rx+2,rx+6,rx+10} do local c=ch(ax-1,ry-10) if c then fill[#fill+1]=c end end
local function isfill(e) for _,c in ipairs(fill) do if c==e then return true end end return false end
for _,c in ipairs(fill) do local inv=c.get_inventory(defines.inventory.chest) local missing=300-inv.get_item_count('solid-fuel')
  if missing>0 then for _,e in pairs(s.find_entities_filtered{type='container',force=F}) do if missing<=0 then break end
    if not isfill(e) then local ei=e.get_inventory(defines.inventory.chest) local h=ei.get_item_count('solid-fuel') if h>0 then local n=c.insert{name='solid-fuel',count=math.min(h,missing)} if n>0 then ei.remove{name='solid-fuel',count=n} missing=missing-n moved=moved+n end end end end end end
local fill2={} for _,ax in ipairs{rx-9,rx-5} do local c=ch(ax-1,ry+4) if c then fill2[#fill2+1]=c end end
local function isfill2(e) for _,c in ipairs(fill2) do if c==e then return true end end return false end
for _,c in ipairs(fill2) do for item,cap in pairs{['engine-unit']=60,['electronic-circuit']=200} do local inv=c.get_inventory(defines.inventory.chest) local missing=cap-inv.get_item_count(item)
  if missing>0 then for _,e in pairs(s.find_entities_filtered{type='container',force=F}) do if missing<=0 then break end
    if not isfill2(e) and not isfill(e) then local ei=e.get_inventory(defines.inventory.chest) local h=ei.get_item_count(item) if h>0 then local n=c.insert{name=item,count=math.min(h,missing)} if n>0 then ei.remove{name=item,count=n} missing=missing-n moved=moved+n end end end end end end end
rcon.print('fuel chain items moved '..moved)""" % (rx, ry)))
