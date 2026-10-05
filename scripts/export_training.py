#!/usr/bin/env python3
"""Turns runs/*.jsonl into chat-format train/valid files for LoRA fine-tuning (mlx_lm lora, same recipe as Turing's hands-adapter).
One example per successful skill call: the prompt is the last observation, the answer is {"skill", "params"}. Failed calls are dropped.
Usage: export_training.py [--valid 0.1]"""
import argparse, glob, json, random, re
from pathlib import Path

ENT = re.compile(r"\b([A-Z][A-Za-z0-9]*)\s+at\s+x=(-?[\d.]+)\s*,?\s*y=(-?[\d.]+)")  # same as agent.py
PAIR = re.compile(r"^(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)$")
ROOT = Path(__file__).resolve().parent.parent
SYS = "You play Factorio. Pick one skill and its parameters as JSON. Never write code."
ap = argparse.ArgumentParser(); ap.add_argument("--valid", type=float, default=0.1); ap.add_argument("--planner", action="store_true", help="also write data/planner.jsonl from runs/planner/ (kept apart: build_tile is not a model skill yet)"); a = ap.parse_args()
by_run = {}
for f in sorted(glob.glob(str(ROOT / "runs" / "*.jsonl"))):
    last = "Start of run."; prev = ""; hist = []; known = {}  # prompt = the skill just called plus its result, so the model sees what it just did
    rows = by_run.setdefault(f, [])
    for line in open(f):
        if not line.strip(): continue
        r = json.loads(line)
        if "SKILL_OK" in str(r.get("observation", "")) and r.get("skill"):
            try: params = json.loads(json.dumps(eval(str(r["params"])))) if isinstance(r["params"], str) else r["params"]
            except Exception: params = {}
            params = {k: (f"x={m.group(1)},y={m.group(2)}" if isinstance(v, str) and (m := PAIR.match(v)) else v) for k, v in params.items()} if isinstance(params, dict) else params  # one position format: x=..,y=..
            rows.append({"messages": [{"role": "system", "content": SYS}, {"role": "user", "content": ("Recent skills: " + ", ".join(hist[-3:]) + "\nKnown: " + "; ".join(f"{k}@{v}" for k, v in list(known.items())[-4:]) + "\n" + prev + last[:700])[:1500]},
                                      {"role": "assistant", "content": json.dumps({"skill": r["skill"], "params": params})}]})
        last = str(r.get("observation", ""))
        hist.append(str(r.get("skill")))
        for pr, x, y in ENT.findall(last): known[pr] = f"x={x},y={y}"
        prev = f"Last skill: {r.get('skill')} {json.dumps(r.get('params'))}\n"
CAP = 100  # place_inserter was 35 percent of the data and won every tie
for k in by_run:
    seen = {}
    kept = []
    for x in by_run[k]:
        sk = json.loads(x["messages"][2]["content"])["skill"]; seen[sk] = seen.get(sk, 0) + 1
        if sk != "place_inserter" or random.Random(seen[sk]).random() < CAP / 288: kept.append(x)
    by_run[k] = kept
# split by run file so near-duplicate calls from one run never sit on both sides
runs = [k for k in by_run if by_run[k]]
random.Random(7).shuffle(runs)
total = sum(len(by_run[k]) for k in runs); valid_rows = []; train_rows = []
for k in runs:
    (valid_rows if len(valid_rows) < total * a.valid else train_rows).extend(by_run[k])
random.Random(7).shuffle(train_rows); random.Random(7).shuffle(valid_rows)
rows = valid_rows + train_rows; n = len(valid_rows)
(ROOT / "data").mkdir(exist_ok=True)
for name, part in (("valid", rows[:n]), ("train", rows[n:])):
    (ROOT / "data" / f"{name}.jsonl").write_text("\n".join(json.dumps(x) for x in part) + "\n")
print(f"{len(rows) - n} train, {n} valid -> data/")

if a.planner:
    # The planner is a rule-based teacher: every pass it picks the correct next tile from the stock, so each logged pick is a free correct label.
    # Kept in its own file until the model owns tile choice. Waits (nothing to build) are most of the log, so only 5 percent of them stay.
    out, rng = [], random.Random(7)
    for f in sorted(glob.glob(str(ROOT / "runs" / "planner" / "*.jsonl"))):
        for line in open(f):
            try: r = json.loads(line)
            except ValueError: continue
            if not str(r.get("observation", "")).startswith("SKILL_OK") or not r.get("skill"): continue
            if r["skill"] == "wait" and rng.random() > 0.05: continue
            user = "Tiles built: " + json.dumps(r.get("tiles", {}), sort_keys=True) + "\nStock: " + json.dumps(r.get("stock", {}), sort_keys=True) + "\nPick the next move."
            out.append({"messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user},
                                     {"role": "assistant", "content": json.dumps({"skill": r["skill"], "params": r.get("params", {})})}]})
    (ROOT / "data" / "planner.jsonl").write_text("\n".join(json.dumps(x) for x in out) + ("\n" if out else ""))
    print(f"{len(out)} planner examples -> data/planner.jsonl")
