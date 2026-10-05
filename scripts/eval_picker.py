#!/usr/bin/env python3
"""Held-out eval for the skill picker: exact skill name first, then exact params.
Run with Turing's venv (it has mlx_lm):
  ~/Documents/Code/turing/.venv/bin/python scripts/eval_picker.py [--adapter PATH] [--n 90] [--out eval/last.json]
No --adapter scores the plain base model, the bar the adapter has to beat."""
import argparse, json, re, sys
from pathlib import Path

sys.path.pop(0)  # scripts/queue.py would shadow the stdlib queue module

ROOT = Path(__file__).resolve().parent.parent
BASE = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"


def parse(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        d = json.loads(m.group(0)) if m else {}
    except ValueError:
        d = {}
    return d.get("skill"), d.get("params") if isinstance(d.get("params"), dict) else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter"); ap.add_argument("--model", default=BASE)
    ap.add_argument("--data", default=str(ROOT / "data" / "valid.jsonl"))
    ap.add_argument("--n", type=int, default=0); ap.add_argument("--out"); ap.add_argument("--label", default="")
    a = ap.parse_args()
    from mlx_lm import load, generate
    model, tok = load(a.model, adapter_path=a.adapter)
    rows = [json.loads(l) for l in open(a.data) if l.strip()]
    rows = rows[: a.n] if a.n else rows
    name_ok = param_ok = valid_json = 0; misses = []
    for r in rows:
        sysm, user, gold = (m["content"] for m in r["messages"])
        prompt = tok.apply_chat_template([{"role": "system", "content": sysm}, {"role": "user", "content": user}],
                                         add_generation_prompt=True, tokenize=False)
        skill, params = parse(generate(model, tok, prompt=prompt, max_tokens=120))
        g = json.loads(gold)
        valid_json += skill is not None
        if skill != g["skill"] or params != g["params"]: misses.append({"gold": g, "got": [skill, params]})
        if skill == g["skill"]:
            name_ok += 1
            param_ok += params == g["params"]
    n = len(rows)
    res = {"n": n, "valid_json": valid_json / n, "skill_name": name_ok / n, "params_exact": param_ok / n,
           "model": a.model, "adapter": a.adapter, "label": a.label or ("base" if not a.adapter else "adapter"), "time": __import__("time").strftime("%m-%d %H:%M")}
    print(json.dumps(res))
    (ROOT / "eval").mkdir(exist_ok=True)
    with open(ROOT / "eval" / "history.jsonl", "a") as h: h.write(json.dumps(res) + "\n")
    (ROOT / "eval" / "misses.jsonl").write_text("\n".join(json.dumps(m) for m in misses) + "\n")
    if a.out:
        Path(a.out).parent.mkdir(exist_ok=True); Path(a.out).write_text(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
