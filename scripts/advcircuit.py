#!/usr/bin/env python3
"""advcircuit.py place|feed|status: one advanced-circuit assembler next to the plastic plant, hand-fed. Idempotent.
ponytail: create_entity over RCON like oil.py; the agent builds it itself once skills cover fluid-free assemblers."""
import sys, factorio_rcon as f
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=30)
run = lambda l: c.send_command(" ".join(l.split("\n")))
A = "{name='assembling-machine-2',position={-31.5,-2.5},radius=0.3}"
if sys.argv[1] == "place":
    print(run("""/silent-command local s=game.surfaces[1] local o={}
for _,p in ipairs{{-34.5,-4.5},{-34.5,-8.5}} do if #s.find_entities_filtered{name='medium-electric-pole',position=p,radius=0.3}==0 then s.create_entity{name='medium-electric-pole',position=p,force='player'} end end
local a=s.find_entities_filtered%s[1] if not a then a=s.create_entity{name='assembling-machine-2',position={-31.5,-2.5},force='player'} end
if not a then rcon.print('FAIL place') return end
if a.get_recipe()==nil then a.set_recipe('advanced-circuit') end
rcon.print('assembler net='..tostring(a.electric_network_id))""" % A))
elif sys.argv[1] == "feed":
    print(run("""/silent-command local s=game.surfaces[1] local a=s.find_entities_filtered%s[1]
local plant=s.find_entities_filtered{name='chemical-plant',position={-35.5,-8.5},radius=1}[1]
local inv=s.find_entities_filtered{type='character'}[1].get_main_inventory()
local n=plant.get_output_inventory().get_item_count('plastic-bar') local take=math.min(n,20)
if take>0 then plant.get_output_inventory().remove{name='plastic-bar',count=take} end
local got={} for k,v in pairs{['plastic-bar']=take,['electronic-circuit']=20,['copper-cable']=40} do
  local have=(k=='plastic-bar') and take or inv.get_item_count(k)
  local ins=0 if math.min(v,have)>0 then ins=a.insert{name=k,count=math.min(v,have)} end if k~='plastic-bar' and ins>0 then inv.remove{name=k,count=ins} end got[#got+1]=k..'='..ins end
rcon.print(table.concat(got,' '))""" % A))
else:
    print(run("""/silent-command local m={} for k,v in pairs(defines.entity_status) do m[v]=k end local a=game.surfaces[1].find_entities_filtered%s[1]
rcon.print(m[a.status]..' made='..a.products_finished..' out='..a.get_output_inventory().get_item_count('advanced-circuit'))""" % A))
