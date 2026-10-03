#!/usr/bin/env python3
"""acid.py: sulfuric acid plant beside the sulfur plant (sulfur by inserter, iron by chest, water from the existing 90-tile line), an underground acid
line north to a free field at x -24..-5, y -36..-27 (the old base fills everything nearer), and a row of four processing unit assemblers on it.
Inputs arrive by RCON item moves into the input chests (like the planner tiles), outputs collect in chests. Idempotent replay.
Ports were read from the game (fluidbox.get_pipe_connections), not guessed. ponytail: four assemblers, one acid plant."""
import factorio_rcon as f
import sys
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=60)
run = lambda l: c.send_command(" ".join(l.split("\n")))
FEED = """/silent-command local s=game.surfaces[1] local moved=0
local mine={} local want={}
local function chestAt(x,y) return s.find_entities_filtered{name='wooden-chest',position={x,y},radius=0.3}[1] end
local ironc=chestAt(-23.5,-8.5) if ironc then mine[#mine+1]=ironc want[#want+1]={ironc,'iron-plate',400} end
for _,x in ipairs{-22.5,-18.5,-14.5,-10.5} do local c=chestAt(x-1,-28.5) local o=chestAt(x+1,-28.5) if o then mine[#mine+1]=o end if c then mine[#mine+1]=c want[#want+1]={c,'electronic-circuit',800} want[#want+1]={c,'advanced-circuit',80} end end
local bc=chestAt(-17.5,-38.5) local bo=chestAt(-15.5,-38.5) if bo then mine[#mine+1]=bo end if bc then mine[#mine+1]=bc want[#want+1]={bc,'iron-plate',300} want[#want+1]={bc,'copper-plate',300} end
local function isMine(e) for _,m in ipairs(mine) do if m==e then return true end end return false end
for _,w in ipairs(want) do local c,item,cap=w[1],w[2],w[3] local have=c.get_inventory(defines.inventory.chest).get_item_count(item) local missing=cap-have
  if missing>0 then for _,e in pairs(s.find_entities_filtered{type={'container','furnace'},force='player'}) do if missing<=0 then break end
    if not isMine(e) then local inv=(e.type=='furnace') and e.get_output_inventory() or e.get_inventory(defines.inventory.chest) local h=inv.get_item_count(item)
      if h>0 then local n=c.insert{name=item,count=math.min(h,missing)} if n>0 then inv.remove{name=item,count=n} missing=missing-n moved=moved+n end end end end end end
rcon.print('acid feed moved '..moved)"""
if len(sys.argv) > 1 and sys.argv[1] == "feed":
    print(c.send_command(" ".join(FEED.split("\n")))); raise SystemExit
print(run("""/silent-command local s=game.surfaces[1] local d=defines.direction local F=game.forces.player local out={}
local function put(n,x,y,dir,rec) local e=s.find_entities_filtered{name=n,position={x,y},radius=0.3}[1]
  if not e then if not s.can_place_entity{name=n,position={x,y},direction=dir,force=F} then out[#out+1]='BLOCKED '..n..' '..x..','..y return nil end
    e=s.create_entity{name=n,position={x,y},direction=dir,force=F} end
  if e and rec and e.get_recipe()==nil then e.set_recipe(rec) end
  if e and rec and dir and e.direction~=dir then e.direction=dir end return e end
put('chemical-plant',-26.5,-8.5,d.south,'sulfuric-acid')
put('pipe',-28.5,-6.5) put('pipe',-27.5,-6.5)
put('inserter',-28.5,-8.5,d.west)
put('inserter',-24.5,-8.5,d.east) put('wooden-chest',-23.5,-8.5)
put('pipe',-27.5,-10.5)
put('medium-electric-pole',-28.5,-11.5) put('medium-electric-pole',-24.5,-11.5)
local y=-11.5 local hops=0
while y>-29 and hops<8 do
  local a=put('pipe-to-ground',-27.5,y,d.south) if not a then break end
  local ok=false
  for L=10,2,-1 do local ny=y-L
    local b=s.find_entities_filtered{name='pipe-to-ground',position={-27.5,ny},radius=0.3}[1]
    if b or s.can_place_entity{name='pipe-to-ground',position={-27.5,ny},direction=d.north,force=F} then
      put('pipe-to-ground',-27.5,ny,d.north) y=ny-1 ok=true break end end
  if not ok then out[#out+1]='no free hop after y='..y break end hops=hops+1 end
out[#out+1]='line reached y='..y..' hops='..hops
local ty=-33.5
for x=-27.5,-9.5 do put('pipe',x,ty) end
for _,x in ipairs{-22.5,-18.5,-14.5,-10.5} do
  put('assembling-machine-2',x,-31.5,d.north,'processing-unit')
  put('inserter',x-1,-29.5,d.south) put('wooden-chest',x-1,-28.5)
  put('inserter',x+1,-29.5,d.north) put('wooden-chest',x+1,-28.5)
  put('medium-electric-pole',x+2,-31.5)
end
put('medium-electric-pole',-24.5,-31.5)
put('chemical-plant',-16.5,-35.5,d.south,'battery')
put('inserter',-17.5,-37.5,d.north) put('wooden-chest',-17.5,-38.5)
put('inserter',-15.5,-37.5,d.south) put('wooden-chest',-15.5,-38.5)
put('medium-electric-pole',-13.5,-36.5)
local first=s.find_entities_filtered{name='medium-electric-pole',position={-24.5,-31.5},radius=0.3}[1]
local best,bd
for _,e in pairs(s.find_entities_filtered{type='electric-pole',position={-24.5,-31.5},radius=60,force=F}) do if e.electric_network_id==22 then local dd=(e.position.x+24.5)^2+(e.position.y+31.5)^2 if dd>16 and (not bd or dd<bd) then best,bd=e,dd end end end
local made=0 if best and first then local n=math.ceil(math.sqrt(bd)/7) for k=1,n-1 do local x=math.floor(first.position.x+(best.position.x-first.position.x)*k/n)+0.5 local y=math.floor(first.position.y+(best.position.y-first.position.y)*k/n)+0.5 for dy=0,3 do if s.can_place_entity{name='medium-electric-pole',position={x,y+dy},force=F} then s.create_entity{name='medium-electric-pole',position={x,y+dy},force=F} made=made+1 break end end end end
out[#out+1]='bridge poles '..made
local cx,cy=-28.5,-11.5 local tx0,ty0=-24.5,-31.5
for step=1,6 do local dd=math.sqrt((tx0-cx)^2+(ty0-cy)^2) if dd<=8 then break end
  local px,py=cx+(tx0-cx)/dd*7,cy+(ty0-cy)/dd*7 local placed=false
  for r=0,3 do for dx=-r,r do for dy=-r,r do if not placed then local qx,qy=math.floor(px+dx)+0.5,math.floor(py+dy)+0.5
    local ex=s.find_entities_filtered{name='medium-electric-pole',position={qx,qy},radius=0.3}[1]
    if ex or s.can_place_entity{name='medium-electric-pole',position={qx,qy},force=F} then if not ex then s.create_entity{name='medium-electric-pole',position={qx,qy},force=F} end cx,cy=qx,qy placed=true end end end end end
  if not placed then out[#out+1]='pole chain stuck at '..cx..','..cy break end end
local m={} for k,v in pairs(defines.entity_status) do m[v]=k end
local acid=s.find_entities_filtered{name='chemical-plant',position={-26.5,-8.5},radius=0.5}[1]
if acid then local fl={} for i=1,#acid.fluidbox do local b=acid.fluidbox[i] fl[#fl+1]=b and (b.name..'='..math.floor(b.amount)) or '-' end out[#out+1]='acid '..(m[acid.status] or '?')..' fluids '..table.concat(fl,' ') end
local a1=s.find_entities_filtered{name='assembling-machine-2',position={-22.5,-31.5},radius=0.5}[1]
if a1 then out[#out+1]='pu1 '..(m[a1.status] or '?')..' net '..tostring(a1.electric_network_id)..' acid '..(a1.fluidbox[1] and (a1.fluidbox[1].name..'='..math.floor(a1.fluidbox[1].amount)) or '-') end
local bp=s.find_entities_filtered{name='chemical-plant',position={-16.5,-35.5},radius=0.5}[1] if bp then local fl={} for i=1,#bp.fluidbox do local b=bp.fluidbox[i] fl[#fl+1]=b and (b.name..'='..math.floor(b.amount)) or '-' end out[#out+1]='battery '..(m[bp.status] or '?')..' net '..tostring(bp.electric_network_id)..' '..table.concat(fl,' ') end
rcon.print(table.concat(out,' | '))"""))
