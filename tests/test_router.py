"""Test router.route: shortest routes, turns, underground hops, the rules belts must follow, and the cases with no route."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import router

D = router.DIRS


def step(p, d, n=1):
    return (p[0] + D[d][0] * n, p[1] + D[d][1] * n)


def check(steps, start, goal, blocked):
    """Every rule a real belt line must follow."""
    assert steps and steps[0][1] == start and steps[-1][1] == goal, (steps[0], steps[-1])
    seen = set()
    for i, (kind, tile, d) in enumerate(steps):
        assert tile not in blocked, ("on a blocked tile", tile)
        assert tile not in seen, ("tile used twice", tile)
        seen.add(tile)
        if i == len(steps) - 1:
            break
        nk, nt, nd = steps[i + 1]
        if kind == "ug_in":
            assert nk == "ug_out" and nd == d, "an entrance is followed by its exit, same direction"
            n = abs(nt[0] - tile[0]) + abs(nt[1] - tile[1])
            assert nt == step(tile, d, n) and 2 <= n <= router.MAX_GAP + 1, ("gap out of range", tile, nt)
        else:
            assert nt == step(tile, d), ("next tile is not where this one points", tile, d, nt)   # also forces straight after an exit
            assert nd != router.OPPOSITE[d], "no 180 degree reversal"
            if nk == "ug_in":
                assert nd == d, "a belt feeds an entrance straight on"
        if kind == "ug_out":
            assert nk in ("belt", "ug_in")


def kinds(steps):
    return [s[0] for s in steps]


# a straight run: every tile is a belt facing the way we go
r = router.route((0, 0), (3, 0), set())
check(r, (0, 0), (3, 0), set())
assert kinds(r) == ["belt"] * 4 and [s[2] for s in r[:3]] == ["RIGHT"] * 3

# one turn, shortest length (5 tiles from (0,0) to (2,2)), no underground
r = router.route((0, 0), (2, 2), set())
check(r, (0, 0), (2, 2), set())
assert len(r) == 5 and "ug_in" not in kinds(r)

# a short wall: going around is cheaper than an underground pair
wall = {(2, 0)}
r = router.route((0, 0), (4, 0), wall)
check(r, (0, 0), (4, 0), wall)
assert "ug_in" not in kinds(r), r

# a long wall: the underground hop beats the detour
wall = {(2, y) for y in range(-8, 9)}
r = router.route((0, 0), (4, 0), wall)
check(r, (0, 0), (4, 0), wall)
assert ("ug_in", (1, 0), "RIGHT") in r, r
assert any(k == "ug_out" and t[0] in (3, 4) for k, t, _ in r), r   # exiting at (3,0) then one belt, or straight at (4,0), cost the same

# a wall too thick for one pair: no route inside a one-row strip
wall = {(x, 0) for x in range(1, 8)}
assert router.route((0, 0), (9, 0), wall, bounds=(-2, 0, 12, 0)) is None

# exactly the maximum gap works, one more does not
wall = {(x, 0) for x in range(2, 2 + router.MAX_GAP)}   # MAX_GAP blocked tiles between entrance (1,0) and exit
r = router.route((0, 0), (2 + router.MAX_GAP + 1, 0), wall, bounds=(-2, 0, 14, 0))
assert r is not None
check(r, (0, 0), (2 + router.MAX_GAP + 1, 0), wall)
wall = {(x, 0) for x in range(2, 3 + router.MAX_GAP)}
assert router.route((0, 0), (3 + router.MAX_GAP + 1, 0), wall, bounds=(-2, 0, 14, 0)) is None

# after an underground exit the line continues straight for one tile before it may turn
wall = {(2, y) for y in range(-8, 9)}
r = router.route((0, 0), (4, 3), wall)
check(r, (0, 0), (4, 3), wall)
i = kinds(r).index("ug_out")
if i + 1 < len(r):   # the route may also end right on the exit; check() already enforces the straight tile after any exit
    assert r[i + 1][1] == step(r[i][1], r[i][2])

# blocked start or goal, and start equals goal
assert router.route((0, 0), (3, 0), {(0, 0)}) is None
assert router.route((0, 0), (3, 0), {(3, 0)}) is None
assert router.route((1, 1), (1, 1), set()) == [("belt", (1, 1), "RIGHT")]
assert router.route((1, 1), (1, 1), set(), end_dir="DOWN") == [("belt", (1, 1), "DOWN")]

# the goal is walled in on all four sides with room for an underground exit only: still routed or None, never a crash
box = {(5, 4), (5, 6), (4, 5), (6, 5)}
r = router.route((0, 5), (5, 5), box)
assert r is None or check(r, (0, 5), (5, 5), box) is None

# float tiles from the game are rounded to integers by the caller; ints and floats of whole numbers both work
r = router.route((0.0, 0.0), (2.0, 0.0), set())
assert [s[1] for s in r] == [(0, 0), (1, 0), (2, 0)]

# a maze: the route threads the gap in the wall
wall = {(3, y) for y in range(-6, 7) if y != 4}
r = router.route((0, 0), (6, 0), wall, max_gap=0)
check(r, (0, 0), (6, 0), wall)
assert (3, 4) in [s[1] for s in r]

# the scan command and its reply parser: no Lua comments or newlines (it is one RCON line), a box in, tiles out, junk tolerated
lua = router.scan_lua((-3, 4, 5, 9))
assert lua.startswith("/silent-command ") and "\n" not in lua and "--" not in lua
assert "for x=-3,5 do for y=4,9 do" in lua and "transport-belt" in lua
assert router.parse_blocked("1:2;3:-4;") == {(1, 2), (3, -4)}
assert router.parse_blocked("") == set() and router.parse_blocked(None) == set()
assert router.parse_blocked("1:2;oops;3:x;4:5") == {(1, 2), (4, 5)}

# the place command: one line, one entry per step, underground type and facing carried through
steps = [("belt", (0, 0), "RIGHT"), ("ug_in", (1, 0), "RIGHT"), ("ug_out", (4, 0), "RIGHT"), ("belt", (5, 0), "DOWN")]
lua = router.place_lua(steps)
assert lua.startswith("/silent-command ") and "\n" not in lua and "--" not in lua
assert lua.count("{'transport-belt'") == 2 and "{'underground-belt',1,0,defines.direction.east,'input'}" in lua
assert "{'underground-belt',4,0,defines.direction.east,'output'}" in lua and "{'transport-belt',5,0,defines.direction.south,nil}" in lua
print("ok")
