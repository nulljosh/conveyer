#!/usr/bin/env python3
"""docs/BENCHMARKS.md from real data only: release times from git tags, techs and entities from docs/progress.jsonl, live counts from the files the
loop already writes. Run by the pre-commit hook, so it is current at every commit. Standard library only."""
import json, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
rows = [json.loads(l) for l in (ROOT / "docs" / "progress.jsonl").read_text().splitlines() if l.strip()] if (ROOT / "docs" / "progress.jsonl").exists() else []
tags = [t for t in git("tag", "--sort=creatordate").splitlines() if t.startswith("v")]
start = rows[0]["t"] if rows else 0   # the real-save run began at the first benchmark row
tiles = json.loads((ROOT / ".world" / "tiles.json").read_text()) if (ROOT / ".world" / "tiles.json").exists() else []
res = json.loads((ROOT / "research.json").read_text()) if (ROOT / "research.json").exists() else {}
out = ["# Benchmarks", "",
       "Generated from real data at every commit by `scripts/benchmarks.py`. Nothing here is typed by hand.", "",
       "## Now", "",
       f"- Version: {(ROOT / 'VERSION').read_text().strip()}",
       f"- Techs researched: {res.get('techs', '?')} (rocket silo path: {res.get('silo_done', '?')} of {res.get('silo_total', '?')})",
       f"- Assembler tiles built by the planner: {len(tiles) if isinstance(tiles, list) else '?'}",
       f"- Entities on the map: {rows[-1].get('entities', '?') if rows else '?'}",
       f"- Labs working: {res.get('labs_working', '?')} of {res.get('labs', '?')}", "",
       "## Releases", "", "| Tag | When | Hours into the real-save run |", "|---|---|---|"]
for t in tags:
    ts = int(git("log", "-1", "--format=%ct", t) or 0)
    out.append(f"| {t} | {time.strftime('%b %-d %H:%M', time.localtime(ts))} | {(ts - start) / 3600:.1f} |")
if rows:
    out += ["", "## Research and building, per commit", "", "| When | Version | Techs | Entities | Tiles |", "|---|---|---|---|---|"]
    for r in rows[-12:]:
        out.append(f"| {time.strftime('%b %-d %H:%M', time.localtime(r['t']))} | {r.get('version', '')} | {r.get('techs', '')} | {r.get('entities', '')} | {r.get('tiles', '')} |")
out += ["", "![techs and entities over time](../progress.svg)", ""]
(ROOT / "docs" / "BENCHMARKS.md").write_text("\n".join(out))
print("wrote docs/BENCHMARKS.md")
