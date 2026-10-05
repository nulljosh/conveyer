"""Test stream.py: which parts are due, the one-line Lua, reply parsing, firing turrets, and write-on-change."""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("stream", ROOT / "scripts" / "stream.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

# rates: position every frame, the slow parts only when their interval passed
assert S.due(0.0, {}) == ["pos", "combat", "dots", "hotbar", "silo"]
last = {k: 10.0 for k in S.RATES}
assert S.due(10.15, last) == ["pos"]
assert S.due(10.6, last) == ["pos", "combat"]
assert S.due(12.0, last) == ["pos", "combat", "dots", "hotbar", "silo"]

# one RCON line, no newline and no '--' (a comment would silence the rest of a joined line)
lua = S.build_lua(list(S.LUA), (-10, -20, 10, 20))
assert lua.startswith("/silent-command ") and "\n" not in lua and "--" not in lua
assert "area={{-10,-20},{10,20}}" in lua and "radius=75" in lua
assert "dots=" not in S.build_lua(["pos", "dots"], None)   # no frame.json yet: skip the dots, keep the rest
assert S.view_area({"cx": 0, "cy": 10, "w": 320, "h": 160, "ppt": 16}) == (-10, 5, 10, 15)

reply = ("pos=1.5,-2.25,1234\ndots=1.0:2.0:0;3.0:4.0:2\ncombat=p:1.5:-2.2;e:3.0:4.0:0:1;t:0.0:0.0:7\n"
         "hotbar=coal,14;iron-plate,3;\nsilo=-64:10:42:working:2:0:3\njunk line")
mags, fired = {}, {}
d = S.parse(reply, 100.0, mags, fired)
assert d["pos"] == {"x": 1.5, "y": -2.25, "tick": 1234}
assert d["dots"] == {"t": 100.0, "d": [[1.0, 2.0, 0], [3.0, 4.0, 2]]}
assert d["combat"]["enemies"] == [[3.0, 4.0, 0, 1]] and d["combat"]["turrets"] == [[0.0, 0.0, 0]]
assert d["hotbar"] == {"slots": [{"name": "coal", "count": 14}, {"name": "iron-plate", "count": 3}]}
assert d["silo"]["parts"] == 42 and d["silo"]["status"] == "working"

# a turret whose magazine count dropped is firing, for 2 s
d = S.parse("combat=p:0:0;t:0.0:0.0:5", 101.0, mags, fired)
assert d["combat"]["turrets"] == [[0.0, 0.0, 1]]
d = S.parse("combat=p:0:0;t:0.0:0.0:5", 104.0, mags, fired)
assert d["combat"]["turrets"] == [[0.0, 0.0, 0]]

# empty or broken parts are left out, so the old file stays
assert S.parse("pos=\nsilo=1:2\ndots=x:y:z", 1.0, {}, {}) == {}

# files are written only when the content changed; a new tick or timestamp alone is not a change
with tempfile.TemporaryDirectory() as tmp:
    w = S.Writer(Path(tmp))
    assert w.write({"pos": {"x": 1.0, "y": 2.0, "tick": 1}}, 0.0) == ["pos"]
    assert w.write({"pos": {"x": 1.0, "y": 2.0, "tick": 9}}, 0.5) == []
    assert w.write({"pos": {"x": 1.5, "y": 2.0, "tick": 10}}, 0.6) == ["pos"]
    assert json.loads((Path(tmp) / "live.json").read_text())["x"] == 1.5
    assert json.loads((Path(tmp) / "stream.json").read_text())["pos"]["x"] == 1.5
print("ok")
