#!/usr/bin/env python3
"""livemap.py: the live part of the map. While someone watches (.watching touched in the last 8 s) it writes live_status.json about once a
second: every machine in view with a status code (0 working, 1 waiting for items, 2 stuck: no power, no fuel or output full). The menu bar
app draws these as pulsing dots over the map, so the view moves even when the map picture is a minute old. Stops when runner.pid is gone."""
import json, math, os, time
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
FOCUS = ROOT / ".focus"   # "x,y": the engineer patrols a ring of 9 tiles around that point instead of strolling the science tiles (silo for the launch, oil field for the fights)
def focus_targets():
    try: x, y = [float(v) for v in FOCUS.read_text().split(",")[:2]]
    except Exception: return None
    return [(x + 9 * math.cos(a * math.pi / 4), y + 9 * math.sin(a * math.pi / 4)) for a in range(8)]
COMBAT = ROOT / "combat.json"
ARMOR = "/silent-command local c=game.surfaces[1].find_entities_filtered{type='character'}[1] if c then c.destructible=false end"   # demo: the engineer cannot die on patrol (console assist, labelled as such); a dead character would break every loop that finds him
def attack_target():
    # the first turret that is firing right now (combat.py writes combat.json twice a second): the engineer runs to stand beside it
    try:
        d = json.loads(COMBAT.read_text())
        if time.time() - d["t"] > 4: return None
        fire = [t for t in d["turrets"] if t[2]]
        return (fire[0][0] + 4, fire[0][1] + 4) if fire else None
    except Exception: return None
def targets():
    return [(P.OX + (t["cell"] % P.COLS) * P.CW + 3.5, P.OY + (t["cell"] // P.COLS) * P.CH + 5) for t in P.load()]

TOUR = ("/silent-command local o={} for _,e in pairs(game.surfaces[1].find_entities_filtered{position={%g,%g},radius=42,force='player',name={'gun-turret','pumpjack'}}) do "
        "o[#o+1]=e.name..':'..e.position.x..':'..e.position.y end rcon.print(table.concat(o,';'))")
def field_tour(walker, fx, fy):
    """Every turret and pumpjack at the field in nearest-neighbour order from the focus: an inspection round, not a ring."""
    pts = []
    for r in walker.send_command(TOUR % (fx, fy)).split(";"):
        if r:
            k, x, y = r.split(":"); pts.append((float(x) + 2, float(y) + 2, k))
    out, cur = [], (fx, fy)
    while pts:
        nxt = min(pts, key=lambda q: (q[0] - cur[0]) ** 2 + (q[1] - cur[1]) ** 2); pts.remove(nxt); out.append(nxt); cur = nxt[:2]
    return out

rcon, walker, tgt, ti, lastmap, armored = None, None, [], 0, 0.0, False
tour, tour_i, arrived = [], 0, None
while (ROOT / "runner.pid").exists():
    if not watching(): time.sleep(1.0); continue
    if (ROOT / ".sweep").exists(): time.sleep(0.5); continue   # an assisted sweep (sweep.py) is moving the engineer
    try:
        walker = walker or f.RCONClient("127.0.0.1", 27000, "factorio", timeout=8)  # the player strolls tile to tile, 2.5 tiles per 0.25 s, like a brisk walk
        focus = FOCUS.read_text().strip() if FOCUS.exists() else ""
        field = bool(focus) and not focus.startswith("-57")   # oil-field mode: invulnerable, inspects turrets and pumpjacks, runs to a firing turret
        atk = None; lab = {}; goal = None
        if field:
            if not armored: walker.send_command(ARMOR); armored = True
            fx, fy = [float(v) for v in focus.split(",")[:2]]
            atk = attack_target()
            if atk: goal, lab = atk, {"label": "Responding to an attack"}
            else:
                if not tour: tour, tour_i = field_tour(walker, fx, fy), 0
                if tour:
                    gx, gy, k = tour[tour_i % len(tour)]; goal = (gx, gy)
                    lab = {"label": "Inspecting a gun turret" if k == "gun-turret" else "Checking a pumpjack"}
        elif focus:
            ft = focus_targets(); goal = ft[ti % len(ft)]; lab = {"label": "Guarding the rocket silo"}
        else:
            if not tgt: tgt = targets()
            goal = tgt[ti % len(tgt)]
        if goal and not (ROOT / ".rendering").exists():   # runner parks the player at the picture center while it reads the map
            d = float(walker.send_command(WALK % (*goal, 2.5, 2.5, 2.5)).strip() or 0)
            tl = P.load(); cur = tl[ti % len(tl)]["item"] if tl else ""   # engineer.json feeds the HUD line (label wins over the tile name)
            tmp2 = ROOT / "engineer.tmp"; tmp2.write_text(json.dumps({"item": cur, "t": time.time(), **lab})); os.replace(tmp2, ROOT / "engineer.json")
            if d <= 2.5:
                if field and not atk:   # stand at each stop for 3 s, then the next one; the round restarts when it ends
                    arrived = arrived or time.time()
                    if time.time() - arrived > 3:
                        arrived = None; tour_i += 1
                        if tour_i >= len(tour): tour = []
                else: ti += 1
            else: arrived = None
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
