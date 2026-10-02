#!/usr/bin/env python3
"""Writes research.json (current tech, percent, tech count, queue) every 10s for the menu bar.
Stops when runner.pid is gone."""
import json, time
from pathlib import Path
import sys
import factorio_rcon
sys.path.insert(0, str(Path(__file__).resolve().parent))
import terrain

ROOT = Path(__file__).resolve().parent.parent
LUA = ("/silent-command local F=game.forces.player local r=F.current_research local n=0 for _,x in pairs(F.technologies) do if x.researched then n=n+1 end end "
       "local seen={} local sn=0 local sd=0 local function walk(t) if seen[t.name] then return end seen[t.name]=true sn=sn+1 if t.researched then sd=sd+1 end for _,p in pairs(t.prerequisites) do walk(p) end end walk(F.technologies['rocket-silo']) "
       "local q={} for _,t in pairs(F.research_queue) do q[#q+1]=t.name end "
       "local labs=game.surfaces[1].find_entities_filtered{name='lab'} local w=0 for _,l in pairs(labs) do if l.status==defines.entity_status.working then w=w+1 end end "
       "rcon.print(helpers.table_to_json{current=r and r.name or '', percent=math.floor(F.research_progress*100), techs=n, queue=q, labs=#labs, labs_working=w, silo_done=sd, silo_total=sn})")
last = (None, -1, -1, time.time())
while (ROOT / "runner.pid").exists():
    try:
        rcon = factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio")
        d = json.loads(rcon.send_command(LUA)); now = time.time()
        if (d["current"], d["percent"], d["techs"]) != last[:3]: last = (d["current"], d["percent"], d["techs"], now)
        d["moving"] = now - last[3] < 90
        (ROOT / "research.json").write_text(json.dumps(d))
        if time.time() - (ROOT / ".watching").stat().st_mtime < 8 if (ROOT / ".watching").exists() else False:
            terrain.refresh(rcon)   # needs a viewer; refresh() itself skips unless preview.png is newer than the painted map
    except Exception:
        pass
    time.sleep(2.0 if (ROOT / ".watching").exists() and time.time() - (ROOT / ".watching").stat().st_mtime < 8 else 15.0)
