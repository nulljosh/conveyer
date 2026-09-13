#!/usr/bin/env python3
"""
Generates progress.svg: a sparkline of real entities successfully placed per run,
from the JSONL transcripts in runs/. Real data only — no fabricated trend.
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "runs")


def placements_per_run():
    files = sorted(glob.glob(os.path.join(RUNS, "*.jsonl")), key=os.path.getmtime)
    counts = []
    for f in files:
        lines = [json.loads(l) for l in open(f) if l.strip()]
        if not lines:
            continue
        counts.append(sum(l["observation"].lower().count("placed") for l in lines))
    return counts


def render_svg(counts, path):
    w, h, pad = 480, 120, 16
    if not counts:
        counts = [0]
    max_v = max(counts) or 1
    n = len(counts)
    step = (w - 2 * pad) / max(n - 1, 1)
    points = [
        (pad + i * step, h - pad - (c / max_v) * (h - 2 * pad))
        for i, c in enumerate(counts)
    ]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#3d7ab5"/>' for x, y in points
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<rect width="{w}" height="{h}" fill="none"/>
<polyline points="{poly}" fill="none" stroke="#3d7ab5" stroke-width="2"/>
{dots}
<text x="{pad}" y="{h - 2}" font-family="ui-monospace,monospace" font-size="10" fill="#8a8d99">entities placed per run ({n} runs)</text>
</svg>"""
    with open(path, "w") as f:
        f.write(svg)


if __name__ == "__main__":
    counts = placements_per_run()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "progress.svg")
    render_svg(counts, out)
    print(f"wrote {out}: {counts}")
