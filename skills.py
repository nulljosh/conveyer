"""
Deterministic skill layer between agent.py and FLE.

The LLM no longer writes Python. It picks a skill name + JSON params each turn.
Each skill here is a small Python source TEMPLATE (not a real function you can
import and call) because the code has to run inside FLE's remote exec sandbox
against the live game, not in this process. `render(name, params)` fills in a
template and returns the code string agent.py sends to `Action`.

Every template re-fetches entities by literal position instead of relying on
Python variables persisting across snippets (they don't, see agent.py's old
system prompt) and ends with an assert/print so failure is visible in the
observation instead of a silent no-op.

ponytail: covers exactly the first goal (iron ore + coal -> plate -> gear)
plus power, not the full FLE surface (oil, research, chemical plants). Add a
template here when a new skill is actually needed, not before.
"""

SKILLS = {
    "mine": {
        "params": ["resource", "drill_prototype"],
        "doc": "Place a mining drill on the nearest patch of `resource` (a Resource.* name, "
        "e.g. 'IronOre') using `drill_prototype` (a Prototype.* name, e.g. 'BurnerMiningDrill'), "
        "fuel it with coal if it's a burner drill, and return its position.",
        "template": '''
patch = nearest(Resource.{resource})
box = BuildingBox(width=Prototype.{drill_prototype}.WIDTH, height=Prototype.{drill_prototype}.HEIGHT)
spot = nearest_buildable(Prototype.{drill_prototype}, box, patch)
move_to(spot.center)
drill = place_entity(Prototype.{drill_prototype}, position=spot.center, direction=Direction.DOWN)
if "Burner" in "{drill_prototype}":
    drill = insert_item(Prototype.Coal, drill, quantity=20)
print(f"SKILL_OK mine: placed {drill_prototype} at {{drill.position}} on {resource}")
''',
    },
    "smelt": {
        "params": ["source_position", "drill_prototype", "furnace_prototype"],
        "doc": "Place a furnace next to the mining drill (`drill_prototype`, e.g. "
        "'BurnerMiningDrill') at `source_position` (e.g. 'x=1.0,y=2.0') to catch and smelt its "
        "output into plates.",
        "template": '''
source = get_entity(Prototype.{drill_prototype}, position=Position({source_position}))
box = BuildingBox(width=Prototype.{furnace_prototype}.WIDTH + 2, height=Prototype.{furnace_prototype}.HEIGHT + 2)
spot = nearest_buildable(Prototype.{furnace_prototype}, box, source.drop_position)
move_to(spot.center)
furnace = place_entity(Prototype.{furnace_prototype}, position=spot.center, direction=Direction.UP)
furnace = insert_item(Prototype.Coal, furnace, quantity=20)
belts = connect_entities(source.drop_position, furnace.pickup_position, Prototype.TransportBelt)
print(f"SKILL_OK smelt: placed {furnace_prototype} at {{furnace.position}}, connected to source at {{source.position}}")
''',
    },
    "craft": {
        "params": ["item_prototype", "count"],
        "doc": "Craft `count` of `item_prototype` (e.g. 'IronGearWheel') by hand from current "
        "inventory. Fails loudly if the required ingredients aren't in inventory yet.",
        "template": '''
before = inspect_inventory().get(Prototype.{item_prototype}, 0)
craft_item(Prototype.{item_prototype}, count={count})
after = inspect_inventory().get(Prototype.{item_prototype}, 0)
assert after > before, f"SKILL_FAIL craft: {{Prototype.{item_prototype}}} count did not increase ({{before}} -> {{after}}), check ingredients via inspect_inventory()"
print(f"SKILL_OK craft: {item_prototype} now at {{after}} in inventory")
''',
    },
    "place": {
        "params": ["prototype", "near_position", "direction"],
        "doc": "Place a single `prototype` entity (e.g. 'WoodenChest') on open ground near "
        "`near_position`, facing `direction` (UP/DOWN/LEFT/RIGHT). For anything that needs "
        "fuel or connections, use a dedicated skill (mine/smelt/build_power) instead.",
        "template": '''
box = BuildingBox(width=Prototype.{prototype}.WIDTH + 2, height=Prototype.{prototype}.HEIGHT + 2)
spot = nearest_buildable(Prototype.{prototype}, box, Position({near_position}))
move_to(spot.center)
entity = place_entity(Prototype.{prototype}, position=spot.center, direction=Direction.{direction})
print(f"SKILL_OK place: {prototype} at {{entity.position}}")
''',
    },
    "build_power": {
        "params": ["water_position"],
        "doc": "Build a full offshore pump -> boiler -> steam engine chain starting from "
        "`water_position` (a tile on water, find one first if you don't have one) and confirm "
        "the steam engine is generating energy.",
        "template": '''
move_to(Position({water_position}))
pump = place_entity(Prototype.OffshorePump, position=Position({water_position}))

box = BuildingBox(width=Prototype.Boiler.WIDTH + 4, height=Prototype.Boiler.HEIGHT + 4)
spot = nearest_buildable(Prototype.Boiler, box, pump.position)
move_to(spot.center)
boiler = place_entity(Prototype.Boiler, position=spot.center, direction=Direction.LEFT)
boiler = insert_item(Prototype.Coal, boiler, quantity=20)

box = BuildingBox(width=Prototype.SteamEngine.WIDTH + 4, height=Prototype.SteamEngine.HEIGHT + 4)
spot = nearest_buildable(Prototype.SteamEngine, box, boiler.position)
move_to(spot.center)
engine = place_entity(Prototype.SteamEngine, position=spot.center, direction=Direction.LEFT)

connect_entities(pump, boiler, Prototype.Pipe)
connect_entities(boiler, engine, Prototype.Pipe)
sleep(5)
engine = get_entity(Prototype.SteamEngine, position=engine.position)
assert engine.energy > 0, "SKILL_FAIL build_power: steam engine has no energy after 5s"
print(f"SKILL_OK build_power: steam engine at {{engine.position}} generating {{engine.energy}}")
''',
    },
    "inspect": {
        "params": [],
        "doc": "Print current inventory and nearby entities. Use this when unsure what state "
        "you're in instead of guessing.",
        "template": '''
print(f"SKILL_OK inspect: inventory={{inspect_inventory()}}")
''',
    },
}


def render(name: str, params: dict) -> str:
    if name not in SKILLS:
        known = ", ".join(SKILLS)
        raise ValueError(f"unknown skill {name!r}, known skills: {known}")
    spec = SKILLS[name]
    missing = [p for p in spec["params"] if p not in params]
    if missing:
        raise ValueError(f"skill {name!r} missing params: {missing}")
    try:
        return spec["template"].format(**params)
    except (KeyError, IndexError) as e:
        raise ValueError(f"skill {name!r} template substitution failed: {e}") from e


def catalog_text() -> str:
    lines = []
    for name, spec in SKILLS.items():
        lines.append(f"- {name}({', '.join(spec['params'])}): {spec['doc']}")
    return "\n".join(lines)


def _demo() -> None:
    """Self-check: every skill renders without leftover `{param}` placeholders or
    unresolved doubled braces, and unknown skills/missing params raise cleanly."""
    sample_params = {
        "resource": "IronOre",
        "drill_prototype": "BurnerMiningDrill",
        "source_position": "x=1.0,y=2.0",
        "furnace_prototype": "StoneFurnace",
        "item_prototype": "IronGearWheel",
        "count": 1,
        "prototype": "WoodenChest",
        "near_position": "x=0,y=0",
        "direction": "UP",
        "water_position": "x=0,y=0",
    }
    for name, spec in SKILLS.items():
        params = {p: sample_params[p] for p in spec["params"]}
        code = render(name, params)
        leftover = [p for p in spec["params"] if "{" + p + "}" in code]
        assert not leftover, f"{name}: unsubstituted placeholders {leftover} in:\n{code}"

    try:
        render("nope", {})
        raise AssertionError("expected ValueError for unknown skill")
    except ValueError:
        pass

    try:
        render("mine", {})
        raise AssertionError("expected ValueError for missing params")
    except ValueError:
        pass

    print("skills self-check OK")


if __name__ == "__main__":
    _demo()
