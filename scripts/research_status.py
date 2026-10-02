#!/usr/bin/env python3
"""Writes research.json (current tech, percent, tech count, queue) every 10s for the menu bar.
Stops when runner.pid is gone."""
import json, time
from pathlib import Path
import factorio_rcon

ROOT = Path(__file__).resolve().parent.parent
LUA = ("/silent-command local F=game.forces.player local r=F.current_research local n=0 for _,x in pairs(F.technologies) do if x.researched then n=n+1 end end "
       "local q={} for _,t in pairs(F.research_queue) do q[#q+1]=t.name end "
       "rcon.print(helpers.table_to_json{current=r and r.name or '', percent=math.floor(F.research_progress*100), techs=n, queue=q})")
while (ROOT / "runner.pid").exists():
    try:
        out = factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio").send_command(LUA)
        (ROOT / "research.json").write_text(out)
    except Exception:
        pass
    time.sleep(10)
