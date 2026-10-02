#!/usr/bin/env python3
"""sulfur.py: second chemical plant (sulfur) beside the plastic plant, gas tapped from its pipe, water brought 90 tiles from
the boiler pumps by underground pipe along y=-5.5. Idempotent. Blue science needs sulfur; the nearest water is east of the base.
ponytail: greedy underground hops, stops at the first blocked row and says where; hand-route that gap."""
import factorio_rcon as f
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=90)
run = lambda l: c.send_command(" ".join(l.split("\n")))
print(run("""/silent-command local s=game.surfaces[1] local d=defines.direction local out={}
local function put(n,x,y,dir) local e=s.find_entities_filtered{name=n,position={x,y},radius=0.3}[1] if e then return e end
  if not s.can_place_entity{name=n,position={x,y},direction=dir,force='player'} then out[#out+1]='BLOCKED '..n..' '..x..','..y return nil end
  return s.create_entity{name=n,position={x,y},direction=dir,force='player'} end
local pl=put('chemical-plant',-30.5,-8.5,d.south) if pl and pl.get_recipe()==nil then pl.set_recipe('sulfur') end
put('medium-electric-pole',-33.5,-7.5)
for x=-35.5,-31.5 do put('pipe',x,-5.5) end put('pipe',-31.5,-6.5)
put('pipe',-29.5,-6.5) put('pipe',-29.5,-5.5)
local x=-28.5 local hops=0
while x<50 and hops<12 do
  local a=put('pipe-to-ground',x,-5.5,d.west) if not a then break end
  local placed=false
  for L=10,3,-1 do
    local b=s.find_entities_filtered{name='pipe-to-ground',position={x+L,-5.5},radius=0.3}[1]
    if b or (s.can_place_entity{name='pipe-to-ground',position={x+L,-5.5},direction=d.east,force='player'} and s.can_place_entity{name='pipe-to-ground',position={x+L+1,-5.5},direction=d.west,force='player'}) then
      put('pipe-to-ground',x+L,-5.5,d.east) x=x+L+1 placed=true break end end
  if not placed then out[#out+1]='no free hop after '..x break end hops=hops+1 end
put('offshore-pump',55.5,-4.5,d.south) put('pipe',55.5,-5.5)  -- pump output faces opposite its direction, so south here puts it north into a pipe beside the last underground end
out[#out+1]='reached x='..x..' hops='..hops
rcon.print(table.concat(out,' | '))"""))
