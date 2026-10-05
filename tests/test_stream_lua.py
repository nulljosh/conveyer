"""Run stream.py's real Lua in Lua 5.2 (Factorio's version) against a fake game, then parse what it printed.
Catches Lua syntax errors and wrong API shapes before they reach the server. Skips when no lua5.2 binary is installed (CI installs it)."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fakes
S = fakes.load("stream")

LUA = shutil.which("lua5.2") or shutil.which("lua")
if not LUA:
    print("skip: no lua5.2"); raise SystemExit(0)
ver = subprocess.run([LUA, "-v"], capture_output=True, text=True)
if "5.2" not in ver.stdout + ver.stderr:   # Factorio runs 5.2; a newer Lua would pass code 5.2 rejects, so it proves nothing
    print("skip: need Lua 5.2, got " + (ver.stdout + ver.stderr).strip()); raise SystemExit(0)

MOCK = r"""
storage={}
MS={1,3,9}
defines={entity_status={working=1,normal=2,no_power=3,no_fuel=4,full_output=5,low_power=6,no_minable_resources=7,disabled_by_control_behavior=8,waiting=9},
         inventory={chest=1,turret_ammo=2}}
local function inv(counts) return {get_item_count=function(n) return counts[n] or 0 end} end
local function ent(t) t.valid=true local c=t.counts or {} t.get_inventory=function(i) return inv(c) end return t end
local char=ent{name='character',type='character',position={x=1.5,y=-2.25}}
local silo=ent{name='rocket-silo',position={x=-64.5,y=10.5},rocket_parts=42,status=1,rocket_silo_status=3}
local surf={find_entities_filtered=function(f)
  if f.type=='character' then return CHARS end
  if f.name=='rocket-silo' then return SILOS end
  if f.name=='rocket-silo-rocket' then return {} end
  if f.force=='enemy' then return {ent{name='medium-biter',type='unit',position={x=3,y=4}},ent{name='big-spitter',type='unit',position={x=5,y=5}},
                                   ent{name='biter-spawner',type='unit-spawner',position={x=9,y=9}},ent{name='behemoth-worm-turret',type='turret',position={x=7,y=7}}} end
  if f.type=='ammo-turret' then return {ent{name='gun-turret',position={x=0,y=0},counts={['firearm-magazine']=7}}} end
  if f.type=='container' then return {ent{counts={coal=5,['iron-plate']=2}},ent{counts={coal=1}}} end
  return {ent{position={x=1,y=2},status=MS[1]},ent{position={x=3,y=4},status=MS[2]},ent{position={x=5,y=6},status=MS[3]}}
end}
game={surfaces={surf},tick=1234,forces={player={rockets_launched=2}}}
rcon={print=function(s) io.write(s) end}
"""


def run(setup, parts, area=(-10, -10, 10, 10), full=True, again=None):
    cmd = S.build_lua(parts, area, full)
    assert cmd.startswith("/silent-command ")
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as f:
        f.write(MOCK + setup + "\n" + cmd[len("/silent-command "):])
        if again:   # a second read in the same game: storage carries over, setup changes what the machines look like
            f.write('\nio.write("\\n@@\\n")\n' + again + "\n" + S.build_lua(parts, area, False)[len("/silent-command "):])
    r = subprocess.run([LUA, f.name], capture_output=True, text=True, timeout=10)
    Path(f.name).unlink()
    assert r.returncode == 0, r.stderr
    return r.stdout


# a full frame, every part
out = run("CHARS={char} SILOS={silo}", list(S.LUA))
d = S.parse(out, 1.0, {}, {})
assert set(d) == set(S.LUA), (out, d)
assert d["pos"] == {"x": 1.5, "y": -2.25, "tick": 1234}
assert d["dots"]["d"] == [[1.0, 2.0, 0], [3.0, 4.0, 2], [5.0, 6.0, 1]]
assert d["combat"]["enemies"] == [[3.0, 4.0, 0, 1], [5.0, 5.0, 1, 2], [9.0, 9.0, 3, 0], [7.0, 7.0, 2, 3]]
assert d["combat"]["turrets"] == [[0.0, 0.0, 0]], d["combat"]
slots = {s["name"]: s["count"] for s in d["hotbar"]["slots"]}
assert slots["coal"] == 6 and slots["iron-plate"] == 2 and slots["rocket-fuel"] == 0 and len(slots) == len(S.HOTBAR_KEYS)
assert d["silo"]["x"] == -64.5 and d["silo"]["parts"] == 42 and d["silo"]["status"] == "working" and d["silo"]["launched"] == 2

# no character and no silo yet: those parts come back empty, the frame does not error
out = run("CHARS={} SILOS={}", list(S.LUA))
d = S.parse(out, 1.0, {}, {})
assert "pos" not in d and "combat" not in d and "silo" not in d and "dots" in d and "hotbar" in d, out

# a dead cached character is replaced by a fresh lookup
out = run("storage.cv_char={valid=false} CHARS={char} SILOS={silo}", ["pos"])
assert out.strip() == "pos=1.5,-2.25,1234", out

# dots deltas: a full read lists every machine; the next read lists only the one whose status changed
first, second = run("CHARS={char} SILOS={silo}", ["dots"], again="MS[2]=1").split("\n@@\n")
assert first == "dots=F|1.0:2.0:0;3.0:4.0:2;5.0:6.0:1", first
assert second == "dots=D|3.0:4.0:0", second   # only the machine that went from no_power to working
print("ok")
