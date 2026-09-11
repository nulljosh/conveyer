#!/usr/bin/env python3
"""
Cheap terminal visual for conveyer: polls entity/player positions via a single
RCON query every couple seconds and draws an ASCII map. No render(), no game
client, negligible load on the already CPU-strained Factorio/Box64 container.
"""
import os
import sys
import time

from factorio_rcon import RCONClient

HOST, PORT, PASSWORD = "127.0.0.1", 27000, "factorio"
GRID_W, GRID_H = 60, 24  # terminal cells
VIEW = 80  # world tiles shown across the grid width

LUA = (
    "local out = {} "
    "for _, p in pairs(game.players) do "
    "table.insert(out, string.format('player:%.1f,%.1f', p.position.x, p.position.y)) end "
    "local ents = game.surfaces[1].find_entities_filtered{force='player'} "
    "for _, e in pairs(ents) do "
    "table.insert(out, string.format('%s:%.1f,%.1f', e.name, e.position.x, e.position.y)) end "
    "rcon.print(table.concat(out, ';'))"
)

GLYPH = {
    "character": "@",
    "burner-mining-drill": "D",
    "electric-mining-drill": "D",
    "stone-furnace": "F",
    "steel-furnace": "F",
    "assembling-machine-1": "A",
    "assembling-machine-2": "A",
    "assembling-machine-3": "A",
    "transport-belt": ".",
    "burner-inserter": "i",
    "inserter": "i",
    "wooden-chest": "c",
    "iron-chest": "c",
    "boiler": "B",
    "steam-engine": "E",
    "small-electric-pole": "-",
}


def poll(client):
    resp = client.send_command(f"/sc {LUA}")
    entities = []
    player = None
    for part in resp.split(";"):
        if not part or ":" not in part:
            continue
        name, coords = part.split(":", 1)
        x, y = map(float, coords.split(","))
        if name == "player":
            player = (x, y)
        else:
            entities.append((name, x, y))
    return player, entities


def draw(player, entities):
    grid = [[" "] * GRID_W for _ in range(GRID_H)]
    cx, cy = player if player else (0, 0)
    scale = GRID_W / VIEW
    for name, x, y in entities:
        gx = int((x - cx) * scale + GRID_W / 2)
        gy = int((y - cy) * (scale / 2) + GRID_H / 2)
        if 0 <= gx < GRID_W and 0 <= gy < GRID_H:
            grid[gy][gx] = GLYPH.get(name, "?")
    if player:
        gx, gy = GRID_W // 2, GRID_H // 2
        grid[gy][gx] = "@"
    os.system("clear")
    print(f"conveyer — live view (player at {cx:.1f}, {cy:.1f})")
    print("+" + "-" * GRID_W + "+")
    for row in grid:
        print("|" + "".join(row) + "|")
    print("+" + "-" * GRID_W + "+")
    counts = {}
    for name, _, _ in entities:
        counts[name] = counts.get(name, 0) + 1
    print("  ".join(f"{GLYPH.get(n, '?')}={n}:{c}" for n, c in sorted(counts.items())))


def main():
    client = RCONClient(HOST, PORT, PASSWORD)
    client.connect()
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    try:
        while True:
            player, entities = poll(client)
            draw(player, entities)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
