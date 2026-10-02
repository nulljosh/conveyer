#!/usr/bin/env python3
"""ironfarm.py [N]: electric drill -> steel furnace -> inserter -> chest, N slots on the west iron patch. Idempotent replay.
Iron plate is the raw bottleneck (chests held 581 iron against 6,972 copper). Slots land in .world/ironfarm.json so a
reverted world is rebuilt by rerunning this with no scan. Layout per slot (dx,dy = drill top-left tile): drill 3x3 at
(dx+.5,dy+.5) drops north into a 2x2 steel furnace at (dx+1,dy-2); an inserter at (dx+.5,dy-3.5) empties it into a
wooden chest at (dx+.5,dy-4.5); a medium pole in the tile beside every furnace.
ponytail: slots are scanned once from ore tiles then frozen in json; rescan only by deleting the file."""
import json, sys, pathlib, factorio_rcon as f
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=90)
run = lambda l: c.send_command(" ".join(l.split("\n")))
FILE = pathlib.Path(".world/ironfarm.json")
N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 16
X0, Y0, X1, Y1 = -258, -130, -222, -62   # west patch: 1.5M + 1.1M + 0.6M ore; the near patch is already built over
AREA = "{{%d,%d},{%d,%d}}" % (X0, Y0, X1, Y1)

def scan():
    out = run("/silent-command local t={} for _,r in pairs(game.surfaces[1].find_entities_filtered{name='iron-ore',area=%s}) do t[#t+1]=math.floor(r.position.x)..','..math.floor(r.position.y) end rcon.print(table.concat(t,' '))" % AREA)
    ore = {tuple(map(int, p.split(","))) for p in out.split()}
    slots = []
    for dy in range(Y0 + 6, Y1 - 4, 8):                      # row pitch 8: 7 tall plus a spare tile
        for dx in range(X0 + 2, X1 - 3, 3):
            n = sum((x, y) in ore for x in range(dx - 1, dx + 4) for y in range(dy - 1, dy + 4))
            if n >= 9: slots.append((n, dx, dy))
    return [(dx, dy) for _, dx, dy in sorted(slots, reverse=True)]

LUA = """/silent-command local s=game.surfaces[1] local d=defines.direction local ok={} local bad=0
local function can(n,x,y,dir) return s.can_place_entity{name=n,position={x,y},direction=dir,force='player'} end
local function have(n,x,y) return s.find_entities_filtered{name=n,position={x,y},radius=0.4}[1] end
local function put(n,x,y,dir) return have(n,x,y) or s.create_entity{name=n,position={x,y},direction=dir,force='player'} end
for i,p in ipairs(%s) do local dx,dy=p[1],p[2]
  local done=have('electric-mining-drill',dx+.5,dy+.5)
  if done or (can('electric-mining-drill',dx+.5,dy+.5,d.north) and can('steel-furnace',dx+1,dy-2) and can('inserter',dx+.5,dy-3.5,d.north) and can('wooden-chest',dx+.5,dy-4.5)) then
    put('electric-mining-drill',dx+.5,dy+.5,d.north) put('steel-furnace',dx+1,dy-2) local ins=put('inserter',dx+.5,dy-3.5,d.north) put('wooden-chest',dx+.5,dy-4.5)
    if ins and (ins.drop_position.y>dy-3.5) then ins.direction=d.south end
    put('medium-electric-pole',dx+2.5,dy-2.5)
    ok[#ok+1]=dx..','..dy else bad=bad+1 end end
local m={} for k,v in pairs(defines.entity_status) do m[v]=k end local st={}
for _,e in pairs(s.find_entities_filtered{name='electric-mining-drill',area=%s}) do st[m[e.status] or '?']=(st[m[e.status] or '?'] or 0)+1 end
rcon.print(helpers.table_to_json({ok=ok,bad=bad,drills=st}))"""

def bridge():
    """medium poles every 8.5 tiles from the main grid to the west outpost, so the farm shares the 9 MW grid instead of the lone outpost boiler"""
    return run("""/silent-command local s=game.surfaces[1] local a={-144.5,-29.5} local b={-222.5,-89.5} local L=math.sqrt((b[1]-a[1])^2+(b[2]-a[2])^2) local n=math.ceil(L/8)-1 local made=0 if #s.find_entities_filtered{name='medium-electric-pole',position={-146.5,-31.5},radius=0.5}==0 then s.create_entity{name='medium-electric-pole',position={-146.5,-31.5},force='player'} made=made+1 end -- first hop from the main small pole was 7.8 tiles, over its 7.5 reach
for i=1,n do local x=a[1]+(b[1]-a[1])*i/(n+1) local y=a[2]+(b[2]-a[2])*i/(n+1) x=math.floor(x)+.5 y=math.floor(y)+.5
  local p=s.find_non_colliding_position('medium-electric-pole',{x,y},3,1) or {x,y}
  if #s.find_entities_filtered{name='medium-electric-pole',position=p,radius=0.5}==0 then s.create_entity{name='medium-electric-pole',position=p,force='player'} made=made+1 end end
local e=s.find_entities_filtered{name='electric-mining-drill',area={{-258,-130},{-222,-62}}}[1] rcon.print('bridge poles +'..made..' outpost net='..tostring(e.electric_network_id))""")

if len(sys.argv) > 1 and sys.argv[1] == "bridge": sys.exit(print(bridge()))
print(bridge())  # idempotent; keeps replay one command
slots = json.loads(FILE.read_text()) if FILE.exists() else scan()
raw = run(LUA % (json.dumps(slots[:N] if not FILE.exists() else slots).replace("[", "{").replace("]", "}"), AREA))
if not raw.startswith("{"): sys.exit(raw[:400])
res = json.loads(raw)
if not FILE.exists() and res["ok"]: FILE.write_text(json.dumps([list(map(int, s.split(","))) for s in res["ok"]]))
print(f"placed {len(res['ok'])} slots, {res['bad']} blocked, drills {res['drills']}")
