#!/usr/bin/env python3
"""livemap.py: the live part of the map. While someone watches (.watching touched in the last 8 s) it writes live_status.json about once a
second: every machine in view with a status code (0 working, 1 waiting for items, 2 stuck: no power, no fuel or output full). The menu bar
app draws these as pulsing dots over the map, so the view moves even when the map picture is a minute old. Stops when runner.pid is gone."""
import json, os, time
from pathlib import Path
import sys
import factorio_rcon as f
sys.path.insert(0, str(Path(__file__).resolve().parent))
import planner as P

ROOT = Path(__file__).resolve().parent.parent
OUT, WATCH, FRAME = ROOT / "live_status.json", ROOT / ".watching", ROOT / "frame.json"
LUA = ("/silent-command local s=game.surfaces[1] local S=defines.entity_status local o={} "
       "for _,e in pairs(s.find_entities_filtered{area={{%g,%g},{%g,%g}},force='player',type={'assembling-machine','furnace','lab','mining-drill','boiler','generator','chemical-plant','oil-refinery','rocket-silo'}}) do "
       "local st=e.status local c=1 if st==S.working or st==S.normal then c=0 elseif st==S.no_power or st==S.no_fuel or st==S.full_output or st==S.low_power or st==S.no_minable_resources or st==S.disabled_by_control_behavior then c=2 end "
       "o[#o+1]=string.format('%%.1f:%%.1f:%%d',e.position.x,e.position.y,c) end rcon.print(table.concat(o,';'))")

def watching() -> bool:
    try: return time.time() - WATCH.stat().st_mtime < 8
    except OSError: return False

WALK = ("/silent-command local c=storage.cv_char if not (c and c.valid) then c=game.surfaces[1].find_entities_filtered{type='character'}[1] storage.cv_char=c end "
        "local tx,ty=%g,%g local dx,dy=tx-c.position.x,ty-c.position.y local d=math.sqrt(dx*dx+dy*dy) "
        "if d>%g then c.teleport({c.position.x+dx/d*%g,c.position.y+dy/d*%g}) end rcon.print(d)")
def targets():
    return [(P.OX + (t["cell"] % P.COLS) * P.CW + 3.5, P.OY + (t["cell"] // P.COLS) * P.CH + 5) for t in P.load()]

rcon, walker, tgt, ti, lastmap = None, None, [], 0, 0.0
while (ROOT / "runner.pid").exists():
    if not watching(): time.sleep(1.0); continue
    try:
        walker = walker or f.RCONClient("127.0.0.1", 27000, "factorio", timeout=8)  # the player strolls tile to tile, 2.5 tiles per 0.25 s, like a brisk walk
        if not tgt: tgt = targets()
        if tgt and not (ROOT / ".rendering").exists():   # runner parks the player at the picture center while it reads the map
            d = float(walker.send_command(WALK % (*tgt[ti % len(tgt)], 2.5, 2.5, 2.5)).strip() or 0)
            if d <= 2.5: ti += 1; tgt = targets() if ti % len(tgt) == 0 else tgt
        if time.time() - lastmap < 0.8: time.sleep(0.25); continue
        lastmap = time.time()
        fr = json.loads(FRAME.read_text()); hw, hh = fr["w"] / fr["ppt"] / 2, fr["h"] / fr["ppt"] / 2
        rcon = rcon or f.RCONClient("127.0.0.1", 27000, "factorio", timeout=8)
        raw = rcon.send_command(LUA % (fr["cx"] - hw, fr["cy"] - hh, fr["cx"] + hw, fr["cy"] + hh))
        d = [[float(a), float(b), int(c)] for a, b, c in (p.split(":") for p in raw.split(";") if p)]
        tmp = OUT.with_suffix(".tmp"); tmp.write_text(json.dumps({"t": time.time(), "d": d})); os.replace(tmp, OUT)
    except Exception:
        rcon = walker = None; time.sleep(1.0); continue
    time.sleep(0.25)
