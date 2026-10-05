"""Test progress_svg.py render with temp data."""
import json, tempfile, time, sys, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Load progress_svg module
spec = importlib.util.spec_from_file_location("progress_svg", ROOT / "scripts" / "progress_svg.py")
progress_svg = importlib.util.module_from_spec(spec)

# Load the module first, then point DATA and OUT at a temp dir: set before loading, the module's own assignments win
# and the test overwrote and then deleted the real progress.svg and docs/progress.jsonl
spec.loader.exec_module(progress_svg)
tmpdir = Path(tempfile.mkdtemp())
progress_svg.DATA = tmpdir / "progress.jsonl"
progress_svg.OUT = tmpdir / "progress.svg"

# Test 1: with only 1 row, render outputs "collecting data"
now = time.time()
progress_svg.DATA.write_text(json.dumps({
    "t": round(now),
    "version": "1.0.0",
    "techs": 5,
    "entities": 10,
    "tiles": 3
}) + "\n")
progress_svg.render()
svg1 = progress_svg.OUT.read_text()
assert "collecting data" in svg1, "Should show 'collecting data' with only 1 row"
progress_svg.OUT.unlink()

# Test 2: with 3 rows, render outputs polyline and version
rows = []
for i in range(3):
    rows.append({
        "t": round(now + i * 100),
        "version": "1.0.0",
        "techs": 5 + i * 2,
        "entities": 10 + i * 3,
        "tiles": 3 + i
    })
progress_svg.DATA.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
progress_svg.render()
svg = progress_svg.OUT.read_text()
assert progress_svg.OUT.exists(), "SVG file should exist"
assert "<polyline" in svg, "SVG should contain polyline"
assert "v1.0.0" in svg, "SVG should contain version v1.0.0"

# Cleanup
progress_svg.OUT.unlink()
progress_svg.DATA.unlink()
tmpdir.rmdir()
print("ok")
