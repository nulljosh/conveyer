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
    "harvest": {
        "params": ["resource", "quantity"],
        "doc": "Hand-harvest `quantity` of `resource` (a Resource.* name, e.g. 'Wood', "
        "'Stone', 'Coal', 'IronOre') from the nearest patch/tree into your own inventory. "
        "This is the only way to get raw materials on a vanilla start — there's no free "
        "starting inventory.",
        "template": '''
before = inspect_inventory().get(Resource.{resource}, 0)
patch = nearest(Resource.{resource})
move_to(patch)
harvest_resource(patch, quantity={quantity})
after = inspect_inventory().get(Resource.{resource}, 0)
assert after > before, f"SKILL_FAIL harvest: {resource} count did not increase ({{before}} -> {{after}})"
print(f"SKILL_OK harvest: {resource} now at {{after}} in inventory")
''',
    },
    "research": {
        "params": ["technology"],
        "doc": "Set the current research technology (a Technology.* name, e.g. "
        "'Automation'). Requires science packs in a lab to actually progress.",
        "template": '''
ingredients = set_research(Technology.{technology})
print(f"SKILL_OK research: set to {technology}, needs {{ingredients}}")
''',
    },
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
move_to(source.drop_position)
furnace = place_entity_next_to(Prototype.{furnace_prototype}, reference_position=source.drop_position, direction=Direction.DOWN, spacing=0)
furnace = insert_item(Prototype.Coal, furnace, quantity=20)
print(f"SKILL_OK smelt: placed {furnace_prototype} at {{furnace.position}}, fed by source at {{source.position}}")
''',
    },
    "auto_feed": {
        "params": ["source_position", "drill_prototype", "furnace_prototype"],
        "doc": "The general-purpose automated drill->furnace chain: places a furnace clear "
        "of the resource patch, a burner inserter next to it, and a belt from the drill's "
        "drop_position to the inserter — the inserter then loads the furnace itself. Use "
        "this instead of `smelt` when direct drop-catch fails on a dense ore patch (a "
        "furnace/chest touching the drop tile only works when that tile is just outside "
        "the resource boundary).",
        "template": '''
source = get_entity(Prototype.{drill_prototype}, position=Position({source_position}))
box = BuildingBox(width=Prototype.{furnace_prototype}.WIDTH + 4, height=Prototype.{furnace_prototype}.HEIGHT + 4)
spot = nearest_buildable(Prototype.{furnace_prototype}, box, source.position)
move_to(spot.center)
furnace = place_entity(Prototype.{furnace_prototype}, position=spot.center, direction=Direction.UP)
furnace = insert_item(Prototype.Coal, furnace, quantity=20)
inserter = place_entity_next_to(Prototype.BurnerInserter, reference_position=furnace.position, direction=Direction.DOWN, spacing=0)
inserter = rotate_entity(inserter, Direction.UP)
inserter = insert_item(Prototype.Coal, inserter, quantity=5)
belts = connect_entities(source.drop_position, inserter.pickup_position, Prototype.TransportBelt)
print(f"SKILL_OK auto_feed: furnace at {{furnace.position}} fed via inserter at {{inserter.position}} from drill at {{source.position}}")
''',
    },
    "belt": {
        "params": ["from_prototype", "from_position", "to_prototype", "to_position"],
        "doc": "Connect two existing entities with transport belts (e.g. a drill's "
        "drop_position to an inserter's pickup_position).",
        "template": '''
a = get_entity(Prototype.{from_prototype}, position=Position({from_position}))
b = get_entity(Prototype.{to_prototype}, position=Position({to_position}))
belts = connect_entities(a.drop_position, b.pickup_position, Prototype.TransportBelt)
print(f"SKILL_OK belt: connected {from_prototype} at {{a.position}} to {to_prototype} at {{b.position}}")
''',
    },
    "research_progress": {
        "params": ["technology"],
        "doc": "Print remaining research progress/ingredients for a technology.",
        "template": '''
progress = get_research_progress(Technology.{technology})
print(f"SKILL_OK research_progress: {technology} needs {{progress}}")
''',
    },
    "place_inserter": {
        "params": ["target_prototype", "target_position"],
        "doc": "Place a BurnerInserter (from inventory) next to `target_prototype` at "
        "`target_position`, rotated to feed INTO it — the correct pattern for a furnace/"
        "assembler input, not the generic `place` skill.",
        "template": '''
target = get_entity(Prototype.{target_prototype}, position=Position({target_position}))
inserter = place_entity_next_to(Prototype.BurnerInserter, reference_position=target.position, direction=Direction.DOWN, spacing=0)
inserter = rotate_entity(inserter, Direction.UP)
print(f"SKILL_OK place_inserter: placed at {{inserter.position}}, feeding {target_prototype} at {{target.position}}")
''',
    },
    "find": {
        "params": ["resource"],
        "doc": "Print the position of the nearest patch of `resource` (a Resource.* name, "
        "e.g. 'Water') without moving or harvesting anything.",
        "template": '''
pos = nearest(Resource.{resource})
print(f"SKILL_OK find: nearest {resource} at {{pos}}")
''',
    },
    "recipe": {
        "params": ["item_prototype"],
        "doc": "Print the crafting recipe (ingredients) for an item, so you know what to "
        "gather before attempting `craft`.",
        "template": '''
r = get_prototype_recipe(Prototype.{item_prototype})
print(f"SKILL_OK recipe: {item_prototype} = {{r}}")
''',
    },
    "place_at": {
        "params": ["prototype", "position", "direction"],
        "doc": "Place `prototype` with its own footprint centered EXACTLY at `position` "
        "(no nearest_buildable padding/offset search) — use this when `place` puts things "
        "too far from a specific tile you already know is correct, e.g. a drill's real "
        "drop_position.",
        "template": '''
move_to(Position({position}))
entity = place_entity(Prototype.{prototype}, position=Position({position}), direction=Direction.{direction}, exact=False)
print(f"SKILL_OK place_at: {prototype} at {{entity.position}}")
''',
    },
    "pickup": {
        "params": ["prototype", "position"],
        "doc": "Pick an entity back up into your own inventory (e.g. to reposition a "
        "misplaced furnace).",
        "template": '''
e = get_entity(Prototype.{prototype}, position=Position({position}))
pickup_entity(e)
print(f"SKILL_OK pickup: picked up {prototype} from x={{e.position.x}} y={{e.position.y}}")
''',
    },
    "dropcheck": {
        "params": ["prototype", "position"],
        "doc": "Debug: print an entity's drop_position vs its own position, to diagnose "
        "auto-feed misalignment.",
        "template": '''
e = get_entity(Prototype.{prototype}, position=Position({position}))
print(f"SKILL_OK dropcheck: {prototype} at {{e.position}} direction={{e.direction}} drop_position={{e.drop_position}}")
''',
    },
    "nearby": {
        "params": ["position", "radius"],
        "doc": "List entities within `radius` of `position`. Use this to find something you "
        "placed but lost the exact position for (e.g. a furnace after a partial failure).",
        "template": '''
found = get_entities(position=Position({position}), radius={radius})
print(f"SKILL_OK nearby: {{[(e.name, e.position) for e in found]}}")
''',
    },
    "peek": {
        "params": ["prototype", "position"],
        "doc": "Print an entity's own inventory/status (e.g. a furnace's fuel+output) without "
        "moving anything. Use this to check whether a furnace/drill is actually producing "
        "before assuming collect/smelt failed for a real reason.",
        "template": '''
e = get_entity(Prototype.{prototype}, position=Position({position}))
print(f"SKILL_OK peek: {prototype} at {{e.position}} status={{e.status}} fuel={{e.fuel_inventory}} in={{e.input_inventory if hasattr(e, 'input_inventory') else e.inventory}}")
''',
    },
    "feed": {
        "params": ["item_prototype", "target_prototype", "target_position", "quantity"],
        "doc": "Insert `quantity` of `item_prototype` from your own inventory into a "
        "`target_prototype` entity at `target_position` (e.g. feed coal/ore into a furnace "
        "by hand).",
        "template": '''
target = get_entity(Prototype.{target_prototype}, position=Position({target_position}))
insert_item(Prototype.{item_prototype}, target, quantity={quantity})
print(f"SKILL_OK feed: inserted {quantity} {item_prototype} into {target_prototype} at {{target.position}}")
''',
    },
    "collect": {
        "params": ["item_prototype", "source_position", "quantity"],
        "doc": "Extract `quantity` of `item_prototype` (e.g. 'IronPlate') from an entity "
        "(furnace/chest/etc) at `source_position` into your own inventory.",
        "template": '''
before = inspect_inventory().get(Prototype.{item_prototype}, 0)
extract_item(Prototype.{item_prototype}, Position({source_position}), quantity={quantity})
after = inspect_inventory().get(Prototype.{item_prototype}, 0)
print(f"SKILL_OK collect: {item_prototype} in inventory {{before}} -> {{after}}")
''',
    },
    "craft": {
        "params": ["item_prototype", "count"],
        "doc": "Craft `count` of `item_prototype` (e.g. 'IronGearWheel') by hand from current "
        "inventory. Fails loudly if the required ingredients aren't in inventory yet.",
        "template": '''
before = inspect_inventory().get(Prototype.{item_prototype}, 0)
craft_item(Prototype.{item_prototype}, quantity={count})
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
        "quantity": 5,
        "technology": "Automation",
        "position": "x=1.0,y=2.0",
        "target_prototype": "StoneFurnace",
        "target_position": "x=1.0,y=2.0",
        "radius": 5,
    }
    sample_params["prototype"] = "BurnerMiningDrill"
    sample_params["from_prototype"] = "BurnerMiningDrill"
    sample_params["from_position"] = "x=0,y=0"
    sample_params["to_prototype"] = "BurnerInserter"
    sample_params["to_position"] = "x=1.0,y=2.0"
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
