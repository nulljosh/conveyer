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

# the view rectangle: missing, half-written or zero-size frame.json means no dots this frame, never a crash
with tempfile.TemporaryDirectory() as tmp:
    fp = Path(tmp) / "frame.json"
    assert S.read_area(fp) is None
    fp.write_text('{"cx": 0, "cy"')
    assert S.read_area(fp) is None
    fp.write_text('{"cx": 0, "cy": 0, "w": 0, "h": 160, "ppt": 16}')
    assert S.read_area(fp) is None
    fp.write_text('{"cx": 0, "cy": 0, "w": 320, "h": 160, "ppt": 0}')
    assert S.read_area(fp) is None
    fp.write_text('{"cx": 0, "cy": 0, "w": 320, "h": 160, "ppt": 16}')
    assert S.read_area(fp) == (-10, -5, 10, 5)

# a failed write is skipped and retried next frame, never fatal
with tempfile.TemporaryDirectory() as tmp:
    w = S.Writer(Path(tmp) / "missing-dir")
    assert w.write({"pos": {"x": 1.0, "y": 2.0, "tick": 1}}, 0.0) == []
    (Path(tmp) / "missing-dir").mkdir()
    assert w.write({"pos": {"x": 1.0, "y": 2.0, "tick": 1}}, 0.1) == ["pos"]
    assert w.write({"nope": {}, "pos": "not a dict"}, 0.2) == []   # unknown parts and junk are ignored

# the loop body with a fake server: connect, read, write; then fail, back off, recover
sys.path.insert(0, str(ROOT / "tests"))
import fakes
REPLY = "pos=1.0,2.0,5\ndots=1.0:2.0:0\ncombat=p:1:2\nhotbar=coal,3;\nsilo=0:0:1:working:0:0:1"
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    conns = []
    def connect(replies):
        def c():
            r = fakes.FakeRCON(replies); conns.append(r); return r
        return c
    st = S.Streamer(connect=connect([REPLY]), writer=S.Writer(tmp), frame=tmp / "frame.json")
    nap = st.step(1000.0)
    assert 0.02 <= nap <= 0.1 + 1e-9, nap
    assert {p.name for p in tmp.iterdir()} >= {"live.json", "combat.json", "hotbar.json", "silo.json", "stream.json"}
    assert "dots=" not in conns[0].sent[0]   # no frame.json yet
    assert not (tmp / "live_status.json").exists()
    assert st.last == {k: 1000.0 for k in S.RATES if k != "dots"}   # dots stay due until frame.json exists

    # only position is due 0.1 s later: the Lua asks for nothing else
    conns[0].replies = ["pos=1.5,2.0,6"]
    st.step(1000.1)
    assert "pos=" in conns[0].sent[1] and "combat=" not in conns[0].sent[1]
    assert json.loads((tmp / "live.json").read_text())["x"] == 1.5

    # the server drops: connection closed, backoff grows 1, 2, 4 ... and stops at 30
    conns[0].replies = [ConnectionError("refused")]
    assert st.step(1000.2) == 1.0 and st.rcon is None and conns[0].closed
    st.connect = lambda: (_ for _ in ()).throw(OSError("down"))
    naps = [st.step(1000.3 + i) for i in range(7)]
    assert naps == [2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0], naps

    # it comes back: one good frame resets the backoff
    st.connect = connect(["pos=9.0,9.0,7"])
    assert st.step(1010.0) < 1.0 and st.fails == 0
    assert json.loads((tmp / "live.json").read_text())["x"] == 9.0

    # a reply that is not text counts as a failure, not a crash
    conns[-1].replies = lambda cmd: None
    assert st.step(1011.0) == 1.0 and st.fails == 1

    # with a valid frame.json the dots come back too
    (tmp / "frame.json").write_text('{"cx": 0, "cy": 0, "w": 320, "h": 160, "ppt": 16}')
    st = S.Streamer(connect=connect([REPLY]), writer=S.Writer(tmp), frame=tmp / "frame.json")
    st.step(2000.0)
    assert "area={{-10,-5},{10,5}}" in conns[-1].sent[0]
    assert json.loads((tmp / "live_status.json").read_text())["d"] == [[1.0, 2.0, 0]]
print("ok")

# dots deltas: the first read is full, later ones are merged into what is known, a full read every 30 s drops machines that are gone
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); (tmp / "frame.json").write_text('{"cx": 0, "cy": 0, "w": 320, "h": 160, "ppt": 16}')
    conns = []
    def connect():
        r = fakes.FakeRCON(["dots=F|1.0:2.0:0;3.0:4.0:2"]); conns.append(r); return r
    st = S.Streamer(connect=connect, writer=S.Writer(tmp), frame=tmp / "frame.json")
    st.step(0.0)
    assert "true" in conns[0].sent[0] and json.loads((tmp / "live_status.json").read_text())["d"] == [[1.0, 2.0, 0], [3.0, 4.0, 2]]
    conns[0].replies = ["dots=D|3.0:4.0:0;5.0:6.0:1"]
    st.step(1.0)
    assert json.loads((tmp / "live_status.json").read_text())["d"] == [[1.0, 2.0, 0], [3.0, 4.0, 0], [5.0, 6.0, 1]]
    conns[0].replies = ["dots=F|5.0:6.0:1"]
    st.step(31.0)   # 30 s since the last full read: asks for a full snapshot, which replaces everything
    assert json.loads((tmp / "live_status.json").read_text())["d"] == [[5.0, 6.0, 1]]
    conns[0].replies = [ConnectionError("x")]
    st.step(32.0); assert st.need_full   # a failed read means the next dots read is full again
print("ok")
