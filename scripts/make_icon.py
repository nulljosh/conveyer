#!/usr/bin/env python3
"""Draws the Conveyer icon: a big gear rolling out from behind a belt. Writes the Icon Composer bundle
(icon/Conveyer.icon), a flat vector icon.svg, and renders PNGs with Apple's ictool. Picture only, no text."""
import json, math, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "icon" / "Conveyer.icon"
S = 4
CREAM, CLAY, CLAY_LIGHT = (245, 240, 228), (179, 70, 31), (226, 116, 66)
GEAR = dict(cx=512, cy=464, root=250, tip=312, hole=96, teeth=12)
BELT = dict(x0=96, x1=928, y0=658, y1=872, r=107)

def gear_points(cx, cy, root, tip, teeth, n=1440):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        d = abs((a * teeth / (2 * math.pi)) % 1.0 - 0.5)   # 0 at a tooth centre, 0.5 mid valley
        r = tip if d < 0.2 else root + (tip - root) * (0.32 - d) / 0.12 if d < 0.32 else root
        pts.append((cx + r * math.cos(a - math.pi / 2), cy + r * math.sin(a - math.pi / 2)))
    return pts

def chevrons():
    cy = (BELT["y0"] + BELT["y1"]) / 2
    return [[(x, cy - 58), (x + 58, cy), (x, cy + 58), (x + 28, cy + 58), (x + 86, cy), (x + 28, cy - 58)]
            for x in (BELT["x0"] + 100 + i * 150 for i in range(5))]

def canvas(): return Image.new("RGBA", (1024 * S, 1024 * S), (0, 0, 0, 0))
def done(im): return im.resize((1024, 1024), Image.LANCZOS)

def layer_gear():
    im = canvas(); d = ImageDraw.Draw(im)
    d.polygon([(x * S, y * S) for x, y in gear_points(GEAR["cx"], GEAR["cy"], GEAR["root"], GEAR["tip"], GEAR["teeth"])], fill=CREAM)
    h, cx, cy = GEAR["hole"] * S, GEAR["cx"] * S, GEAR["cy"] * S
    d.ellipse([cx - h, cy - h, cx + h, cy + h], fill=(0, 0, 0, 0))
    return done(im)

def layer_belt():
    im = canvas(); d = ImageDraw.Draw(im)
    d.rounded_rectangle([BELT["x0"] * S, BELT["y0"] * S, BELT["x1"] * S, BELT["y1"] * S], BELT["r"] * S, fill=CLAY)
    for c in chevrons():
        d.polygon([(x * S, y * S) for x, y in c], fill=CLAY_LIGHT)
    return done(im)

(BUNDLE / "Assets").mkdir(parents=True, exist_ok=True)
for old in ("crate.png",): (BUNDLE / "Assets" / old).unlink(missing_ok=True)
layer_gear().save(BUNDLE / "Assets" / "gear.png"); layer_belt().save(BUNDLE / "Assets" / "belt.png")
group = lambda img, name, shadow, tr=0.22: {"layers": [{"glass": True, "image-name": img, "name": name}], "lighting": "individual", "name": name,
    "shadow": shadow, "specular": True, "translucency": {"enabled": tr > 0, "value": tr}}
(BUNDLE / "icon.json").write_text(json.dumps({
    "fill": {"linear-gradient": ["extended-srgb:0.14,0.12,0.10,1.0", "extended-srgb:0.03,0.03,0.02,1.0"],
             "orientation": {"start": {"x": 0.5, "y": 0}, "stop": {"x": 0.5, "y": 1}}},
    # first group is the top layer: the belt sits in front, the gear rolls out from behind it
    "groups": [group("belt.png", "Belt", {"kind": "layer-color", "opacity": 0.55}, 0), group("gear.png", "Gear", {"kind": "neutral", "opacity": 0.5})],
    "supported-platforms": {"squares": "shared"}}, indent=2))

pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in gear_points(GEAR["cx"], GEAR["cy"], GEAR["root"], GEAR["tip"], GEAR["teeth"]))
chev = "".join(f'<polygon points="{" ".join(f"{x},{y}" for x, y in c)}" fill="#e27442"/>' for c in chevrons())
(ROOT / "icon.svg").write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="200" height="200">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#241f1a"/><stop offset="1" stop-color="#080705"/></linearGradient>
<mask id="m"><rect width="1024" height="1024" fill="#fff"/><circle cx="{GEAR["cx"]}" cy="{GEAR["cy"]}" r="{GEAR["hole"]}" fill="#000"/></mask></defs>
<rect width="1024" height="1024" rx="230" fill="url(#g)"/>
<polygon points="{pts}" fill="#f5f0e4" mask="url(#m)"/>
<rect x="{BELT["x0"]}" y="{BELT["y0"]}" width="{BELT["x1"] - BELT["x0"]}" height="{BELT["y1"] - BELT["y0"]}" rx="{BELT["r"]}" fill="#b3461f"/>{chev}
</svg>
''')
ict = "/Applications/Icon Composer.app/Contents/Executables/ictool"
subprocess.run([ict, str(BUNDLE), "--export-image", "--output-file", str(ROOT / "icon" / "icon-1024.png"), "--platform", "iOS",
                "--rendition", "Default", "--width", "1024", "--height", "1024", "--scale", "1"], check=False, capture_output=True)
shutil.copy(ROOT / "icon.svg", ROOT / "web" / "icon.svg")
subprocess.run(["magick", str(ROOT / "icon" / "icon-1024.png"), "-resize", "512x512", str(ROOT / "web" / "icon.png")], check=False)
print("icon built")
