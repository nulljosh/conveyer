#!/usr/bin/env python3
"""barrels.py: crude by barrel instead of by the 320-tile pipe. Joining the four rich wells to the old line killed all flow (tested eight ways,
see docs/LEARNINGS.md), so the wells fill barrels at the field and the loop moves the full barrels to emptying assemblers beside the refinery,
the same remote chest-to-chest move the planner already uses for every other item. `barrels.py` builds both ends (idempotent),
`barrels.py move` shuttles barrels (keepbusy runs it every pass). Ports were read from the game; an inserter's direction is the side it picks
from; an assembler's direction must be set after create. EMPTIERS is a list because one emptier fed the refinery at only ~4 crude/s.
ponytail: one filler (about 180 crude/s); add emptiers by adding a row to EMPTIERS."""
import sys, json
from pathlib import Path
import factorio_rcon as f
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=60)
run = lambda l: c.send_command(" ".join(l.split("\n")))
_F = Path(__file__).resolve().parent.parent / ".world" / "fillers.json"   # oilfield2.py appends here
FILLERS = [tuple(x) for x in (json.loads(_F.read_text()) if _F.exists() else [[264.5, 82.5]])]
FX, FY = FILLERS[0]                       # the first filler at the east field is the one this script builds
import json
from pathlib import Path
_E = Path(__file__).resolve().parent.parent / ".world" / "emptiers.json"   # refineries.py appends here
EMPTIERS = [tuple(e) for e in (json.loads(_E.read_text()) if _E.exists() else [[-37.5, 3.5], [-33.5, 3.5]])]
LIST = ",".join("{%g,%g}" % e for e in EMPTIERS)
BUILD_LIST = ",".join("{%g,%g}" % e for e in EMPTIERS[:2])   # only the first two are built here; refineries.py builds the rest with their refineries
if len(sys.argv) > 2 and sys.argv[1] == "stock":   # barrels.py stock N: steel from stores becomes N empty barrels in the filler input chests (hand-crafted barrels, one steel each)
    FL = ",".join("{%g,%g}" % f_ for f_ in FILLERS)
    print(run("""/silent-command local s=game.surfaces[1] local need=%d local got=0
for _,e in pairs(s.find_entities_filtered{type='container',force='player'}) do if got>=need then break end local inv=e.get_inventory(defines.inventory.chest) local h=inv.get_item_count('steel-plate') if h>200 then local n=math.min(need-got,h-150) got=got+inv.remove{name='steel-plate',count=n} end end
local FL={%s} local per=math.ceil(got/#FL) local ins=0
for _,f in ipairs(FL) do local c=s.find_entities_filtered{name={'wooden-chest','steel-chest'},position={f[1]-3,f[2]+1},radius=0.3}[1] if c and got>0 then local k=c.insert{name='barrel',count=math.min(per,got)} ins=ins+k got=got-k end end
rcon.print('barrels stocked '..ins)""" % (int(sys.argv[2]), FL)))
    raise SystemExit
if len(sys.argv) > 1 and sys.argv[1] == "move":
    FL = ",".join("{%g,%g}" % f_ for f_ in FILLERS)
    print(run("""/silent-command local s=game.surfaces[1] local moved=0
local function ch(x,y) return s.find_entities_filtered{name={'wooden-chest','steel-chest'},position={x,y},radius=0.3}[1] end
local function take(c,item) if not c then return 0 end local inv=c.get_inventory(defines.inventory.chest) local n=inv.get_item_count(item) if n>0 then inv.remove{name=item,count=n} end return n end
local E={%s} local FL={%s}
local full=0 for _,f in ipairs(FL) do full=full+take(ch(f[1]+3,f[2]),'crude-oil-barrel') end
for _,e in ipairs(E) do full=full+take(ch(e[1]-1,e[2]+3),'crude-oil-barrel') end
local per=math.ceil(full/#E)
for _,e in ipairs(E) do local c=ch(e[1]-1,e[2]+3) local give=math.min(per,full) if c and give>0 then local k=c.insert{name='crude-oil-barrel',count=give} full=full-k moved=moved+k end end
if full>0 then local c=ch(E[1][1]-1,E[1][2]+3) if c then c.insert{name='crude-oil-barrel',count=full} end end
local empty=0 for _,e in ipairs(E) do empty=empty+take(ch(e[1]+1,e[2]+3),'barrel') end
local per2=math.ceil(empty/#FL) for _,f in ipairs(FL) do local give=math.min(per2,empty) local c=ch(f[1]-3,f[2]+1) if c and give>0 then c.insert{name='barrel',count=give} empty=empty-give end end
rcon.print('barrels moved full '..moved)""" % (LIST, FL)))
    raise SystemExit
print(run("""/silent-command local s=game.surfaces[1] local d=defines.direction local F=game.forces.player local out={}
local function put(n,x,y,dir,rec) local e=s.find_entities_filtered{name=n,position={x,y},radius=0.3}[1]
  if not e then if not s.can_place_entity{name=n,position={x,y},direction=dir,force=F} then out[#out+1]='BLOCKED '..n..' '..x..','..y return nil end
    e=s.create_entity{name=n,position={x,y},direction=dir,force=F} end
  if e and rec and e.get_recipe()==nil then e.set_recipe(rec) end
  if e and rec and dir and e.direction~=dir then e.direction=dir end return e end
local FX,FY=%g,%g
for x=269.5,FX,-1 do put('pipe',x,FY-2) end
put('assembling-machine-2',FX,FY,d.north,'crude-oil-barrel')
put('inserter',FX-2,FY+1,d.west) put('wooden-chest',FX-3,FY+1)
put('inserter',FX+2,FY,d.west) put('wooden-chest',FX+3,FY)
put('medium-electric-pole',FX+2,FY+1)
local E={%s}
for i,e in ipairs(E) do local EX,EY=e[1],e[2]
  put('assembling-machine-2',EX,EY,d.south,'empty-crude-oil-barrel')
  put('pipe',EX,EY-2)
  put('inserter',EX-1,EY+2,d.south) put('wooden-chest',EX-1,EY+3)
  put('inserter',EX+1,EY+2,d.north) put('wooden-chest',EX+1,EY+3)
  put('medium-electric-pole',EX-3+(i==1 and 0 or 6),EY+1)
  if i>1 then local px=E[1][1] for x=px+1,EX do put('pipe',x,EY-2) end end end
put('medium-electric-pole',E[1][1]+2,E[1][2]+3)
local m={} for k,v in pairs(defines.entity_status) do m[v]=k end
local fa=s.find_entities_filtered{name='assembling-machine-2',position={FX,FY},radius=0.5}[1]
if fa then out[#out+1]='filler '..m[fa.status]..' net '..tostring(fa.electric_network_id)..' crude '..(fa.fluidbox[1] and math.floor(fa.fluidbox[1].amount) or 0) end
for i,e in ipairs(E) do local ea=s.find_entities_filtered{name='assembling-machine-2',position={e[1],e[2]},radius=0.5}[1] if ea then out[#out+1]='emptier'..i..' '..m[ea.status]..' net '..tostring(ea.electric_network_id) end end
rcon.print(table.concat(out,' | '))""" % (FX, FY, BUILD_LIST)))
