"""Test planner.py's pure parts: tiers, the supply Lua, stock parsing, plan load/save. RCON is faked (CI has no game)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fakes
fakes.install_rcon()
P = fakes.load("planner")

# tiers: raw plates are 0, an item is 1 + its highest ingredient
rec = {"iron-gear-wheel": {"ing": {"iron-plate": 2}, "out": 1},
       "copper-cable": {"ing": {"copper-plate": 1}, "out": 2},
       "electronic-circuit": {"ing": {"iron-plate": 1, "copper-cable": 3}, "out": 1},
       "inserter": {"ing": {"electronic-circuit": 1, "iron-gear-wheel": 1, "iron-plate": 1}, "out": 1}}
t = P.tiers(rec)
assert t == {"iron-gear-wheel": 1, "copper-cable": 1, "electronic-circuit": 2, "inserter": 3}, t
assert P.tiers({}) == {}
assert P.tiers({"x": {"ing": {}, "out": 1}}) == {"x": 1}   # no ingredients: tier 1, not a crash on max([])

# supply: one Lua call for every tile whose recipe is known; unknown recipes are skipped, no tiles means no call
sent = []
P.run = lambda lua: sent.append(lua) or "moved 3"
plan = [{"item": "copper-cable", "cell": 0}, {"item": "iron-gear-wheel", "cell": 4}, {"item": "solar-panel", "cell": 5}]
assert P.supply(plan, rec) == "moved 3" and len(sent) == 1
lua = sent[0]
assert "item='copper-cable'" in lua and "item='iron-gear-wheel'" in lua and "solar-panel" not in lua
assert "['copper-plate']=%d" % P.BUF["copper-cable"] in lua   # buffer per recipe
ox, oy = P.OX + (4 % P.COLS) * P.CW, P.OY + (4 // P.COLS) * P.CH   # cell 4 sits in column 1, row 1
assert "p={%g,%g}" % (ox + 0.5, oy + 1.5) in lua
sent.clear()
assert P.supply([], rec) == "" and sent == []

# stock: 'name=count' pairs back into a dict
P.run = lambda lua: "coal=12 iron-plate=0"
assert P.stock(["coal", "iron-plate"]) == {"coal": 12, "iron-plate": 0}

# plan file round trip, and a missing plan is empty
with tempfile.TemporaryDirectory() as tmp:
    P.PLAN = Path(tmp) / "w" / "tiles.json"
    assert P.load() == []
    P.save(plan)
    assert P.load() == plan
print("ok")
