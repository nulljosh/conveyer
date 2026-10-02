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
PX = 16  # pixels per tile
G = Path("/Users/joshua/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app/Contents/data/base/graphics/terrain")
# tile name -> (code, texture sheet). Sheets keep 64 px 1x1 variants along the top row.
TILES = {"grass-1": "a", "grass-2": "b", "grass-3": "e", "grass-4": "f", "dry-dirt": "o", "landfill": "l",
         **{f"dirt-{i}": str(i) for i in range(1, 8)}, "sand-1": "x", "sand-2": "y", "sand-3": "z",
         **{f"red-desert-{i}": "pqrt"[i] for i in range(4)}, "water": "w", "deepwater": "W",
         "water-green": "w", "deepwater-green": "W", "water-shallow": "w", "water-mud": "w",
         "stone-path": "s", "concrete": "c", "hazard-concrete-left": "c", "hazard-concrete-right": "c",
         "refined-concrete": "c", "refined-hazard-concrete-left": "c", "refined-hazard-concrete-right": "c"}
SHEETS = {c: n + ".png" for n, c in TILES.items() if "-" in n and n.split("-")[0] in ("grass", "dirt", "sand", "red")}
SHEETS.update({"o": "dry-dirt.png", "l": "landfill.png", "w": "water/water1.png", "W": "water/water1.png",
               "s": "stone-path/stone-path-1.png", "c": "concrete/concrete.png"})
_cache = {}
def variants(code):
    """Opaque variants of a sheet as (span, tiles): span 4 = the sheet's 4x4 big patches (256 px), else 1x1 (64 px)."""
    if code not in _cache:
        try:
            sheet = Image.open(G / SHEETS.get(code, "dry-dirt.png")).convert("RGBA")
            span = 4 if sheet.height >= 512 else 1
            size, y = 64 * span, sheet.height - 64 * span
            out = []
            for i in range(sheet.width // size):
                t = sheet.crop((i * size, y, i * size + size, y + size))
                if np.array(t)[..., 3].min() > 200:  # skip transparent padding and edge pieces
                    out.append(np.array(t.convert("RGB").resize((PX * span, PX * span), Image.LANCZOS)))
            _cache[code] = (span, out or [np.full((PX, PX, 3), (88, 70, 48), np.uint8)])
            if not out: _cache[code] = (1, _cache[code][1])
        except Exception:  # no local game install: flat muted color
            _cache[code] = (1, [np.full((PX, PX, 3), (88, 70, 48), np.uint8)])
    return _cache[code]
_LUA_MAP = "local m={" + ",".join(f"['{n}']='{c}'" for n, c in TILES.items()) + "} "
LUA = ("/silent-command " + _LUA_MAP + "local s=game.surfaces[1] local ch=s.find_entities_filtered{type='character'}[1] local p=ch.position "
       "local sx=math.floor(p.x)-%d local sy=math.floor(p.y)-%d local out={} "
       "for r=%d,%d do local row={} for c=0,%d do row[#row+1]=m[s.get_tile(sx+c,sy+r).name] or 'o' end "
       "out[#out+1]=table.concat(row) end rcon.print(p.x..','..p.y..'|'..table.concat(out,','))")

def refresh(rcon) -> bool:
    if not SRC.exists() or (OUT.exists() and OUT.stat().st_mtime >= SRC.stat().st_mtime):
        return False
    try:
        fg = np.array(Image.open(SRC).convert("RGB"))
    except Exception:  # runner mid-write, try next time
        return False
    H, W = fg.shape[:2]                       # any size: 1024x1024 square or the wide 1920x1088 view
    nx, ny = W // PX + 3, H // PX + 3         # tiles to cover the picture plus a margin
    hx, hy = nx // 2, ny // 2
    rows, step = [], 24                       # RCON replies are capped near 4 KB, so ask for 24 rows at a time
    for r0 in range(0, ny, step):
        reply = rcon.send_command(LUA % (hx, hy, r0, min(r0 + step, ny) - 1, nx - 1))
        head, body = reply.split("|", 1); rows += body.split(",")
    px, py = map(float, head.split(","))
    sx, sy = int(np.floor(px)) - hx, int(np.floor(py)) - hy
    img = np.zeros((H, W, 3), np.uint8)
    for r, row in enumerate(rows):
        for c, k in enumerate(row):
            x0 = round(W / 2 + (sx + c - px) * PX); y0 = round(H / 2 + (sy + r - py) * PX)
            span, v = variants(k); X, Y = sx + c, sy + r
            big = v[((X // span) * 7919 + (Y // span) * 104729) % len(v)]
            ox, oy = (X % span) * PX, (Y % span) * PX
            tile = big[oy:oy + PX, ox:ox + PX]
            ys, xs = slice(max(y0, 0), min(y0 + PX, H)), slice(max(x0, 0), min(x0 + PX, W))
            if ys.start < ys.stop and xs.start < xs.stop:
                img[ys, xs] = tile[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    spread = fg.max(axis=2).astype(int) - fg.min(axis=2)
    bg = (fg.max(axis=2) < 75) & (spread < 10)  # the flat dark grid
    img[~bg] = fg[~bg]
    tmp = OUT.with_name(OUT.stem + ".tmp.png")
    Image.fromarray(img).save(tmp)
    tmp.replace(OUT)  # atomic: readers never see a half-written file
    return True

if __name__ == "__main__":
    print(refresh(factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio")))
