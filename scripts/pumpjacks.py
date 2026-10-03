#!/usr/bin/env python3
"""pumpjacks.py: more crude. One pumpjack at 44% yield fed the whole refinery (crude 14 of 200, gas starved plastic, sulfur and acid). This puts
pumpjacks on the four richer wells beside it (191, 133, 143 and 196 percent) and pipes each output into the existing underground line by
breadth-first search over free tiles. Idempotent replay: pumpjacks are found by position, pipes only fill gaps.
Pumpjack facing: its output tile is read from the game (fluidbox.get_pipe_connections), not guessed. ponytail: surface pipes only, no undergrounds."""
import factorio_rcon as f
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=120)
run = lambda l: c.send_command(" ".join(l.split("\n")))
print(run("""/silent-command local s=game.surfaces[1] local d=defines.direction local F=game.forces.player local o={}
local e1=s.find_entities_filtered{name='pipe-to-ground',position={270.5,86.5},radius=0.3}[1]
if e1 then e1.destroy() end
local jn=s.find_entities_filtered{name='pipe',position={270.5,86.5},radius=0.3}[1] or s.create_entity{name='pipe',position={270.5,86.5},force=F}
if not (s.find_entities_filtered{name='pipe-to-ground',position={269.5,86.5},radius=0.3}[1]) then s.create_entity{name='pipe-to-ground',position={269.5,86.5},direction=d.east,force=F} end
local function key(x,y) return x..','..y end
local function pipeAt(x,y) return s.find_entities_filtered{name={'pipe','pipe-to-ground'},position={x,y},radius=0.3}[1] end
local function bfs(sx,sy)
  local q={{sx,sy}} local seen={[key(sx,sy)]=true} local prev={} local head=1
  while head<=#q do local cur=q[head] head=head+1 local x,y=cur[1],cur[2]
    local tp=pipeAt(x,y)
    if tp and not (x==sx and y==sy) then local path={} local k=key(x,y) local px,py=x,y
      while prev[k] do local pr=prev[k] path[#path+1]={pr[1],pr[2]} k=key(pr[1],pr[2]) end return path end
    for _,dd in ipairs{{1,0},{-1,0},{0,1},{0,-1}} do local nx,ny=x+dd[1],y+dd[2]
      if nx>=262 and nx<=292 and ny>=64 and ny<=98 and not seen[key(nx,ny)] then
        if pipeAt(nx,ny) or s.can_place_entity{name='pipe',position={nx,ny},force=F} then seen[key(nx,ny)]=true prev[key(nx,ny)]={x,y} q[#q+1]={nx,ny} end end end end
  return nil end
for _,w in ipairs{{276,83},{276,89},{279,75},{284,80}} do
  local r=s.find_entities_filtered{name='crude-oil',position={w[1],w[2]},radius=2}[1]
  if r then
    local e=s.find_entities_filtered{name='pumpjack',position=r.position,radius=1}[1] or s.create_entity{name='pumpjack',position=r.position,direction=d.north,force=F}
    if e then local cc=e.fluidbox.get_pipe_connections(1)[1] local ox,oy=cc.target_position.x,cc.target_position.y
      if not pipeAt(ox,oy) then if s.can_place_entity{name='pipe',position={ox,oy},force=F} then s.create_entity{name='pipe',position={ox,oy},force=F} end end
      local path=bfs(ox,oy)
      if path then local n=0 for _,p in ipairs(path) do if not pipeAt(p[1],p[2]) then s.create_entity{name='pipe',position={p[1],p[2]},force=F} n=n+1 end end o[#o+1]='pj '..r.position.x..','..r.position.y..' piped '..n..' tiles'
      else o[#o+1]='pj '..r.position.x..','..r.position.y..' NO PATH' end end end end
local m={} for k,v in pairs(defines.entity_status) do m[v]=k end
for _,e in pairs(s.find_entities_filtered{name='pumpjack'}) do o[#o+1]=string.format('%.0f,%.0f %s net %s',e.position.x,e.position.y,m[e.status] or '?',tostring(e.electric_network_id)) end
rcon.print(table.concat(o,' | '))"""))
