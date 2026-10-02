#!/usr/bin/env python3
"""Rebuild the oil block in one shot (refinery, crude pipes, poles, plastic plant). Idempotent.
FLE's Lua state can't be saved, so the server always reboots to the 10:55 copy. Rerun this after any crash.
an output inserter and chest buffer plastic (a full plant stalled between 20 s passes); an inserter and chest feed the plant coal (hand-feeding 50 lasted 5 s at 10x). ponytail: create_entity over RCON, not the character walking; swap to skills when the agent builds this itself."""
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
put('wooden-chest',-32.5,-8.5)
put('wooden-chest',-35.5,-5.5)
local oi=s.find_entities_filtered{name='inserter',position={-35.5,-6.5},radius=0.3}[1] or s.create_entity{name='inserter',position={-35.5,-6.5},direction=d.south,force='player'}
if oi and oi.drop_position.y<oi.position.y then oi.direction=(oi.direction+8)%16 end
local ci=s.find_entities_filtered{name='inserter',position={-33.5,-8.5},radius=0.3}[1] or s.create_entity{name='inserter',position={-33.5,-8.5},direction=d.west,force='player'}
if ci and ci.drop_position.x>ci.position.x then ci.direction=(ci.direction+8)%16 end
local cc=s.find_entities_filtered{name='wooden-chest',position={-32.5,-8.5},radius=0.3}[1]
local pl=s.find_entities_filtered{name='chemical-plant',position={-35.5,-8.5},radius=0.3}[1]
local bag=s.find_entities_filtered{type='character'}[1].get_main_inventory()
if cc then local ci2=cc.get_inventory(defines.inventory.chest) for _,e in pairs(s.find_entities_filtered{type='container',force='player'}) do if e~=cc then local inv=e.get_inventory(defines.inventory.chest) local h=inv.get_item_count('coal') if h>400 then local need=780-ci2.get_item_count('coal') if need<=0 then break end local n=ci2.insert{name='coal',count=math.min(need,h-300)} if n>0 then inv.remove{name='coal',count=n} end end end end end
if cc then local h=math.min(700-cc.get_inventory(defines.inventory.chest).get_item_count('coal'),bag.get_item_count('coal')) if h>0 then bag.remove{name='coal',count=cc.get_inventory(defines.inventory.chest).insert{name='coal',count=h}} end end
if pl then local need=50-pl.get_item_count('coal') local h=math.min(need,bag.get_item_count('coal')) if h>0 then bag.remove{name='coal',count=pl.insert{name='coal',count=h}} end end
local m={} for k,v in pairs(defines.entity_status) do m[v]=k end
for _,n in ipairs{'oil-refinery','chemical-plant'} do local e=s.find_entities_filtered{name=n,area={{-42,-12},{-33,2}}}[1]
  if e then local fl={} for i=1,#e.fluidbox do local b=e.fluidbox[i] fl[#fl+1]=b and (b.name..'='..math.floor(b.amount)) or '-' end
  out[#out+1]=n..' '..(m[e.status] or '?')..' net='..tostring(e.electric_network_id)..' fluids '..table.concat(fl,' ') end end
rcon.print(table.concat(out,' | '))"""
print(c.send_command(" ".join(LUA.split("\n"))))
