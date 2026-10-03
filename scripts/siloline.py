#!/usr/bin/env python3
"""siloline.py: feeds the existing rocket silo its 100 rocket parts the legit way. Three steel chests with fast inserters on the silo's west edge
(one each for processing units, low density structures and rocket fuel); each run tops the chests up from the base's other chests, the same
remote chest-to-chest move the planner uses. The silo crafts the parts itself (10 of each per part, 3 s). When part 100 lands it calls launch_rocket() itself
(only if .assist is absent). No .assist, no console parts. Idempotent replay; rerun to refill. `siloline.py` builds and feeds.
Built from game state: silo recipe and rocket-part recipe read from prototypes (100 parts x 10 processing unit, 10 low density structure, 10 rocket fuel).
ponytail: one feeder per item (about 2.3 items/s each at 1x); add a second inserter row if the silo starves at 10x."""
import sys
from pathlib import Path
import factorio_rcon as f

ITEMS = ["processing-unit", "low-density-structure", "rocket-fuel"]
KEEP = 480   # top each chest up to this many (a steel chest holds 480 of a 10-stack item)
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=90)
LUA = """/silent-command local s=game.surfaces[1] local F=game.forces.player local d=defines.direction local out={}
local silo=s.find_entities_filtered{name='rocket-silo'}[1] if not silo then rcon.print('NO SILO') return end
local sx,sy=silo.position.x,silo.position.y local items={%s} local mine={}
local function put(n,x,y,dir) local e=s.find_entities_filtered{name=n,position={x,y},radius=0.3}[1] if e then return e end
  if not s.can_place_entity{name=n,position={x,y},direction=dir,force=F} then out[#out+1]='BLOCKED '..n..' '..x..','..y return nil end
  return s.create_entity{name=n,position={x,y},direction=dir,force=F} end
local pole=put('medium-electric-pole',sx-5,sy+2)
local chests={}
for i,it in ipairs(items) do local y=sy-1+(i-1)
  put('fast-inserter',sx-5,y,d.west)
  local ch=put('steel-chest',sx-6,y) if ch then chests[it]=ch mine[ch.unit_number]=true end end
pcall(function() silo.auto_launch=true end)
local moved={} for it,ch in pairs(chests) do local ci=ch.get_inventory(defines.inventory.chest) local need=%d-ci.get_item_count(it)
  if need>0 then for _,e in pairs(s.find_entities_filtered{type='container',force=F}) do if need<=0 then break end
    if not mine[e.unit_number] then local inv=e.get_inventory(defines.inventory.chest) local h=inv.get_item_count(it)
      if h>0 then local t=math.min(h,need) local k=ci.insert{name=it,count=t} if k>0 then inv.remove{name=it,count=k} need=need-k end end end end end
  moved[#moved+1]=it..' in chest='..ci.get_item_count(it) end
if %d==1 and #s.find_entities_filtered{name='rocket-silo-rocket'}>0 and silo.rocket_silo_status==defines.rocket_silo_status.rocket_ready then local ok,err=pcall(function() silo.launch_rocket() end) out[#out+1]='LAUNCH ok='..tostring(ok)..' '..tostring(err)..' launched='..F.rockets_launched end
local ins=0 for _,e in pairs(s.find_entities_filtered{type='inserter',position={sx-5,sy},radius=3}) do if e.status~=defines.entity_status.no_power then ins=ins+1 end end
out[#out+1]='silo parts='..silo.rocket_parts..' status='..tostring(silo.status)..' powered inserters='..ins..' net silo/pole='..tostring(silo.electric_network_id)..'/'..tostring(pole and pole.electric_network_id)..' '..table.concat(moved,', ')
rcon.print(table.concat(out,' | '))"""
LAUNCH = 0 if any((Path(__file__).resolve().parent.parent / n).exists() for n in (".assist", ".hold")) else 1   # a legit launch means no .assist; .hold (a file) also pauses the launch so a camera can be rolling first; either way the script only feeds
print(c.send_command(" ".join((LUA % (",".join("'%s'" % i for i in ITEMS), KEEP, LAUNCH)).split("\n"))))
