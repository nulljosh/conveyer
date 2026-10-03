#!/usr/bin/env python3
"""progress.svg: techs researched and entities built over time, from docs/progress.jsonl (real rows only, no invented trend).
Every run appends one row from the live state (research.json, .world/tiles.json, the newest benchmark row, VERSION) when it differs from the last,
and redraws. The git pre-commit hook (.githooks/pre-commit) runs this, so the graph moves with every commit. Standard library only."""
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "docs" / "progress.jsonl", ROOT / "progress.svg"

def read_json(p, default):
    try: return json.loads(Path(p).read_text())
    except Exception: return default

def rows():
    return [json.loads(l) for l in DATA.read_text().splitlines() if l.strip()] if DATA.exists() else []

def backfill():
    """First run only: seed the history from the benchmark log (real techs and entities every 5 minutes since the real save started)."""
    bench = ROOT / "shots" / "bench.jsonl"
    if DATA.exists() or not bench.exists(): return
    out = []
    for l in bench.read_text().splitlines():
        try: b = json.loads(l)
        except Exception: continue
        if b.get("entities", -1) > 0 and b.get("techs", -1) > 0:
            out.append({"t": time.mktime(time.strptime(b["t"], "%Y%m%d-%H%M%S")), "techs": b["techs"], "entities": b["entities"]})
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text("".join(json.dumps(r) + "\n" for r in out[::6]))  # one row every 30 minutes keeps the file small

def current():
    r = read_json(ROOT / "research.json", {})
    bench = [json.loads(l) for l in (ROOT / "shots" / "bench.jsonl").read_text().splitlines()[-3:] if l.strip()] if (ROOT / "shots" / "bench.jsonl").exists() else []
    b = next((x for x in reversed(bench) if x.get("entities", -1) > 0), {})
    tiles = read_json(ROOT / ".world" / "tiles.json", [])
    return {"t": round(time.time()), "version": (ROOT / "VERSION").read_text().strip(), "techs": r.get("techs") or b.get("techs"),
            "entities": b.get("entities"), "tiles": len(tiles) if isinstance(tiles, list) else None}

def badge():
    r = ROOT / "README.md"
    if r.exists():
        import re
        v = (ROOT / "VERSION").read_text().strip()
        r.write_text(re.sub(r"version-v[\d.]+-blue", f"version-v{v}-blue", r.read_text(), 1))

def append():
    backfill()
    now, rs = current(), rows()
    if now["techs"] is None or now["entities"] is None: return
    key = lambda x: (x.get("version"), x.get("techs"), x.get("entities"), x.get("tiles"))
    if not rs or key(rs[-1]) != key(now):
        with open(DATA, "a") as f: f.write(json.dumps(now) + "\n")

def render():
    rs = rows()
    W, H, L, R, T, B = 720, 220, 46, 46, 28, 36
    if len(rs) < 2:
        OUT.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"><text x="20" y="40" font-family="-apple-system,Helvetica,sans-serif" font-size="13" fill="#8a8d99">collecting data</text></svg>'); return
    t0, t1 = rs[0]["t"], rs[-1]["t"]
    X = lambda t: L + (t - t0) / max(t1 - t0, 1) * (W - L - R)
    mt = max(r["techs"] for r in rs) or 1
    me = max(r["entities"] for r in rs) or 1
    Yt = lambda v: H - B - v / mt * (H - T - B)
    Ye = lambda v: H - B - v / me * (H - T - B)
    line = lambda key, Y: " ".join(f"{X(r['t']):.1f},{Y(r[key]):.1f}" for r in rs if r.get(key) is not None)
    marks, last = "", None
    for r in rs:
        v = r.get("version")
        if v and v != last:
            x = X(r["t"]); marks += f'<line x1="{x:.1f}" y1="{T}" x2="{x:.1f}" y2="{H-B}" stroke="#c9ccd6" stroke-dasharray="2 3"/><text x="{x:.1f}" y="{T-8}" text-anchor="middle" font-size="9" fill="#8a8d99">v{v}</text>'; last = v
    grid = "".join(f'<line x1="{L}" y1="{H-B-i*(H-T-B)/4:.1f}" x2="{W-R}" y2="{H-B-i*(H-T-B)/4:.1f}" stroke="#ececf1"/>' for i in range(5))
    when = lambda t: time.strftime("%b %-d %H:%M", time.localtime(t))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="-apple-system,Helvetica,Arial,sans-serif">
<rect width="{W}" height="{H}" fill="#ffffff" rx="10"/>
{grid}{marks}
<polyline points="{line('entities', Ye)}" fill="none" stroke="#d98a2b" stroke-width="2" stroke-linejoin="round"/>
<polyline points="{line('techs', Yt)}" fill="none" stroke="#3d7ab5" stroke-width="2.4" stroke-linejoin="round"/>
<text x="{L-8}" y="{T+4}" text-anchor="end" font-size="10" fill="#3d7ab5">{mt}</text><text x="{L-8}" y="{H-B+4}" text-anchor="end" font-size="10" fill="#3d7ab5">0</text>
<text x="{W-R+8}" y="{T+4}" font-size="10" fill="#d98a2b">{me}</text><text x="{W-R+8}" y="{H-B+4}" font-size="10" fill="#d98a2b">0</text>
<text x="{L}" y="{H-12}" font-size="10" fill="#8a8d99">{when(t0)}</text><text x="{W-R}" y="{H-12}" text-anchor="end" font-size="10" fill="#8a8d99">{when(t1)}</text>
<text x="{W/2}" y="{H-12}" text-anchor="middle" font-size="10" fill="#8a8d99"><tspan fill="#3d7ab5">techs researched</tspan>  and  <tspan fill="#d98a2b">entities built</tspan>, one row per commit</text>
</svg>"""
    OUT.write_text(svg)

if __name__ == "__main__":
    badge(); append(); render(); print(f"wrote {OUT} from {len(rows())} rows")
