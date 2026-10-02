#!/usr/bin/env python3
"""Turns runs/*.jsonl into chat-format train/valid files for LoRA fine-tuning (mlx_lm lora, same recipe as Turing's hands-adapter).
One example per successful skill call: the prompt is the last observation, the answer is {"skill", "params"}. Failed calls are dropped.
Usage: export_training.py [--valid 0.1]"""
import argparse, glob, json, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYS = "You play Factorio. Pick one skill and its parameters as JSON. Never write code."
ap = argparse.ArgumentParser(); ap.add_argument("--valid", type=float, default=0.1); a = ap.parse_args()
rows = []
for f in sorted(glob.glob(str(ROOT / "runs" / "*.jsonl"))):
    last = "Start of run."
    for line in open(f):
        if not line.strip(): continue
        r = json.loads(line)
        if "SKILL_OK" in str(r.get("observation", "")) and r.get("skill"):
            try: params = json.loads(json.dumps(eval(str(r["params"])))) if isinstance(r["params"], str) else r["params"]
            except Exception: params = {}
            rows.append({"messages": [{"role": "system", "content": SYS}, {"role": "user", "content": last[:1500]},
                                      {"role": "assistant", "content": json.dumps({"skill": r["skill"], "params": params})}]})
        last = str(r.get("observation", ""))
random.Random(7).shuffle(rows)
n = max(1, int(len(rows) * a.valid))
(ROOT / "data").mkdir(exist_ok=True)
for name, part in (("valid", rows[:n]), ("train", rows[n:])):
    (ROOT / "data" / f"{name}.jsonl").write_text("\n".join(json.dumps(x) for x in part) + "\n")
print(f"{len(rows) - n} train, {n} valid -> data/")
