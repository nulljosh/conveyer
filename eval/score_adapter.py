#!/usr/bin/env python3
"""Score the skill picker on data/valid.jsonl: exact skill name, then exact params. Base model vs the LoRA adapter.
python3 eval/score_adapter.py [conveyer-adapter]"""
import json, sys
from pathlib import Path
from mlx_lm import load, generate

ROOT = Path(__file__).resolve().parent.parent  # run from eval/: scripts/ has a queue.py that shadows the stdlib
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


def parse(text):
    try: d = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except ValueError: return None, None
    return d.get("skill"), d.get("params")


def score(adapter):
    model, tok = load(MODEL, adapter_path=adapter)
    rows = [json.loads(l) for l in (ROOT / "data" / "valid.jsonl").read_text().splitlines() if l]
    name = params = 0
    for r in rows:
        msgs = r["messages"]
        prompt = tok.apply_chat_template(msgs[:-1], add_generation_prompt=True, tokenize=False)
        want_name, want_params = parse(msgs[-1]["content"])
        got_name, got_params = parse(generate(model, tok, prompt=prompt, max_tokens=200))
        name += got_name == want_name
        params += got_name == want_name and got_params == want_params
    return len(rows), name, params


if __name__ == "__main__":
    adapter = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "conveyer-adapter")
    for label, a in (("base", None), ("adapter", adapter)):
        n, name, params = score(a)
        print("%-8s skill name %d/%d (%.0f%%)  name+params %d/%d (%.0f%%)" % (label, name, n, 100 * name / n, params, n, 100 * params / n))
