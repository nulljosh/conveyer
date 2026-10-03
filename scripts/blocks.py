#!/usr/bin/env python3
"""blocks.py: build helpers so a new factory block is a few calls instead of hand-edited coordinates.
Every call is one RCON round trip. The Lua prelude gives: put (place or reuse, force direction, set recipe), ports (read an entity's fluid
connections from the game), power (make sure a medium pole reaches a spot and chain it to net 22), status (machine and inserter status, so an
unpowered inserter shows up at once), and pipe (breadth-first pipe route that refuses to touch another fluid's pipe).
Lessons baked in: an inserter's direction is the side it picks from; assemblers need direction set after create; a medium pole powers 3.5 tiles
each way; never put -- comments in joined Lua. ponytail: surface pipes only, 90x90 search box, one fluid per route."""
import factorio_rcon as f

PRELUDE = """local s=game.surfaces[1] local d=defines.direction local F=game.forces.player local out={}
local M={} for k,v in pairs(defines.entity_status) do M[v]=k end
local function put(n,x,y,dir,rec) local e=s.find_entities_filtered{name=n,position={x,y},radius=0.3}[1]
  if not e then if not s.can_place_entity{name=n,position={x,y},direction=dir,force=F} then out[#out+1]='BLOCKED '..n..' '..x..','..y return nil end
    e=s.create_entity{name=n,position={x,y},direction=dir,force=F} end
  if e and rec and e.get_recipe()==nil then e.set_recipe(rec) end
  if e and dir and e.direction~=dir and (rec or e.type=='inserter') then e.direction=dir end return e end
local function power(x,y) local near=s.find_entities_filtered{type='electric-pole',position={x,y},radius=3.4,force=F}[1] if near then return near end
  for r=0,3 do for dx=-r,r do for dy=-r,r do local px,py=math.floor(x+dx)+0.5,math.floor(y+dy)+0.5 if s.can_place_entity{name='medium-electric-pole',position={px,py},force=F} then local p=s.create_entity{name='medium-electric-pole',position={px,py},force=F}
    local best,bd for _,e in pairs(s.find_entities_filtered{type='electric-pole',position={px,py},radius=60,force=F}) do if e~=p and e.electric_network_id==22 then local dd=(e.position.x-px)^2+(e.position.y-py)^2 if not bd or dd<bd then best,bd=e,dd end end end
    if best then local cx,cy=px,py for k=1,8 do local dist=math.sqrt((best.position.x-cx)^2+(best.position.y-cy)^2) if dist<=8.5 then break end local nx,ny=cx+(best.position.x-cx)/dist*7,cy+(best.position.y-cy)/dist*7 local placed=false
      for r2=0,3 do for ex=-r2,r2 do for ey=-r2,r2 do if not placed then local qx,qy=math.floor(nx+ex)+0.5,math.floor(ny+ey)+0.5 if s.can_place_entity{name='medium-electric-pole',position={qx,qy},force=F} then s.create_entity{name='medium-electric-pole',position={qx,qy},force=F} cx,cy=qx,qy placed=true end end end end end
      if not placed then break end end end return p end end end end return nil end
local function st(e) if not e then return 'missing' end return M[e.status] or '?' end
"""

class Site:
    def __init__(self, timeout=90):
        self.c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=timeout)

    def run(self, body):
        """Run Lua with the prelude; the body ends with rcon.print(table.concat(out,' | ')) unless it prints itself."""
        src = "/silent-command " + PRELUDE + body
        return self.c.send_command(" ".join(src.split("\n")))

    def ports(self, name, direction, recipe=None, x=0.5, y=0.5):
        """Fluid ports of an entity as the game reports them: 'box flow dx,dy' relative to its center, read from a throwaway copy far away."""
        r = self.run("""local e=s.create_entity{name='%s',position={%g,%g},direction=%d,force=F}
if not e then rcon.print('cannot place') return end
%s
local o={} for i=1,#e.fluidbox do for _,c in ipairs(e.fluidbox.get_pipe_connections(i)) do o[#o+1]=i..' '..tostring(c.flow_direction)..' '..string.format('%%.1f,%%.1f',c.target_position.x-e.position.x,c.target_position.y-e.position.y) end end
e.destroy() rcon.print(table.concat(o,' | '))""" % (name, x, y, direction, ("e.set_recipe('%s')" % recipe) if recipe else ""))
        return r

    def free_spot(self, w, h, near, maxr=90, step=4):
        """Nearest clear w by h rectangle (no entities, no water) to near; returns 'x,y' of its top-left corner or 'none'."""
        return self.run("""local W,H=%d,%d local best
local function free(x1,y1,x2,y2) return s.count_entities_filtered{area={{x1,y1},{x2,y2}}}==0 and s.count_tiles_filtered{area={{x1,y1},{x2,y2}},name={'water','deepwater','water-green','deepwater-green','water-shallow','water-mud'}}==0 end
for r=0,%d,%d do for dx=-r,r,%d do for _,dy in ipairs{-r,r} do local x,y=%g+dx,%g+dy if not best and free(x,y,x+W,y+H) then best={x,y} end end end
  for dy=-r,r,%d do for _,dx in ipairs{-r,r} do local x,y=%g+dx,%g+dy if not best and free(x,y,x+W,y+H) then best={x,y} end end end end
rcon.print(best and (best[1]..','..best[2]) or 'none')""" % (w, h, maxr, step, step, near[0], near[1], step, near[0], near[1]))

    def pipe(self, start, goal_fluid_near, avoid_names=("pipe", "pipe-to-ground")):
        """Route pipes from start (x,y, a free tile or an existing pipe) to the first existing pipe whose network holds the same fluid as the pipe at
        goal_fluid_near. Never lets a new pipe touch a pipe of a different fluid. Returns the number of pipes placed or an error."""
        return self.run("""local function pat(x,y) return s.find_entities_filtered{name={'pipe','pipe-to-ground'},position={x,y},radius=0.3}[1] end
local sx,sy=%g,%g local gx,gy=%g,%g local goal=pat(gx,gy) if not goal then rcon.print('no goal pipe') return end
local gseg=goal.fluidbox.get_fluid_segment_id(1) local gfluid=goal.fluidbox[1] and goal.fluidbox[1].name
local function key(x,y) return x..','..y end
local function foreign(x,y) for _,dd in ipairs{{1,0},{-1,0},{0,1},{0,-1}} do local n=pat(x+dd[1],y+dd[2]) if n and n.fluidbox.get_fluid_segment_id(1)~=gseg then local nf=n.fluidbox[1] if nf and gfluid and nf.name~=gfluid then return true end end end return false end
local q={{sx,sy}} local seen={[key(sx,sy)]=true} local prev={} local head=1 local found
while head<=#q and not found do local cur=q[head] head=head+1
  for _,dd in ipairs{{1,0},{-1,0},{0,1},{0,-1}} do local nx,ny=cur[1]+dd[1],cur[2]+dd[2]
    if math.abs(nx-sx)<=45 and math.abs(ny-sy)<=45 and not seen[key(nx,ny)] then local pe=pat(nx,ny)
      if pe and pe.fluidbox.get_fluid_segment_id(1)==gseg then prev[key(nx,ny)]=cur found={nx,ny} break end
      if not pe and s.can_place_entity{name='pipe',position={nx,ny},force=F} and not foreign(nx,ny) then seen[key(nx,ny)]=true prev[key(nx,ny)]=cur q[#q+1]={nx,ny} end end end end
if not found then rcon.print('NO PATH') return end
local n=0 local cur=prev[key(found[1],found[2])] while cur do if not pat(cur[1],cur[2]) then s.create_entity{name='pipe',position={cur[1],cur[2]},force=F} n=n+1 end cur=prev[key(cur[1],cur[2])] end
rcon.print('piped '..n)""" % (start[0], start[1], goal_fluid_near[0], goal_fluid_near[1]))

if __name__ == "__main__":
    s = Site()
    print("AM2 north:", s.ports("assembling-machine-2", 0, "processing-unit"))
    print("refinery north:", s.ports("oil-refinery", 0, "basic-oil-processing", x=0.0, y=0.0))
