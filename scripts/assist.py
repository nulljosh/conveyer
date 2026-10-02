#!/usr/bin/env python3
"""ASSISTED mode (Joshua asked for v1 tonight, 2026-10-02): tops every lab to 200 of each pack through RCON, standing in for the
purple and yellow chains that are not built yet. Runs only while the file .assist exists. Anything shipped with this is labeled assisted."""
from pathlib import Path
import factorio_rcon as f
if not (Path(__file__).resolve().parent.parent / ".assist").exists(): raise SystemExit("no .assist file, assisted mode off")
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=30)
print(c.send_command("/silent-command local n=0 for _,l in pairs(game.surfaces[1].find_entities_filtered{name='lab'}) do for _,p in ipairs{'automation-science-pack','logistic-science-pack','chemical-science-pack','production-science-pack','utility-science-pack'} do local h=l.get_item_count(p) if h<200 then n=n+l.insert{name=p,count=200-h} end end end rcon.print('assist inserted '..n)"))
