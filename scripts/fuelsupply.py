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
local cc=ch(36.5,-11.5) if cc then local inv=cc.get_inventory(defines.inventory.chest)
  local mb=600-inv.get_item_count('stone-brick') if mb>0 then for _,e in pairs(s.find_entities_filtered{type={'container','furnace'},force=F}) do if mb<=0 then break end if e~=cc then local ei=(e.type=='furnace') and e.get_output_inventory() or e.get_inventory(defines.inventory.chest) local h=ei.get_item_count('stone-brick') if h>0 then local n=cc.insert{name='stone-brick',count=math.min(h,mb)} if n>0 then ei.remove{name='stone-brick',count=n} mb=mb-n moved=moved+n end end end end end
  local mo=120-inv.get_item_count('iron-ore') if mo>0 then for _,e in pairs(s.find_entities_filtered{type='furnace',force=F}) do if mo<=0 then break end local src=e.get_inventory(defines.inventory.furnace_source) local h=src and src.get_item_count('iron-ore') or 0 if h>10 then local n=cc.insert{name='iron-ore',count=math.min(h-5,mo)} if n>0 then src.remove{name='iron-ore',count=n} mo=mo-n moved=moved+n end end end end end
rcon.print('fuel chain items moved '..moved)""" % (rx, ry)))
