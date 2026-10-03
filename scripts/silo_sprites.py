#!/usr/bin/env python3
"""silo_sprites.py: builds the rocket silo and rocket pictures the live window draws, from the game's own art in the Steam install (copied at run time into
assets/silo/, never committed). Layer files, sizes and offsets come straight from base/prototypes/entity/entities.lua (rocket-silo and rocket-silo-rocket):
every sprite is scale 0.5 and by_pixel(x, y) shifts by x/32 tiles, so at 32 px per tile the shift in output pixels is just x, y. Outputs, all centred on the
silo centre in a 704 px square canvas (22 tiles): silo_closed.png, silo_open_back.png and silo_open_front.png (doors slid apart; the rocket goes between the two), and rocket.png (the pod with its glow,
308 x 752 source at half size, its centre sits 65 px below the silo centre). `silo_sprites.py` builds them; the app draws them at f.ppt * zoom.
ponytail: static frames only (no arms or turbine animation); the doors and the rocket's rise are moved by the app."""
import json
from pathlib import Path
from PIL import Image, ImageChops

STEAM = Path.home() / "Library/Application Support/Steam/steamapps/common/Factorio/factorio.app/Contents/data/base/graphics/entity"
OUT = Path(__file__).resolve().parent.parent / "assets" / "silo"
OUT.mkdir(parents=True, exist_ok=True)
C = 704


def load(name, a=0.5):
    im = Image.open(STEAM / name).convert("RGBA")
    return im.resize((round(im.width * a), round(im.height * a)), Image.LANCZOS)


def put(canvas, im, sx, sy, alpha=1.0, additive=False):
    x, y = round(C / 2 + sx - im.width / 2), round(C / 2 + sy - im.height / 2)
    if alpha < 1: im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    if additive:   # glow layers add light instead of covering
        box = canvas.crop((x, y, x + im.width, y + im.height)); add = ImageChops.add(box.convert("RGB"), im.convert("RGB"))
        add = Image.merge("RGBA", (*add.split(), box.getchannel("A"))); canvas.paste(Image.composite(add, box, im.getchannel("A")), (x, y))
    else:
        canvas.alpha_composite(im, (max(x, 0), max(y, 0))) if x >= 0 and y >= 0 else canvas.paste(im, (x, y), im)


def silo(open_doors, part="all"):
    """part: back (shadow, hole, back door), front (front door, frame, front lip) or all. The rocket is drawn between back and front."""
    cv = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    ox, oy = (40.0, -17.0) if open_doors else (0, 0)   # doors slide about 70 percent of the game's offset so they stay under the frame
    if part in ("all", "back"):
        put(cv, load("rocket-silo/00-rocket-silo-shadow.png"), 7, 2, alpha=0.6)
        put(cv, load("rocket-silo/01-rocket-silo-hole.png"), -5, 16)
        put(cv, load("rocket-silo/04-door-back.png"), 37 + ox, 12 + oy)
    if part in ("all", "front"):
        put(cv, load("rocket-silo/05-door-front.png"), -28 - ox, 33 - oy)
        put(cv, load("rocket-silo/06-rocket-silo.png"), 3, -1)
        put(cv, load("rocket-silo/14-rocket-silo-front.png"), -1, 78)
    return cv


silo(False).save(OUT / "silo_closed.png")
silo(True, "back").save(OUT / "silo_open_back.png")
silo(True, "front").save(OUT / "silo_open_front.png")
pod = load("rocket-silo/rocket-static-pod.png"); glow = load("rocket-silo/rocket-static-emission.png")
rk = Image.new("RGBA", pod.size, (0, 0, 0, 0)); rk.alpha_composite(pod)
box = rk.convert("RGB"); add = ImageChops.add(box, glow.convert("RGB").resize(pod.size)); rk = Image.merge("RGBA", (*add.split(), pod.getchannel("A")))
rk.save(OUT / "rocket.png")
(OUT / "meta.json").write_text(json.dumps({"canvas_px": C, "px_per_tile": 32, "rocket_w": rk.width, "rocket_h": rk.height, "rocket_center_y_px": 65}))
print("wrote", [p.name for p in OUT.iterdir()])
