#!/usr/bin/env python3
"""Draws the Conveyer icon: a gear riding a belt. Writes the Icon Composer bundle (icon/Conveyer.icon),
a flat vector icon.svg, and renders PNGs with Apple's ictool. Picture only, no text."""
import json, math, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "icon" / "Conveyer.icon"
S = 4  # supersample
CREAM, CLAY, CLAY_LIGHT = (245, 240, 228), (179, 70, 31), (226, 116, 66)

def gear_points(cx, cy, root, tip, teeth=12, n=1440):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        d = abs((a * teeth / (2 * math.pi)) % 1.0 - 0.5)   # 0 at a tooth centre, 0.5 mid valley
        r = tip if d < 0.2 else root + (tip - root) * (0.32 - d) / 0.12 if d < 0.32 else root
        pts.append((cx + r * math.cos(a - math.pi / 2), cy + r * math.sin(a - math.pi / 2)))
    return pts

GEAR = dict(cx=512, cy=402, root=205, tip=256, hole=80)
BELT = dict(x0=118, x1=906, y0=640, y1=800, r=80)

def layer_gear():
    im = Image.new("RGBA", (1024 * S, 1024 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon([(x * S, y * S) for x, y in gear_points(GEAR["cx"], GEAR["cy"], GEAR["root"], GEAR["tip"])], fill=CREAM)
    h = GEAR["hole"] * S; cx, cy = GEAR["cx"] * S, GEAR["cy"] * S
    d.ellipse([cx - h, cy - h, cx + h, cy + h], fill=(0, 0, 0, 0))
    return im.resize((1024, 1024), Image.LANCZOS)

def chevrons():
    out = []
    for i in range(5):
        x = BELT["x0"] + 70 + i * 135; cy = (BELT["y0"] + BELT["y1"]) / 2
        out.append([(x, cy - 46), (x + 46, cy), (x, cy + 46), (x + 22, cy + 46), (x + 68, cy), (x + 22, cy - 46)])
    return out

def layer_belt():
    im = Image.new("RGBA", (1024 * S, 1024 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([BELT["x0"] * S, BELT["y0"] * S, BELT["x1"] * S, BELT["y1"] * S], BELT["r"] * S, fill=CLAY)
    for c in chevrons():
        d.polygon([(x * S, y * S) for x, y in c], fill=CLAY_LIGHT)
    return im.resize((1024, 1024), Image.LANCZOS)

(BUNDLE / "Assets").mkdir(parents=True, exist_ok=True)
layer_gear().save(BUNDLE / "Assets" / "gear.png"); layer_belt().save(BUNDLE / "Assets" / "belt.png")
(BUNDLE / "icon.json").write_text(json.dumps({
    "fill": {"linear-gradient": ["extended-srgb:0.14,0.12,0.10,1.0", "extended-srgb:0.03,0.03,0.02,1.0"],
             "orientation": {"start": {"x": 0.5, "y": 0}, "stop": {"x": 0.5, "y": 1}}},
    "groups": [
        {"layers": [{"glass": True, "image-name": "gear.png", "name": "Gear"}], "lighting": "individual", "name": "Gear",
         "shadow": {"kind": "neutral", "opacity": 0.5}, "specular": True, "translucency": {"enabled": True, "value": 0.2}},
        {"layers": [{"glass": True, "image-name": "belt.png", "name": "Belt"}], "lighting": "individual", "name": "Belt",
         "shadow": {"kind": "layer-color", "opacity": 0.5}, "specular": True, "translucency": {"enabled": True, "value": 0.25}}],
    "supported-platforms": {"squares": "shared"}}, indent=2))

# flat vector for the web and README
pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in gear_points(GEAR["cx"], GEAR["cy"], GEAR["root"], GEAR["tip"]))
chev = "".join(f'<polygon points="{" ".join(f"{x},{y}" for x, y in c)}" fill="#e27442"/>' for c in chevrons())
(ROOT / "icon.svg").write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="200" height="200">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#241f1a"/><stop offset="1" stop-color="#080705"/></linearGradient>
<mask id="m"><rect width="1024" height="1024" fill="#fff"/><circle cx="{GEAR["cx"]}" cy="{GEAR["cy"]}" r="{GEAR["hole"]}" fill="#000"/></mask></defs>
<rect width="1024" height="1024" rx="230" fill="url(#g)"/>
<rect x="{BELT["x0"]}" y="{BELT["y0"]}" width="{BELT["x1"] - BELT["x0"]}" height="{BELT["y1"] - BELT["y0"]}" rx="{BELT["r"]}" fill="#b3461f"/>{chev}
<polygon points="{pts}" fill="#f5f0e4" mask="url(#m)"/>
</svg>
''')
ict = "/Applications/Icon Composer.app/Contents/Executables/ictool"
for plat, out in (("iOS", "icon-1024.png"),):
    subprocess.run([ict, str(BUNDLE), "--export-image", "--output-file", str(ROOT / "icon" / out), "--platform", plat,
                    "--rendition", "Default", "--width", "1024", "--height", "1024", "--scale", "1"], check=False)
print("icon built")
import shutil
shutil.copy(ROOT / "icon.svg", ROOT / "web" / "icon.svg")
subprocess.run(["magick", str(ROOT / "icon" / "icon-1024.png"), "-resize", "512x512", str(ROOT / "web" / "icon.png")], check=False)
