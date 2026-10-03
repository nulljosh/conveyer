#!/usr/bin/env python3
"""Draws eval/benchmarks.svg from eval/history.jsonl: skill name, params and valid JSON per eval run.
Run any time, it is cheap: python3 scripts/bench_graph.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = [json.loads(l) for l in open(ROOT / "eval" / "history.jsonl") if l.strip()] if (ROOT / "eval" / "history.jsonl").exists() else []
W, H, L, B, T = 640, 300, 50, 50, 40
lines = [("skill_name", "Skill name", "#1a1a1a"), ("params_exact", "Exact params", "#0a7d3c"), ("valid_json", "Valid JSON", "#999999")]
out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="-apple-system,Helvetica,sans-serif" font-size="11">',
       f'<rect width="{W}" height="{H}" fill="white"/><text x="{L}" y="24" font-size="14" font-weight="600">Conveyer picker, held-out eval</text>']
for i in range(6):
    y = T + (H - T - B) * i / 5
    out.append(f'<line x1="{L}" x2="{W-20}" y1="{y}" y2="{y}" stroke="#eee"/><text x="{L-8}" y="{y+4}" text-anchor="end" fill="#888">{100-20*i}%</text>')
n = max(len(rows), 2)
def pt(i, v): return L + (W - L - 20) * i / (n - 1), T + (H - T - B) * (1 - v)
for k, name, col in lines:
    pts = " ".join("%.1f,%.1f" % pt(i, r[k]) for i, r in enumerate(rows))
    if rows: out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2"/>')
    for i, r in enumerate(rows):
        x, y = pt(i, r[k]); out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{col}"/>')
for i, r in enumerate(rows):
    out.append(f'<text x="{pt(i,0)[0]:.1f}" y="{H-B+16}" text-anchor="middle" fill="#888">{r.get("label","")}</text><text x="{pt(i,0)[0]:.1f}" y="{H-B+30}" text-anchor="middle" fill="#bbb">{r.get("time","")}</text>')
for j, (k, name, col) in enumerate(lines):
    out.append(f'<rect x="{L+j*120}" y="{H-14}" width="10" height="10" fill="{col}"/><text x="{L+j*120+16}" y="{H-5}">{name}</text>')
out.append("</svg>")
(ROOT / "eval" / "benchmarks.svg").write_text("\n".join(out))
print(f"{len(rows)} runs -> eval/benchmarks.svg")
