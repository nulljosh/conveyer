#!/usr/bin/env python3
"""power.py [N]: N more steam boilers (default 5) with two engines each on the east shore, +1.8 MW per column; coal arrives by
inserter from a chest that this script tops up from the big coal stores. Idempotent; rerun refills the chests.
The grid was ~9 MW and everything read low_power once the farms, labs and 20 tiles came online.
The pump at (56.5,-0.5) facing east sits on the shore (water starts at x=57); can_place alone accepts dry spots. ponytail: boilers face south at y=0, engines hang below; columns on a 4-tile pitch so a pipe, a pole and a gap fit between them."""
import sys, factorio_rcon as f
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=90)
print(c.send_command(" ".join("""/silent-command local s=game.surfaces[1] local d=defines.direction local out={} local N=%d
local function put(n,x,y,dir) local e=s.find_entities_filtered{name=n,position={x,y},radius=0.3}[1] if e then return e end
  if not s.can_place_entity{name=n,position={x,y},direction=dir,force='player'} then out[#out+1]='BLOCKED '..n..' '..x..','..y return nil end
  return s.create_entity{name=n,position={x,y},direction=dir,force='player'} end
local pump=put('offshore-pump',56.5,-0.5,d.east)
for px=55.5,53.5,-1 do put('pipe',px,-0.5) end
for i=0,N-1 do local cx=51.5-4*i
  local b=put('boiler',cx,0,d.south)
  if b then put('steam-engine',cx,3.5,d.south) put('steam-engine',cx,8.5,d.south)
    put('wooden-chest',cx,-2.5) local ins=put('inserter',cx,-1.5,d.south) if ins and ins.drop_position.y<ins.position.y then ins.direction=(ins.direction+8)%%16 end
    put('medium-electric-pole',cx+2,3.5) put('medium-electric-pole',cx+2,-2.5)
    if i<N-1 then put('pipe',cx-2,-0.5) end end end
local main=s.find_entities_filtered{name='lab'}[1].electric_network_id
local e=s.find_entities_filtered{name='steam-engine',position={51.5,3.5},radius=0.5}[1]
if e and e.electric_network_id~=main then local best,bd for _,q in pairs(s.find_entities_filtered{type='electric-pole',position={53.5,-2.5},radius=40}) do if q.electric_network_id==main then local dd=((q.position.x-53.5)^2+(q.position.y+2.5)^2)^0.5 if not bd or dd<bd then best,bd=q,dd end end end
  if best then local n=math.ceil(bd/7) for k=1,n-1 do local x=math.floor(53.5+(best.position.x-53.5)*k/n)+.5 local y=math.floor(-2.5+(best.position.y+2.5)*k/n)+.5 local p=s.find_non_colliding_position('medium-electric-pole',{x,y},3,1) if p then s.create_entity{name='medium-electric-pole',position=p,force='player'} end end end end
-- feed: top every new boiler chest up to 700 coal from the biggest coal stores
for _,ch in pairs(s.find_entities_filtered{name='wooden-chest',area={{30,-3},{54,-2}}}) do local inv=ch.get_inventory(defines.inventory.chest) local need=700-inv.get_item_count('coal')
  if need>0 then for _,src in pairs(s.find_entities_filtered{type='container',force='player'}) do if need<=0 then break end if src~=ch and not (src.position.y>-3.1 and src.position.y<-1.9 and src.position.x>30 and src.position.x<54) then local si=src.get_inventory(defines.inventory.chest) local h=si.get_item_count('coal') if h>200 then local t=math.min(h-200,need) local n=inv.insert{name='coal',count=t} si.remove{name='coal',count=n} need=need-n end end end end end
local m={} for k,v in pairs(defines.entity_status) do m[v]=k end local st={} for _,b in pairs(s.find_entities_filtered{name='boiler',position={44,0},radius=12}) do st[m[b.status]]=(st[m[b.status]] or 0)+1 end
rcon.print('pump '..tostring(pump~=nil)..' boilers '..serpent.line(st)..' '..table.concat(out,' | '))""".replace("\n-- feed: top every new boiler chest up to 700 coal from the biggest coal stores\n","\n").split("\n")) % N))
