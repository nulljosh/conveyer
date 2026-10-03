#!/usr/bin/env python3
"""Turns runs/*.jsonl into chat-format train/valid files for LoRA fine-tuning (mlx_lm lora, same recipe as Turing's hands-adapter).
One example per successful skill call: the prompt is the last observation, the answer is {"skill", "params"}. Failed calls are dropped.
Usage: export_training.py [--valid 0.1]"""
import argparse, glob, json, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYS = "You play Factorio. Pick one skill and its parameters as JSON. Never write code."
ap = argparse.ArgumentParser(); ap.add_argument("--valid", type=float, default=0.1); a = ap.parse_args()
by_run = {}
for f in sorted(glob.glob(str(ROOT / "runs" / "*.jsonl"))):
    last = "Start of run."; prev = ""; hist = []  # prompt = the skill just called plus its result, so the model sees what it just did
    rows = by_run.setdefault(f, [])
    for line in open(f):
        if not line.strip(): continue
        r = json.loads(line)
        if "SKILL_OK" in str(r.get("observation", "")) and r.get("skill"):
            try: params = json.loads(json.dumps(eval(str(r["params"])))) if isinstance(r["params"], str) else r["params"]
            except Exception: params = {}
            rows.append({"messages": [{"role": "system", "content": SYS}, {"role": "user", "content": ("Recent skills: " + ", ".join(hist[-3:]) + "\n" + prev + last[:700])[:1500]},
                                      {"role": "assistant", "content": json.dumps({"skill": r["skill"], "params": params})}]})
        last = str(r.get("observation", ""))
        hist.append(str(r.get("skill")))
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
