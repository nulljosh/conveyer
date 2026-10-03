#!/usr/bin/env python3
"""minimap.py: a small whole-base overview for the live window. One RCON call bins player entities, pumpjacks and enemy nests into 16-tile chunks,
PIL paints them (light = our base, orange = oil, red = nests) into minimap.png, and minimap.json records where it sits in tile coordinates so the
Swift app can drop the player dot on it live. Loops every 30 s and stops when runner.pid is gone; `minimap.py --once` paints one frame.
ponytail: chunk-level (16 tiles) on purpose, cheap enough to run beside the 10x server; per-entity detail is the main map's job."""
import json, os, sys, time
from pathlib import Path
from PIL import Image
import factorio_rcon as f

ROOT = Path(__file__).resolve().parent.parent
CH = 16   # tiles per chunk cell
LUA = """/silent-command local s=game.surfaces[1] local b={p={},o={},e={},w={}}
local function add(t,x,y) local k=math.floor(x/16)..','..math.floor(y/16) t[k]=(t[k] or 0)+1 end
local skip={['electric-pole']=1,['pipe']=1,['pipe-to-ground']=1,['character']=1,['transport-belt']=1,['underground-belt']=1}
for _,e in pairs(s.find_entities_filtered{force='player'}) do if e.name=='pumpjack' then add(b.o,e.position.x,e.position.y) elseif not skip[e.type] then add(b.p,e.position.x,e.position.y) end end
for _,e in pairs(s.find_entities_filtered{force='enemy',type={'unit-spawner','turret'}}) do if e.type=='unit-spawner' then add(b.e,e.position.x,e.position.y) else add(b.w,e.position.x,e.position.y) end end
local out={} for kind,t in pairs(b) do for k,n in pairs(t) do out[#out+1]=kind..','..k..','..n end end
rcon.print(table.concat(out,';'))"""


def cells(raw):
    out = {"p": {}, "o": {}, "e": {}, "w": {}}
    for row in raw.strip().split(";"):
        try:
            kind, x, y, n = row.split(",")
            out[kind][(int(x), int(y))] = int(n)
        except ValueError:
            pass   # a truncated tail row is fine, the next frame repaints
    return out


TERRAIN_LUA = """/silent-command local s=game.surfaces[1] local rows={} for y=%d,%d do local row='' for x=%d,%d do local t=s.get_tile(x*16+8,y*16+8).name local c='o'
if t:find('deepwater') then c='W' elseif t:find('water') then c='w' elseif t:find('grass') then c='g' elseif t:find('sand') then c='s' elseif t:find('dirt') then c='d' elseif t:find('desert') then c='r' end row=row..c end rows[#rows+1]=row end rcon.print(table.concat(rows,'/'))"""
TERRAIN_RGB = {"g": (58, 76, 48), "d": (92, 68, 44), "s": (128, 106, 70), "r": (122, 86, 56), "w": (28, 52, 84), "W": (22, 42, 70), "o": (70, 64, 56)}
_terrain = {}   # bounds -> rows: the ground does not change, ask once per bounds

def terrain(r, x0, x1, y0, y1):
    key = (x0, x1, y0, y1)
    if key not in _terrain:
        raw = r.send_command(" ".join((TERRAIN_LUA % (y0, y1, x0, x1)).split("\n"))).strip()
        _terrain[key] = raw.split("/")
    return _terrain[key]


def paint(c, r=None):
    base = list(c["p"]) + list(c["o"])
    if not base:
        return
    pad = 10   # chunks of surroundings so nests near the base show; poles and pipes are left out so the base reads as blobs, not a skeleton
    x0, x1 = min(x for x, _ in base) - pad, max(x for x, _ in base) + pad
    y0, y1 = min(y for _, y in base) - pad, max(y for _, y in base) + pad
    w, h = x1 - x0 + 1, y1 - y0 + 1
    s = max(2, min(8, 320 // max(w, h)))   # pixels per chunk
    im = Image.new("RGB", (w * s, h * s), (24, 26, 30))
    px = im.load()
    rows = terrain(r, x0, x1, y0, y1) if r else []
    for ry, row in enumerate(rows[:h]):   # ground first, so the base, oil and nests sit on real terrain, not black
        for rx, ch in enumerate(row[:w]):
            col = TERRAIN_RGB.get(ch, (70, 64, 56))
            for dx in range(s):
                for dy in range(s): px[rx * s + dx, ry * s + dy] = col

    def fill(cx, cy, col):
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            for dx in range(s):
                for dy in range(s):
                    px[(cx - x0) * s + dx, (cy - y0) * s + dy] = col
    for (cx, cy), n in c["w"].items(): fill(cx, cy, (110, 40, 40))
    for (cx, cy), n in c["e"].items(): fill(cx, cy, (210, 55, 55))
    for (cx, cy), n in c["p"].items(): v = min(255, 120 + n * 8); fill(cx, cy, (v, v, v))
    for (cx, cy), n in c["o"].items(): fill(cx, cy, (240, 150, 40))
    tmp = ROOT / "minimap.tmp.png"
    im.save(tmp)
    os.replace(tmp, ROOT / "minimap.png")
    meta = {"x0": x0 * CH, "y0": y0 * CH, "w": w * CH, "h": h * CH}   # tile coords of the top-left corner and the covered span
    (ROOT / "minimap.tmp.json").write_text(json.dumps(meta))
    os.replace(ROOT / "minimap.tmp.json", ROOT / "minimap.json")


def once():
    r = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=30)
    paint(cells(r.send_command(" ".join(LUA.split("\n")))), r)


if __name__ == "__main__":
    if "--once" in sys.argv:
        once(); sys.exit()
    pid = ROOT / "runner.pid"
    while pid.exists():
        try:
            once()
        except Exception as e:   # server restarting: try again next lap
            print("minimap:", e, file=sys.stderr)
        time.sleep(30)
