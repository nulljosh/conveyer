"""router.py: belt routing for the route_belt skill (#4). Pure Python, no game imports, so tests/test_router.py can check it.

route(start, goal, blocked) finds the cheapest belt path between two free tiles with A*. Where a wall is in the way and a detour costs
more, it hops the wall with an underground belt pair. Rules it keeps, all from how Factorio belts work:
  - a belt never turns back on itself (no 180 degree reversal);
  - an underground pair spans at most MAX_GAP tiles between entrance and exit;
  - an underground exit outputs straight ahead, so the tile after an exit continues in the same direction (the turn happens one tile later);
  - the entrance and exit tiles must be free, the tiles between them may be anything (water, machines, other belts).
Tiles are integer (x, y) with y growing downward, so UP is (0, -1) like in the game. Directions are the strings UP RIGHT DOWN LEFT.

Result: a list of steps, each ("belt" | "ug_in" | "ug_out", (x, y), direction), in travel order. None when there is no route.
"""
import heapq

DIRS = {"UP": (0, -1), "RIGHT": (1, 0), "DOWN": (0, 1), "LEFT": (-1, 0)}
OPPOSITE = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}
MAX_GAP = 4          # basic underground belt: up to 4 tiles between the entrance and the exit
UNDER_COST = 4.0     # a pair costs more than the belts it replaces, so plain belts win unless the detour is long
TURN_COST = 0.05     # tie-break toward straight runs
MARGIN = 10          # how far outside the start/goal box the search may wander
MAX_NODES = 60000    # guard: give up instead of searching forever


def _add(p, d, n=1):
    dx, dy = DIRS[d]
    return (p[0] + dx * n, p[1] + dy * n)


def route(start, goal, blocked, bounds=None, max_gap=MAX_GAP, end_dir=None):
    """Cheapest belt route from the tile `start` to the tile `goal`. `blocked` is a set of (x, y) tiles that cannot hold a belt.
    `bounds` is (min_x, min_y, max_x, max_y) to stay inside; default is the start/goal box plus MARGIN. `end_dir` sets the facing of the last tile."""
    start, goal = (int(start[0]), int(start[1])), (int(goal[0]), int(goal[1]))
    blocked = {(int(x), int(y)) for x, y in blocked}
    if start in blocked or goal in blocked:
        return None
    if bounds is None:
        bounds = (min(start[0], goal[0]) - MARGIN, min(start[1], goal[1]) - MARGIN, max(start[0], goal[0]) + MARGIN, max(start[1], goal[1]) + MARGIN)
    x0, y0, x1, y1 = bounds

    def free(p):
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and p not in blocked

    def h(p):
        return abs(p[0] - goal[0]) + abs(p[1] - goal[1])

    if start == goal:
        return [("belt", start, end_dir or "RIGHT")]

    # node: (tile, direction we arrived in, True when we just left an underground exit and must go straight)
    root = (start, None, False)
    best = {root: 0.0}
    came = {}
    heap = [(h(start), 0.0, 0, root)]
    tick, seen = 1, 0
    end = None
    while heap:
        _, g, _, node = heapq.heappop(heap)
        if g > best.get(node, 1e18):
            continue
        tile, d_in, forced = node
        if tile == goal:
            end = node
            break
        seen += 1
        if seen > MAX_NODES:
            return None
        for d in DIRS:
            if d_in is not None and d == OPPOSITE[d_in]:
                continue
            if forced and d != d_in:
                continue
            q = _add(tile, d)
            if not free(q):
                # an underground hop: entrance q must be free, so a blocked q means no hop from here in this direction
                pass
            else:
                cost = 1.0 + (TURN_COST if d_in is not None and d != d_in else 0.0)
                nxt = (q, d, False)
                if g + cost < best.get(nxt, 1e18):
                    best[nxt] = g + cost
                    came[nxt] = (node, ("step", d))
                    heapq.heappush(heap, (g + cost + h(q), g + cost, tick, nxt)); tick += 1
                # hop from the entrance q, over 1..max_gap tiles of anything, to a free exit tile
                for gap in range(1, max_gap + 1):
                    ex = _add(q, d, gap + 1)
                    if not free(ex):
                        continue
                    cost = 1.0 + (gap + 1) + UNDER_COST + (TURN_COST if d_in is not None and d != d_in else 0.0)
                    nxt = (ex, d, True)
                    if g + cost < best.get(nxt, 1e18):
                        best[nxt] = g + cost
                        came[nxt] = (node, ("ug", d, gap))
                        heapq.heappush(heap, (g + cost + h(ex), g + cost, tick, nxt)); tick += 1
    if end is None:
        return None

    moves = []
    node = end
    while node in came:
        node, mv = came[node]
        moves.append((node, mv))
    moves.reverse()

    steps = []
    for (tile, _, _), mv in moves:
        d = mv[1]
        if not steps or steps[-1][1] != tile:       # the tile we leave is a plain belt unless it already is an underground exit
            steps.append(("belt", tile, d))
        if mv[0] == "ug":
            gap = mv[2]
            entrance = _add(tile, d)
            exit_tile = _add(entrance, d, gap + 1)
            steps.append(("ug_in", entrance, d))
            steps.append(("ug_out", exit_tile, d))
    if steps[-1][1] != goal:                         # the goal tile itself: a belt facing end_dir, or the way we came (an exit on the goal keeps its own facing)
        steps.append(("belt", goal, end_dir or steps[-1][2]))
    return _dedupe(steps)


def _dedupe(steps):
    """A tile can be listed twice (a leaving belt on a tile that is already an exit); keep the underground entry."""
    out, at = [], {}
    for s in steps:
        if s[1] in at:
            if s[0] != "belt":
                out[at[s[1]]] = s
            continue
        at[s[1]] = len(out)
        out.append(s)
    return out


def length(steps):
    """Belt tiles used, counting each underground as its two tiles."""
    return len(steps)


def scan_lua(box):
    """One RCON command that lists every tile in box = (x0, y0, x1, y1) where a belt cannot be placed, as 'x:y;x:y'. The game's own check, so water,
    cliffs, trees and machines all count; FLE's can_place_entity depends on the engineer's inventory and reach, which made every tile look blocked."""
    x0, y0, x1, y1 = (int(v) for v in box)
    return ("/silent-command local s=game.surfaces[1] local o={} for x=%d,%d do for y=%d,%d do "
            "if not s.can_place_entity{name='transport-belt',position={x+0.5,y+0.5}} then o[#o+1]=x..':'..y end end end rcon.print(table.concat(o,';'))") % (x0, x1, y0, y1)


def parse_blocked(text):
    """The reply of scan_lua as a set of (x, y). Junk pieces are skipped, so a half-read reply gives fewer blocked tiles, never a crash."""
    out = set()
    for part in str(text or "").strip().split(";"):
        if ":" in part:
            try:
                x, y = part.split(":")
                out.add((int(x), int(y)))
            except ValueError:
                pass
    return out


FACING = {"UP": "north", "RIGHT": "east", "DOWN": "south", "LEFT": "west"}


def place_lua(steps):
    """One RCON command that creates every step of a route with the game's create_entity (free, like the planner's tiles: no belts needed in the
    engineer's inventory, so the skill must say it is console placed). Prints 'placed N failed M' plus the first failed tiles."""
    items = []
    for kind, (x, y), d in steps:
        name = "transport-belt" if kind == "belt" else "underground-belt"
        io = "nil" if kind == "belt" else ("'input'" if kind == "ug_in" else "'output'")
        items.append("{'%s',%d,%d,defines.direction.%s,%s}" % (name, x, y, FACING[d], io))
    return ("/silent-command local s=game.surfaces[1] local n,bad=0,{} for _,t in ipairs({%s}) do "
            "local e=s.create_entity{name=t[1],position={t[2]+0.5,t[3]+0.5},direction=t[4],type=t[5],force='player'} "
            "if e then n=n+1 else bad[#bad+1]=t[2]..':'..t[3] end end "
            "rcon.print('placed '..n..' failed '..#bad..' '..table.concat(bad,';'))") % ",".join(items)
