#!/usr/bin/env python3
"""livefeed.py: the live part of the live view. Writes live.json (character position) about 5 times a second, but only while
the menu bar app says someone is looking (.watching touched in the last 8 s); otherwise it sleeps and costs nothing.
One persistent RCON connection, one tiny Lua call that caches the character entity, and a file write only when it moved.
Stops when runner.pid is gone."""
import json, os, time
from pathlib import Path
import factorio_rcon as f

ROOT = Path(__file__).resolve().parent.parent
LIVE, WATCH, HOTBAR = ROOT / "live.json", ROOT / ".watching", ROOT / "hotbar.json"
LUA = ("/silent-command local c=storage.cv_char if not (c and c.valid) then c=game.surfaces[1].find_entities_filtered{type='character'}[1] storage.cv_char=c end "
       "rcon.print(c.position.x..','..c.position.y..','..game.tick)")
HOTBAR_LUA = ("/silent-command local c=storage.cv_char if not (c and c.valid) then c=game.surfaces[1].find_entities_filtered{type='character'}[1] storage.cv_char=c end "
              "local inv=c.get_main_inventory() if not inv then rcon.print('') return end "
              "local items={} for _,v in pairs(inv.get_contents()) do table.insert(items,{name=v.name,count=v.count}) end "
              "table.sort(items,function(a,b) return a.count>b.count end) "
              "local out='' for i=1,math.min(10,#items) do out=out..items[i].name..','..items[i].count..';' end "
              "rcon.print(out)")

def watching() -> bool:
    try: return time.time() - WATCH.stat().st_mtime < 8
    except OSError: return False

def runner_alive(gone=[0.0]) -> bool:
    """runner.pid vanishes for a few seconds during a restart; only quit if it stays gone for a minute."""
    if (ROOT / "runner.pid").exists(): gone[0] = 0.0; return True
    gone[0] = gone[0] or time.time()
    return time.time() - gone[0] < 60

rcon, last = None, None
hotbar_tick = 0
while runner_alive():
    if not watching():
        time.sleep(1.0); continue
    try:
        rcon = rcon or f.RCONClient("127.0.0.1", 27000, "factorio", timeout=5)
        x, y, tick = rcon.send_command(LUA).split(",")
        if (x, y) != last:
            tmp = LIVE.with_suffix(".tmp"); tmp.write_text(json.dumps({"x": float(x), "y": float(y), "tick": int(tick)}))
            os.replace(tmp, LIVE); last = (x, y)  # atomic, the app never reads half a file
        hotbar_tick += 1
        if hotbar_tick >= 5:  # about once per second
            hotbar_tick = 0
            raw = rcon.send_command(HOTBAR_LUA).strip()
            slots = []
            if raw:
                for item_str in raw.split(";"):
                    if item_str:
                        parts = item_str.split(",")
                        if len(parts) >= 2:
                            slots.append({"name": parts[0], "count": int(parts[1])})
            tmp = HOTBAR.with_suffix(".tmp"); tmp.write_text(json.dumps({"slots": slots}))
            os.replace(tmp, HOTBAR)
    except Exception:
        rcon = None; time.sleep(1.0); continue
    time.sleep(0.2)
