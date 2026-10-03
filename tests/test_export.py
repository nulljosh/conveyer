"""Smallest check that fails if the training export breaks: every line is a 3-message chat with a JSON skill answer."""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if not list((ROOT / "runs").glob("*.jsonl")):  # runs/ is not in git, so a fresh clone (CI) has nothing to export
    print("skip: no runs/"); raise SystemExit(0)
subprocess.run([sys.executable, str(ROOT / "scripts" / "export_training.py")], check=True, capture_output=True)
for name in ("train", "valid"):
    lines = (ROOT / "data" / f"{name}.jsonl").read_text().splitlines()
    assert lines, f"{name}.jsonl is empty"
    for l in lines:
        m = json.loads(l)["messages"]
        assert [x["role"] for x in m] == ["system", "user", "assistant"]
        ans = json.loads(m[2]["content"])
        assert "skill" in ans and "params" in ans
print("ok")
