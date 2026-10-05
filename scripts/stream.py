#!/usr/bin/env python3
"""stream.py: one feeder for the live window, in place of livefeed.py, combat.py and the status dots of livemap.py.
One RCON connection, one Lua call per frame. Each frame asks only for the parts that are due:
position 10 Hz, combat 2 Hz, status dots 1 Hz, hotbar and silo every 2 s.
It writes the files the app reads today (live.json, live_status.json, combat.json, hotbar.json, silo.json), each only when it changed,
plus stream.json with everything in one place (the app moves to that one file in plan step 3, see docs/LOOP-HANDOFF.md).
Like the old feeders it sleeps while nobody watches (.watching older than 8 s) and stops when runner.pid stays gone for a minute.
livemap.py keeps walking the engineer but skips its own dots read while stream.json is fresh.
`stream.py --once` prints one frame and exits."""
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCH, FRAME, STREAM = ROOT / ".watching", ROOT / "frame.json", ROOT / "stream.json"
FILES = {"pos": "live.json", "dots": "live_status.json", "combat": "combat.json", "hotbar": "hotbar.json", "silo": "silo.json"}
RATES = {"pos": 0.1, "combat": 0.5, "dots": 1.0, "hotbar": 2.0, "silo": 2.0}   # seconds between reads
COMBAT_R = 75
HOTBAR_KEYS = ["rocket-fuel", "low-density-structure", "processing-unit", "plastic-bar", "steel-plate", "iron-plate", "copper-plate", "coal", "crude-oil-barrel", "barrel"]

# Each part is a Lua function body that returns one string. No '--' comments and no newlines: they go into one joined RCON line.
CHAR = ("local c=storage.cv_char if not (c and c.valid) then c=game.surfaces[1].find_entities_filtered{type='character'}[1] storage.cv_char=c end "
        "if not c then return '' end ")
LUA = {
    "pos": CHAR + "return c.position.x..','..c.position.y..','..game.tick",
    "dots": ("local s=game.surfaces[1] local S=defines.entity_status local o={} "
             "for _,e in pairs(s.find_entities_filtered{area={{X1,Y1},{X2,Y2}},force='player',type={'assembling-machine','furnace','lab','mining-drill','boiler','generator','chemical-plant','oil-refinery','rocket-silo'}}) do "
             "local st=e.status local k=1 if st==S.working or st==S.normal then k=0 elseif st==S.no_power or st==S.no_fuel or st==S.full_output or st==S.low_power or st==S.no_minable_resources or st==S.disabled_by_control_behavior then k=2 end "
             "o[#o+1]=string.format('%.1f:%.1f:%d',e.position.x,e.position.y,k) end return table.concat(o,';')"),
    "combat": (CHAR + "local s=game.surfaces[1] local p=c.position local o={string.format('p:%.1f:%.1f',p.x,p.y)} "
               "for _,e in pairs(s.find_entities_filtered{position=p,radius=RAD,force='enemy',type={'unit','unit-spawner','turret'}}) do local n=e.name local z=0 "
               "if n:find('behemoth') then z=3 elseif n:find('big') then z=2 elseif n:find('medium') then z=1 end "
               "local k=0 if e.type=='unit-spawner' then k=3 elseif e.type=='turret' then k=2 elseif n:find('spitter') then k=1 end "
               "o[#o+1]=string.format('e:%.1f:%.1f:%d:%d',e.position.x,e.position.y,k,z) end "
               "for _,t in pairs(s.find_entities_filtered{position=p,radius=RAD,force='player',type='ammo-turret'}) do "
               "o[#o+1]=string.format('t:%.1f:%.1f:%d',t.position.x,t.position.y,t.get_inventory(defines.inventory.turret_ammo).get_item_count()) end "
               "return table.concat(o,';')").replace("RAD", str(COMBAT_R)),
    "hotbar": ("local keys={" + ",".join("'%s'" % k for k in HOTBAR_KEYS) + "} local tot={} "
               "for _,ch in pairs(game.surfaces[1].find_entities_filtered{type='container',force='player'}) do local inv=ch.get_inventory(defines.inventory.chest) "
               "for _,n in ipairs(keys) do tot[n]=(tot[n] or 0)+inv.get_item_count(n) end end "
               "local out='' for _,n in ipairs(keys) do out=out..n..','..(tot[n] or 0)..';' end return out"),
    "silo": ("local s=game.surfaces[1] local si=s.find_entities_filtered{name='rocket-silo'}[1] if not si then return '' end "
             "local rev={} for k,v in pairs(defines.entity_status) do rev[v]=k end "
             "return si.position.x..':'..si.position.y..':'..si.rocket_parts..':'..rev[si.status]..':'..game.forces.player.rockets_launched..':'.."
             "(#s.find_entities_filtered{name='rocket-silo-rocket'}>0 and 1 or 0)..':'..tostring(si.rocket_silo_status)"),
}


def due(now, last, rates=RATES):
    """The parts whose interval has passed, in a fixed order."""
    return [k for k in rates if now - last.get(k, float("-inf")) >= rates[k]]


def view_area(frame):
    """The map rectangle the window shows, from frame.json (center, pixels, pixels per tile)."""
    hw, hh = frame["w"] / frame["ppt"] / 2, frame["h"] / frame["ppt"] / 2
    return frame["cx"] - hw, frame["cy"] - hh, frame["cx"] + hw, frame["cy"] + hh


def build_lua(parts, area=None):
    """One RCON command that runs every requested part and prints 'name=result' lines."""
    calls = []
    for k in parts:
        body = LUA[k]
        if k == "dots":
            if area is None: continue
            for tok, v in zip(("X1", "Y1", "X2", "Y2"), area): body = body.replace(tok, "%g" % v)
        calls.append("O[#O+1]='%s='..(function() %s end)()" % (k, body))
    return "/silent-command local O={} " + " ".join(calls) + " rcon.print(table.concat(O,'\\n'))"


def split_reply(raw):
    out = {}
    for line in raw.splitlines():
        k, sep, v = line.partition("=")
        if sep and k in LUA: out[k] = v.strip()
    return out


def parse_pos(v):
    x, y, tick = v.split(",")
    return {"x": float(x), "y": float(y), "tick": int(tick)}


def parse_dots(v, now):
    return {"t": now, "d": [[float(a), float(b), int(c)] for a, b, c in (p.split(":") for p in v.split(";") if p)]}


def parse_combat(v, now, last_mags, fired_at):
    """Same output as combat.py. A turret whose magazine count dropped since the last read is firing, flagged for 2 s."""
    player, enemies, turrets = [0, 0], [], []
    for row in v.split(";"):
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
            pass   # a truncated row: the next read repaints
    return {"t": now, "player": player, "enemies": enemies, "turrets": turrets}


def parse_hotbar(v):
    slots = []
    for item in v.split(";"):
        p = item.split(",")
        if len(p) >= 2 and p[0]: slots.append({"name": p[0], "count": int(p[1])})
    return {"slots": slots}


def parse_silo(v, now):
    sx, sy, sp, ss, sl, sk, sr = v.split(":")
    return {"x": float(sx), "y": float(sy), "parts": int(sp), "status": ss, "launched": int(sl), "rocket": int(sk), "rocket_status": sr, "t": now}


def parse(reply, now, mags, fired):
    """Raw RCON reply to {part: data}. A part that came back empty or malformed is left out, so its old file stays."""
    out = {}
    for k, v in split_reply(reply).items():
        if not v: continue
        try:
            if k == "pos": out[k] = parse_pos(v)
            elif k == "dots": out[k] = parse_dots(v, now)
            elif k == "combat": out[k] = parse_combat(v, now, mags, fired)
            elif k == "hotbar": out[k] = parse_hotbar(v)
            elif k == "silo": out[k] = parse_silo(v, now)
        except (ValueError, IndexError):
            pass
    return out


def write_json(path, data):
    tmp = path.with_suffix(".tmp"); tmp.write_text(json.dumps(data)); os.replace(tmp, path)   # atomic, the app never reads half a file


class Writer:
    """Writes each part's legacy file only when its content changed (the app keys off mtime), plus stream.json."""
    def __init__(self, root=ROOT):
        self.root, self.last, self.state, self.beat = root, {}, {}, 0.0

    def write(self, parts, now):
        changed = []
        for k, d in parts.items():
            key = {x: y for x, y in d.items() if x not in ("t", "tick")}   # a new timestamp or tick alone is not a change
            if self.last.get(k) == key: continue
            self.last[k] = key; self.state[k] = d; changed.append(k)
            write_json(self.root / FILES[k], d)
        if changed or now - self.beat >= 1.0:   # at least once a second, so livemap.py knows stream.py is alive
            self.beat = now; write_json(self.root / STREAM.name, {"t": now, **self.state})
        return changed


def watching():
    try: return time.time() - WATCH.stat().st_mtime < 8
    except OSError: return False


def runner_alive(gone=[0.0]):
    """runner.pid vanishes for a few seconds during a restart; only quit if it stays gone for a minute."""
    if (ROOT / "runner.pid").exists(): gone[0] = 0.0; return True
    gone[0] = gone[0] or time.time()
    return time.time() - gone[0] < 60


def connect():
    import factorio_rcon as f
    return f.RCONClient("127.0.0.1", 27000, "factorio", timeout=5)


def frame_once(rcon, parts, mags, fired):
    try: area = view_area(json.loads(FRAME.read_text()))
    except Exception: area = None
    now = time.time()
    return parse(rcon.send_command(build_lua(parts, area)), now, mags, fired)


def main():
    if "--once" in sys.argv:
        print(json.dumps(frame_once(connect(), list(LUA), {}, {}), indent=1)); return
    rcon, last, mags, fired, w = None, {}, {}, {}, Writer()
    while runner_alive():
        if not watching():
            time.sleep(1.0); continue
        now = time.time(); parts = due(now, last)
        if parts:
            try:
                rcon = rcon or connect()
                w.write(frame_once(rcon, parts, mags, fired), now)
                for k in parts: last[k] = now
            except Exception as e:   # server restarting: reconnect next lap
                print("stream:", e, file=sys.stderr); rcon = None; time.sleep(1.0); continue
        time.sleep(max(0.02, min(last.get(k, 0.0) + RATES[k] for k in RATES) - time.time()))


if __name__ == "__main__":
    main()
