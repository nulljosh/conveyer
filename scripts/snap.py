#!/usr/bin/env python3
"""Every N minutes: copy the textured preview_map.png (falls back to preview.png) to shots/ and append one benchmark row.
Bounded: stops when runner.pid is gone or after --hours. Usage: snap.py [--mins 5] [--hours 6]"""
import argparse, json, re, shutil, subprocess, time
from pathlib import Path
import factorio_rcon

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(); ap.add_argument("--mins", type=float, default=5); ap.add_argument("--hours", type=float, default=6)
a = ap.parse_args()
(ROOT / "shots").mkdir(exist_ok=True)
LUA = ("/silent-command local n=0 local s=0 for _,e in pairs(game.surfaces[1].find_entities_filtered{force='player'}) "
       "do if e.type~='character' then n=n+1 end end rcon.print(n)")
TECH = "/silent-command local n=0 for _,x in pairs(game.forces.player.technologies) do if x.researched then n=n+1 end end rcon.print(n)"
end = time.time() + a.hours * 3600
while time.time() < end and (ROOT / "runner.pid").exists():
    t = time.strftime("%Y%m%d-%H%M%S")
    shutil.copy(ROOT / ("preview_map.png" if (ROOT / "preview_map.png").exists() else "preview.png"), ROOT / "shots" / f"{t}.png")
    for old_f in sorted((ROOT / "shots").glob("2*.png"))[:-288]:  # keep a day of 5-minute frames, the wide frames are 2 MB each
        old_f.unlink()
    techs = -1
    try:
        c = factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio"); entities = int(c.send_command(LUA).strip())
        techs = int(c.send_command(TECH).strip())
    except Exception:
        entities = -1
    lp = Path("/tmp/conveyer_runner.log")
    log = lp.read_text(errors="ignore") if lp.exists() else ""  # the log is gone after a reboot; the benchmark must not die with it
    steps = re.findall(r"\[runner\] (\w+) -> ok=(\w+)", log)
    ok = sum(1 for _, o in steps if o == "True")
    pid = (ROOT / "runner.pid").read_text().strip()
    rss = subprocess.run(["ps", "-o", "rss=", "-p", pid], capture_output=True, text=True).stdout.strip() or "0"
    row = {"t": t, "entities": entities, "techs": techs, "steps": len(steps), "ok": ok, "rss_mb": round(int(rss) / 1024)}
    with open(ROOT / "shots" / "bench.jsonl", "a") as f: f.write(json.dumps(row) + "\n")
    print(row, flush=True)
    time.sleep(a.mins * 60)
