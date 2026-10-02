#!/usr/bin/env python3
"""Paints real ground (grass, dirt, sand, water) under preview.png and writes preview_map.png.
FLE's renderer draws sprites on a flat dark grid. The view is +-32 tiles around the player at 16 px a tile,
so tiles come from RCON (67x67 around the player, two calls to stay under RCON's 4 KB reply cap)."""
from pathlib import Path
import numpy as np
from PIL import Image
import factorio_rcon

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "preview.png", ROOT / "preview_map.png"
N, PX = 67, 16  # tiles per side queried, pixels per tile
COLORS = {  # muted so sprites stay readable
    "g": (62, 82, 44), "d": (88, 70, 48), "s": (128, 108, 70), "w": (34, 66, 96),
    "W": (24, 48, 78), "c": (100, 95, 86), "o": (70, 70, 60),
}
LUA = ("/silent-command local s=game.surfaces[1] local ch=s.find_entities_filtered{type='character'}[1] local p=ch.position "
       "local sx=math.floor(p.x)-33 local sy=math.floor(p.y)-33 local out={} "
       "for r=%d,%d do local row={} for c=0,66 do local n=s.get_tile(sx+c,sy+r).name "
       "local k='o' if n:find('deepwater') then k='W' elseif n:find('water') then k='w' elseif n:find('grass') then k='g' "
       "elseif n:find('sand') then k='s' elseif n:find('dirt') or n:find('desert') then k='d' elseif n:find('concrete') or n:find('path') or n:find('refined') then k='c' end "
       "row[#row+1]=k end out[#out+1]=table.concat(row) end rcon.print(p.x..','..p.y..'|'..table.concat(out,','))")

def refresh(rcon) -> bool:
    if not SRC.exists() or (OUT.exists() and OUT.stat().st_mtime >= SRC.stat().st_mtime):
        return False
    a = rcon.send_command(LUA % (0, 33)); b = rcon.send_command(LUA % (34, 66))
    (px, py), rows = (map(float, a.split("|")[0].split(",")), a.split("|")[1].split(",") + b.split("|")[1].split(","))
    sx, sy = int(np.floor(px)) - 33, int(np.floor(py)) - 33
    img = np.zeros((1024, 1024, 3), np.uint8)
    for r, row in enumerate(rows):
        for c, k in enumerate(row):
            x0 = round(512 + (sx + c - px) * PX); y0 = round(512 + (sy + r - py) * PX)
            img[max(y0, 0):max(y0 + PX, 0), max(x0, 0):max(x0 + PX, 0)] = COLORS[k]
    try:
        fg = np.array(Image.open(SRC).convert("RGB"))
    except Exception:  # runner mid-write, try next time
        return False
    spread = fg.max(axis=2).astype(int) - fg.min(axis=2)
    bg = (fg.max(axis=2) < 75) & (spread < 10)  # the flat dark grid
    img[~bg] = fg[~bg]
    Image.fromarray(img).save(OUT)
    return True

if __name__ == "__main__":
    print(refresh(factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio")))
