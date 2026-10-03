#!/usr/bin/env python3
"""combat.py: the fight feed for the live window. Twice a second, while someone watches, one RCON call lists every enemy within 75 tiles of the
engineer (biters, spitters, worms, nests, with a size 0 to 3) and every player gun turret with its magazine count. A turret whose count dropped
since the last poll is firing, and stays flagged for 2 s. Writes combat.json; the menu bar app draws red markers for enemies and a flash on
firing turrets. Stops when runner.pid is gone; `combat.py --once` prints one snapshot.
Codes: kind 0 biter, 1 spitter, 2 worm, 3 nest; size 0 small, 1 medium, 2 big, 3 behemoth.
ponytail: magazine deltas stand in for 'is shooting'; swap for a real shooting_target read if the API ever exposes one."""
import json, os, sys, time
from pathlib import Path
import factorio_rcon as f

ROOT = Path(__file__).resolve().parent.parent
OUT, WATCH = ROOT / "combat.json", ROOT / ".watching"
R = 75
LUA = """/silent-command local s=game.surfaces[1] local c=s.find_entities_filtered{type='character'}[1] if not c then rcon.print('') return end
local p=c.position local o={string.format('p:%%.1f:%%.1f',p.x,p.y)}
for _,e in pairs(s.find_entities_filtered{position=p,radius=%d,force='enemy',type={'unit','unit-spawner','turret'}}) do local n=e.name local z=0
  if n:find('behemoth') then z=3 elseif n:find('big') then z=2 elseif n:find('medium') then z=1 end
  local k=0 if e.type=='unit-spawner' then k=3 elseif e.type=='turret' then k=2 elseif n:find('spitter') then k=1 end
  o[#o+1]=string.format('e:%%.1f:%%.1f:%%d:%%d',e.position.x,e.position.y,k,z) end
for _,t in pairs(s.find_entities_filtered{position=p,radius=%d,force='player',type='ammo-turret'}) do
  o[#o+1]=string.format('t:%%.1f:%%.1f:%%d',t.position.x,t.position.y,t.get_inventory(defines.inventory.turret_ammo).get_item_count()) end
rcon.print(table.concat(o,';'))""" % (R, R)


def watching():
    try: return time.time() - WATCH.stat().st_mtime < 8
    except OSError: return False


def snapshot(c, last_mags, fired_at):
    raw = c.send_command(" ".join(LUA.split("\n"))).strip()
    player, enemies, turrets, now = [0, 0], [], [], time.time()
    for row in raw.split(";"):
        p = row.split(":")
        try:
            if p[0] == "p": player = [float(p[1]), float(p[2])]
            elif p[0] == "e": enemies.append([float(p[1]), float(p[2]), int(p[3]), int(p[4])])
            elif p[0] == "t":
                key = (p[1], p[2]); m = int(p[3])
                if key in last_mags and m < last_mags[key]: fired_at[key] = now
                last_mags[key] = m
                turrets.append([float(p[1]), float(p[2]), 1 if now - fired_at.get(key, 0) < 2 else 0])
        except (ValueError, IndexError):
            pass   # a truncated row: the next poll repaints
    return {"t": now, "player": player, "enemies": enemies, "turrets": turrets}


if __name__ == "__main__":
    c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=8)
    last, fired = {}, {}
    if "--once" in sys.argv:
        d = snapshot(c, last, fired); print(len(d["enemies"]), "enemies,", len(d["turrets"]), "turrets", d["player"]); sys.exit()
    while (ROOT / "runner.pid").exists():
        if not watching(): time.sleep(1.0); continue
        try:
            d = snapshot(c, last, fired)
            tmp = OUT.with_suffix(".tmp"); tmp.write_text(json.dumps(d)); os.replace(tmp, OUT)
        except Exception as e:   # server restarting: reconnect next lap
            print("combat:", e, file=sys.stderr)
            try: c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=8)
            except Exception: time.sleep(2)
        time.sleep(0.5)
