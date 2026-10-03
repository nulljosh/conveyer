#!/usr/bin/env python3
"""defend.py: a ring of gun turrets around the north-west oil field, kept topped up with piercing ammo. Biters killed 6 of 9 pumpjacks there.
Idempotent replay (a crash reverts the world, health.sh --fix and shuttle.sh both call it). Materials come out of the base chests (plates), like
barrels.py stock: a turret is 40 iron + 10 copper, a piercing magazine 4 iron + 1 steel + 5 copper. `defend.py` builds and tops up to AMMO each.
ponytail: gun turrets and a fixed ring; add laser turrets (laser-turret tech not researched) or walls when biters outgrow piercing."""
import sys
import factorio_rcon as f

CX, CY, R, N, AMMO = -213.0, -408.0, 28.0, 22, 40   # ring centre, radius, turret count, magazines per turret
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=120)
LUA = """/silent-command local s=game.surfaces[1] local F=game.forces.player local out={}
local function take(item,n) local got=0 for _,e in pairs(s.find_entities_filtered{type='container',force='player'}) do if got>=n then break end
  local inv=e.get_inventory(defines.inventory.chest) local h=inv.get_item_count(item) if h>0 then local t=math.min(h,n-got) inv.remove{name=item,count=t} got=got+t end end return got end
local function give(item,n) if n>0 then for _,e in pairs(s.find_entities_filtered{type='container',force='player'}) do local k=e.insert{name=item,count=n} n=n-k if n<=0 then break end end end end
local ts={} for _,t in pairs(s.find_entities_filtered{name='gun-turret',position={%g,%g},radius=%g}) do ts[#ts+1]=t end
local built=0 for i=1,%d do if #ts>=%d then break end local a=2*math.pi*i/%d local x,y=%g+%g*math.cos(a),%g+%g*math.sin(a)
  local p=s.find_non_colliding_position('gun-turret',{x,y},6,1) if p and (take('iron-plate',40)==40) then if take('copper-plate',10)==10 then
    local t=s.create_entity{name='gun-turret',position=p,force=F} if t then ts[#ts+1]=t built=built+1 end else give('iron-plate',40) end end end
local need=0 for _,t in pairs(ts) do need=need+math.max(0,%d-t.get_inventory(defines.inventory.turret_ammo).get_item_count('piercing-rounds-magazine')) end
local fi=take('iron-plate',need*4) local st=take('steel-plate',need) local co=take('copper-plate',need*5)
local can=math.min(math.floor(fi/4),st,math.floor(co/5)) give('iron-plate',fi-can*4) give('steel-plate',st-can) give('copper-plate',co-can*5)
local filled=0 for _,t in pairs(ts) do local have=t.get_inventory(defines.inventory.turret_ammo).get_item_count('piercing-rounds-magazine') local d=math.min(%d-have,can-filled) if d>0 then filled=filled+t.insert{name='piercing-rounds-magazine',count=d} end end
give('iron-plate',(can-filled)*4) give('steel-plate',can-filled) give('copper-plate',(can-filled)*5)
rcon.print('turrets '..#ts..' (+'..built..') mags added '..filled..' of '..need..' needed')"""
print(c.send_command(" ".join((LUA % (CX, CY, R + 12, N, N, N, CX, R, CY, R, AMMO, AMMO)).split("\n"))))
