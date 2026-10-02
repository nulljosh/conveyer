#!/usr/bin/env python3
"""planner.py status | step | replay | labs
A small self-expanding factory, after the tile-and-demand idea in Chris Uehlinger's "Factorio Automated" video.
Tile = one assembler-2 with an input chest and an output chest. Tier(item) = 1 + highest tier of its ingredients (plates are tier 0).
Demand: a target item wants N in stock; the lowest-tier ingredient with no tile yet gets built first, one tile per step.
Logistics stand-in: supply() moves items between chests over RCON, the way bots would. The plan lives in .world/tiles.json,
so after a crash (the world reverts) `replay` rebuilds every tile.
ponytail: create_entity is free (no assembler items spent) and supply() teleports items; swap for bots once robotics is researched."""
import json, sys
from pathlib import Path
import factorio_rcon as f

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / ".world" / "tiles.json"
TARGETS = {"automation-science-pack": 300, "logistic-science-pack": 300}
RAW = {"iron-plate", "copper-plate", "steel-plate", "stone-brick", "coal", "plastic-bar", "sulfur"}
OX, OY, CW, CH, COLS = -28, 4, 9, 6, 3  # tile grid origin and cell size; cells that can't hold a tile are skipped
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=60)
run = lambda lua: c.send_command(" ".join(lua.split("\n")))

def recipes(item):
    """Closure of {item: {ingredient: amount}} down to the raw plates, read from the live game."""
    out = run("""/silent-command local R=game.forces.player.recipes local o={} local raw={%s}
    local function walk(n) if o[n] or raw[n] then return end local r=R[n] if not r then return end local ing={} for _,i in pairs(r.ingredients) do ing[i.name]=i.amount walk(i.name) end
    o[n]={ing=ing,out=r.products[1].amount} end walk('%s') rcon.print(helpers.table_to_json(o))""" % (",".join(f"['{r}']=true" for r in RAW), item))
    return json.loads(out)

def tiers(rec):
    t = {}
    def tier(n):
        if n in RAW or n not in rec: return 0
        if n not in t: t[n] = 1 + max([tier(i) for i in rec[n]["ing"]] or [0])
        return t[n]
    for n in rec: tier(n)
    return t

def load(): return json.loads(PLAN.read_text()) if PLAN.exists() else []
def save(p): PLAN.parent.mkdir(exist_ok=True); PLAN.write_text(json.dumps(p, indent=1))

PLACE = """/silent-command local s=game.surfaces[1] local d=defines.direction local ox,oy=%d,%d local out={}
local function put(n,x,y,dir) local e=s.find_entities_filtered{name=n,position={x,y},radius=0.2}[1] if e then return e end
  e=s.create_entity{name=n,position={x,y},direction=dir,force='player'} if not e then out[#out+1]='FAIL '..n..' '..x..','..y end return e end
if not s.can_place_entity{name='assembling-machine-2',position={ox+3.5,oy+1.5},force='player'} and #s.find_entities_filtered{name='assembling-machine-2',position={ox+3.5,oy+1.5},radius=0.2}==0 then rcon.print('BLOCKED') return end
local a=put('assembling-machine-2',ox+3.5,oy+1.5) if a and a.get_recipe()==nil then a.set_recipe('%s') end
put('wooden-chest',ox+0.5,oy+1.5) put('wooden-chest',ox+6.5,oy+1.5)
for _,x in ipairs{ox+1.5,ox+5.5} do for _,old in pairs(s.find_entities_filtered{name='inserter',position={x,oy+1.5},radius=0.2}) do old.destroy() end local i=put('fast-inserter',x,oy+1.5,d.east) if i and i.drop_position.x<i.position.x then i.direction=(i.direction+8)%%16 end end
local p=put('medium-electric-pole',ox+3.5,oy+3.5)
local lab=s.find_entities_filtered{name='lab'}[1] local main=lab and lab.electric_network_id
if p and main and p.electric_network_id~=main then
  local best,bd=nil,1e9 for _,q in pairs(s.find_entities_filtered{type='electric-pole',position=p.position,radius=45}) do if q.electric_network_id==main then local dd=((q.position.x-p.position.x)^2+(q.position.y-p.position.y)^2)^0.5 if dd<bd then best,bd=q,dd end end end
  if best then local n=math.ceil(bd/8) for k=1,n-1 do local x=math.floor(p.position.x+(best.position.x-p.position.x)*k/n)+0.5 local y=math.floor(p.position.y+(best.position.y-p.position.y)*k/n)+0.5
    for dy=0,3 do if s.can_place_entity{name='medium-electric-pole',position={x,y+dy},force='player'} then s.create_entity{name='medium-electric-pole',position={x,y+dy},force='player'} break end end end end
end
rcon.print('placed '..table.concat(out,' ')..' net='..tostring(a and a.electric_network_id)..' main='..tostring(main))"""

def place(item, cell):
    ox, oy = OX + (cell % COLS) * CW, OY + (cell // COLS) * CH
    return run(PLACE % (ox, oy, item)), ox, oy

SUPPLY = """/silent-command local s=game.surfaces[1] local want=%s local ins={%s} local outs={%s} local moved={}
local function stock(name) local n=0 for _,e in pairs(s.find_entities_filtered{type='container',force='player'}) do n=n+e.get_inventory(defines.inventory.chest).get_item_count(name) end return n end
for _,t in ipairs(ins) do local chest=s.find_entities_filtered{name='wooden-chest',position=t.p,radius=0.2}[1]
  local oc=s.find_entities_filtered{name='wooden-chest',position=t.o,radius=0.2}[1]
  if oc and oc.get_inventory(defines.inventory.chest).get_item_count(t.item)>=t.cap then chest=nil end
  if chest then for item,amt in pairs(t.need) do local have=chest.get_inventory(defines.inventory.chest).get_item_count(item) local missing=amt-have
    if missing>0 then for _,e in pairs(s.find_entities_filtered{type={'container','furnace'},force='player'}) do if missing<=0 then break end
      local isinput=false for _,q in ipairs(ins) do if math.abs(q.p[1]-e.position.x)<0.2 and math.abs(q.p[2]-e.position.y)<0.2 then isinput=true end end
      if not isinput then local inv=(e.type=='furnace') and e.get_output_inventory() or e.get_inventory(defines.inventory.chest) local h=inv.get_item_count(item)
        if h>0 then local n=chest.insert{name=item,count=math.min(h,missing)} if n>0 then inv.remove{name=item,count=n} missing=missing-n moved[#moved+1]=item..'+'..n end end end end
    if missing>0 then local bag=s.find_entities_filtered{type='character'}[1].get_main_inventory() local h=bag.get_item_count(item) if h>0 then local n=chest.insert{name=item,count=math.min(h,missing)} if n>0 then bag.remove{name=item,count=n} moved[#moved+1]=item..'+'..n..'(bag)' end end end end end end end
rcon.print(table.concat(moved,' '))"""

def supply(plan, rec):
    ins, outs = [], []
    for t in plan:
        ox, oy = OX + (t["cell"] % COLS) * CW, OY + (t["cell"] // COLS) * CH
        need = {i: a * 100 for i, a in rec[t["item"]]["ing"].items()}  # 100 crafts of every ingredient on hand
        cap = 400 if t["item"] in TARGETS else 200  # demand: a tile holding this much of its product stops being fed
        ins.append("{p={%g,%g},o={%g,%g},item='%s',cap=%d,need={%s}}" % (ox + 0.5, oy + 1.5, ox + 6.5, oy + 1.5, t["item"], cap, ",".join(f"['{k}']={v}" for k, v in need.items())))
    return run(SUPPLY % ("{}", ",".join(ins), "")) if ins else ""

STOCK = """/silent-command local s=game.surfaces[1] local o={} for _,n in ipairs{%s} do local k=0 for _,e in pairs(s.find_entities_filtered{type='container',force='player'}) do k=k+e.get_inventory(defines.inventory.chest).get_item_count(n) end o[#o+1]=n..'='..k end rcon.print(table.concat(o,' '))"""

def stock(items):
    return dict((kv.split("=")[0], int(kv.split("=")[1])) for kv in run(STOCK % ",".join(f"'{i}'" for i in items)).split())

def build_order():
    rec = {}
    for tgt in TARGETS: rec.update(recipes(tgt))
    return rec, tiers(rec)

def step():
    rec, tr = build_order(); plan = load(); have = {t["item"] for t in plan}
    missing = sorted((i for i in rec if i not in have), key=lambda i: tr[i])  # lowest tier first
    if missing:
        item = missing[0]; cell = len(plan)
        while True:
            res, ox, oy = place(item, cell)
            if res.startswith("BLOCKED"): cell += 1; continue
            break
        plan.append({"item": item, "cell": cell}); save(plan)
        print(f"built {item} (tier {tr[item]}) at cell {cell}: {res}")
    print("supplied:", supply(plan, rec) or "nothing to move")
    print("stock:", stock(list(TARGETS) + list(rec)))
    return bool(missing)

def replay():
    rec, tr = build_order()
    for t in load():
        res, _, _ = place(t["item"], t["cell"]); print(t["item"], res)
    print("supplied:", supply(load(), rec) or "nothing to move")

LABS = """/silent-command local s=game.surfaces[1] local inv=s.find_entities_filtered{type='character'}[1].get_main_inventory() local o={}
for _,n in ipairs{'automation-science-pack','logistic-science-pack'} do for _,e in pairs(s.find_entities_filtered{type='container',force='player'}) do
  local ci=e.get_inventory(defines.inventory.chest) local h=ci.get_item_count(n) if h>0 then local k=inv.insert{name=n,count=h} if k>0 then ci.remove{name=n,count=k} o[#o+1]=n..'+'..k end end end end rcon.print(table.concat(o,' '))"""

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "step": step()
    elif cmd == "replay": replay()
    elif cmd == "labs": print(run(LABS) or "no packs in chests")
    else:
        rec, tr = build_order(); print("tiers:", {k: tr[k] for k in sorted(tr, key=tr.get)}); print("plan:", load()); print("stock:", stock(list(TARGETS) + list(rec)))
