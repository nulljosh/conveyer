#!/usr/bin/env python3
"""statline.py [component] : append one detailed line to logs/conveyer.log and print it.
Format: ISO time | component | key=value ... (same keys every time, so it greps and graphs).
Covers research, labs, power, tiles, stocks, bag, base size, character position, enemies."""
import json, sys, time
from pathlib import Path
import factorio_rcon as f

ROOT = Path(__file__).resolve().parent.parent
LUA = """/silent-command local s=game.surfaces[1] local F=game.forces.player local m={} for k,v in pairs(defines.entity_status) do m[v]=k end
local function count(n) return s.count_entities_filtered{name=n,force='player'} end
local function status(n) local t={} for _,e in pairs(s.find_entities_filtered{name=n,force='player'}) do local k=m[e.status] t[k]=(t[k] or 0)+1 end return t end
local ch=s.find_entities_filtered{type='character'}[1] local inv=ch.get_main_inventory()
local techs=0 for _,t in pairs(F.technologies) do if t.researched then techs=techs+1 end end
local r=F.current_research local packs={} for _,l in pairs(s.find_entities_filtered{name='lab'}) do local i=l.get_inventory(defines.inventory.lab_input) packs[#packs+1]=i.get_item_count('automation-science-pack')..'/'..i.get_item_count('logistic-science-pack') end
local function chest(n) local k=0 for _,e in pairs(s.find_entities_filtered{type='container',force='player'}) do k=k+e.get_inventory(defines.inventory.chest).get_item_count(n) end return k end
local bag={} for _,n in ipairs{'coal','iron-plate','copper-plate','steel-plate','firearm-magazine','advanced-circuit','electronic-circuit'} do bag[n]=inv.get_item_count(n) end
local power=0 local engines=status('steam-engine') 
rcon.print(helpers.table_to_json{tick=game.tick,speed=game.speed,techs=techs,research=r and r.name or '',pct=math.floor(F.research_progress*100),queue=#F.research_queue,
 labs=status('lab'),lab_packs=packs,drills=status('electric-mining-drill'),furnaces=status('steel-furnace'),boilers=status('boiler'),engines=engines,
 assemblers={a2=count('assembling-machine-2'),a1=count('assembling-machine-1')},entities=#s.find_entities_filtered{force='player'},
 sci_stock={red=chest('automation-science-pack'),green=chest('logistic-science-pack')},bag=bag,pos={math.floor(ch.position.x),math.floor(ch.position.y)},
 nests=s.count_entities_filtered{type='unit-spawner',position=ch.position,radius=150},evolution=string.format('%.2f',game.forces.enemy.get_evolution_factor(s))})"""

comp = sys.argv[1] if len(sys.argv) > 1 else "tick"
try:
    d = json.loads(f.RCONClient("127.0.0.1", 27000, "factorio", timeout=30).send_command(" ".join(LUA.split("\n"))))
    flat = lambda v: ",".join(f"{k}:{x}" for k, x in v.items()) if isinstance(v, dict) else (",".join(map(str, v)) if isinstance(v, list) else v)
    line = " ".join(f"{k}={flat(v) or '-'}" for k, v in d.items())
except Exception as e:  # logging must never take the caller down
    line = f"error={type(e).__name__}:{e}"
out = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} | {comp} | {line}"
(ROOT / "logs").mkdir(exist_ok=True)
with open(ROOT / "logs" / "conveyer.log", "a") as fh: fh.write(out + "\n")
print(out)
