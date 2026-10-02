#!/usr/bin/env python3
"""Rebuild the oil block in one shot (refinery, crude pipes, poles, plastic plant). Idempotent.
FLE's Lua state can't be saved, so the server always reboots to the 10:55 copy. Rerun this after any crash.
ponytail: create_entity over RCON, not the character walking; swap to skills when the agent builds this itself."""
import factorio_rcon as f
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=30)
LUA = """/silent-command local s=game.surfaces[1] local d=defines.direction local out={}
local function put(name,x,y,dir,recipe)
  local e=s.find_entities_filtered{name=name,position={x,y},radius=0.3}[1]
  if not e then e=s.create_entity{name=name,position={x,y},direction=dir or d.north,force='player'} end
  if not e then out[#out+1]='FAIL '..name..' '..x..','..y return end
  if recipe and e.get_recipe()==nil then e.set_recipe(recipe) end
  if dir and e.direction~=dir then e.direction=dir end
end
put('pipe',-47.5,-10.5) put('pipe',-47.5,-9.5) put('pipe',-47.5,-8.5)
put('pipe-to-ground',-47.5,-7.5,d.north) put('pipe-to-ground',-47.5,-2.5,d.south)
put('pipe',-47.5,-1.5) put('pipe',-47.5,-0.5)
for x=-47.5,-37.5 do put('pipe',x,0.5) end
put('oil-refinery',-38.5,-2.5,d.north,'basic-oil-processing')
put('medium-electric-pole',-43.5,-13.5) put('medium-electric-pole',-43.5,-9.5) put('medium-electric-pole',-38.5,-8.5) put('medium-electric-pole',-42.5,-3.5)
put('chemical-plant',-35.5,-8.5,d.south,'plastic-bar')
put('pipe',-36.5,-5.5) put('pipe',-36.5,-6.5)
local m={} for k,v in pairs(defines.entity_status) do m[v]=k end
for _,n in ipairs{'oil-refinery','chemical-plant'} do local e=s.find_entities_filtered{name=n,area={{-42,-12},{-33,2}}}[1]
  if e then local fl={} for i=1,#e.fluidbox do local b=e.fluidbox[i] fl[#fl+1]=b and (b.name..'='..math.floor(b.amount)) or '-' end
  out[#out+1]=n..' '..(m[e.status] or '?')..' net='..tostring(e.electric_network_id)..' fluids '..table.concat(fl,' ') end end
rcon.print(table.concat(out,' | '))"""
print(c.send_command(" ".join(LUA.split("\n"))))
