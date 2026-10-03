"""Test steelfeed.feed: returns the server's report, survives a dead server, and the Lua only targets steel furnaces."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("steelfeed", ROOT / "scripts" / "steelfeed.py")
steelfeed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(steelfeed)

assert steelfeed.feed(lambda lua: "steel furnaces fed 300 plates, 0 starved of iron") == "steel furnaces fed 300 plates, 0 starved of iron"
assert steelfeed.feed(lambda lua: "") == "no reply"


def dead(lua):
    raise ConnectionError("rcon down")


assert steelfeed.feed(dead).startswith("steelfeed skipped: rcon down")
assert "'steel-furnace'" in steelfeed.LUA and "steel-plate" in steelfeed.LUA and "furnace_source" in steelfeed.LUA
print("ok")
