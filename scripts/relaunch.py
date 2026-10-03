#!/usr/bin/env python3
"""relaunch.py: ASSISTED relaunch for the camera. The world was rolled back to an old copy after the 21:11 server crash, so the silo and the stock of
processing units, low density structures and rocket fuel are gone. The legit launch happened at 20:45 (v2.0.0). This script puts the silo back (console),
joins it to the grid, and fills a bank of five steel chests with the 100 rocket parts' worth of items (console). From there the normal silo feed line
(siloline.py) carries the items to the silo's three chests, the silo crafts the 100 parts itself and launch_rocket() fires when part 100 lands.
Everything it creates from nothing is labelled assisted; say so wherever the video is shown. Idempotent: reruns only refill the bank to 1,000 each.
`relaunch.py` prepares; run siloline.py (the shuttle loop does) to feed and launch."""
import subprocess, sys
from pathlib import Path
from blocks import Site

ROOT = Path(__file__).resolve().parent.parent
s = Site(timeout=120)
print(s.run("""local silo=s.find_entities_filtered{name='rocket-silo'}[1] local out={}
if not silo and s.can_place_entity{name='rocket-silo',position={-57.5,10.5},force=F} then silo=s.create_entity{name='rocket-silo',position={-57.5,10.5},force=F} out[#out+1]='silo placed' end
if not silo then rcon.print('NO SPOT FOR THE SILO') return end
local p=power(-63.5,6.5) out[#out+1]='silo pole net='..tostring(p and p.electric_network_id)..' silo net='..tostring(silo.electric_network_id)
local want={['processing-unit']=1000,['low-density-structure']=1000,['rocket-fuel']=1000}
local have={} for _,e in pairs(s.find_entities_filtered{name='steel-chest',force=F,position={-72,22},radius=14}) do for it,_ in pairs(want) do have[it]=(have[it] or 0)+e.get_inventory(defines.inventory.chest).get_item_count(it) end end
local function bank() local pos=s.find_non_colliding_position('steel-chest',{-72,22},12,1) return pos and s.create_entity{name='steel-chest',position=pos,force=F} end
for it,n in pairs(want) do local need=n-(have[it] or 0)
  while need>0 do local c=bank() if not c then out[#out+1]='no room for a bank chest' break end local k=c.insert{name=it,count=math.min(need,480)} need=need-k if k==0 then break end end end
out[#out+1]='bank filled' rcon.print(table.concat(out,' | ')) """))
print(subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/siloline.py")], capture_output=True, text=True).stdout.strip()[:400])
