#!/usr/bin/env python3
"""acid.py: sulfuric acid plant beside the sulfur plant (sulfur by inserter, iron by chest, water from the existing 90-tile line), an underground acid
line north to a free field at x -24..-5, y -36..-27 (the old base fills everything nearer), and a row of four processing unit assemblers on it.
Inputs arrive by RCON item moves into the input chests (like the planner tiles), outputs collect in chests. Idempotent replay.
Ports were read from the game (fluidbox.get_pipe_connections), not guessed. ponytail: four assemblers, one acid plant."""
import factorio_rcon as f
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=60)
run = lambda l: c.send_command(" ".join(l.split("\n")))
print(run("""/silent-command local s=game.surfaces[1] local d=defines.direction local F=game.forces.player local out={}
local function put(n,x,y,dir,rec) local e=s.find_entities_filtered{name=n,position={x,y},radius=0.3}[1]
  if not e then if not s.can_place_entity{name=n,position={x,y},direction=dir,force=F} then out[#out+1]='BLOCKED '..n..' '..x..','..y return nil end
    e=s.create_entity{name=n,position={x,y},direction=dir,force=F} end
  if e and rec and e.get_recipe()==nil then e.set_recipe(rec) end return e end
put('chemical-plant',-26.5,-8.5,d.south,'sulfuric-acid')
put('pipe',-28.5,-6.5) put('pipe',-27.5,-6.5)
put('inserter',-28.5,-8.5,d.east)
put('inserter',-24.5,-8.5,d.west) put('wooden-chest',-23.5,-8.5)
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
rcon.print(table.concat(out,' | '))"""))
