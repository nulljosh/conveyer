#!/usr/bin/env python3
"""Record a milestone as a GIF. Usage: milestone.py NAME reset | frame | finish
Each frame is a real render (sprites + ground), cropped to 40x40 tiles around the player.
Needs the runner as the only step.sh caller, so it refuses to run while keepbusy.sh is up."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
import terrain

ROOT = Path(__file__).resolve().parent.parent
name, cmd = sys.argv[1], sys.argv[2]
D = ROOT / "shots" / "milestones" / name
D.mkdir(parents=True, exist_ok=True)
frames = lambda: sorted(D.glob("[0-9][0-9][0-9].png"))

if cmd == "reset":
    for f in frames(): f.unlink()
elif cmd == "frame":
    if subprocess.run(["pgrep", "-f", "scripts/keepbusy.sh"], capture_output=True).stdout.strip():
        sys.exit("keepbusy.sh is running: stop it first, two step.sh callers shift results")
    r = subprocess.run([str(ROOT / "step.sh"), '{"screenshot":true,"radius":30}'], capture_output=True, text=True, cwd=ROOT)
    if r.returncode or not json.loads(r.stdout).get("ok"): sys.exit(f"screenshot failed: {r.stdout or r.stderr}")
    tmp = Path(tempfile.mkdtemp()) / "p.png"
    shutil.copy(ROOT / "preview.png", tmp)  # grab it before the runner's idle capture overwrites it
    out = D / f"{(int(frames()[-1].stem) + 1 if frames() else 0):03d}.png"
    terrain.SRC, terrain.OUT = tmp, out
    import factorio_rcon
    if not terrain.refresh(factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio")) or not out.exists():
        sys.exit("terrain paint failed, no frame written")
    Image.open(out).crop((192, 192, 832, 832)).save(out)  # 40 tiles at 16 px, player centered
    print(out)
elif cmd == "finish":
    fs = frames()
    if not fs: sys.exit("no frames")
    ims = [Image.open(f).convert("RGB").resize((560, 560), Image.LANCZOS).quantize(128) for f in fs]
    gif = D.parent / f"{name}.gif"
    ims[0].save(gif, save_all=True, append_images=ims[1:], duration=[900] * (len(ims) - 1) + [2500], loop=0, optimize=True)
    print(gif, f"{gif.stat().st_size // 1024} KB")
