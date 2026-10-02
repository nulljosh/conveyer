#!/usr/bin/env python3
"""labs.py [N]: grow to N labs (default 12) on a free grid near the first three, a medium pole in every gap. Idempotent.
Three labs were the research wall: the silo path is about 150k lab-seconds, and the packs are fed by RCON so lab count is free.
a pole at (-47.5,-48.5) joins the corner lab, 10 tiles from the grid, one hop short. ponytail: grid scan each run, no json; labs are cheap to find again."""
import sys, factorio_rcon as f
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=60)
print(c.send_command(" ".join("""/silent-command local s=game.surfaces[1] local want=%d local have=#s.find_entities_filtered{name='lab'} local made=0
for y=-50.5,-26.5,3 do for x=-84.5,-44.5,4 do if have+made<want then
  local lab=s.find_entities_filtered{name='lab',position={x,y},radius=0.4}[1]
  if not lab and s.can_place_entity{name='lab',position={x,y},force='player'} and s.can_place_entity{name='medium-electric-pole',position={x+2,y},force='player'} then
    s.create_entity{name='lab',position={x,y},force='player'} s.create_entity{name='medium-electric-pole',position={x+2,y},force='player'} made=made+1 end end end end
if #s.find_entities_filtered{name='medium-electric-pole',position={-47.5,-48.5},radius=0.4}==0 and s.can_place_entity{name='medium-electric-pole',position={-47.5,-48.5},force='player'} then s.create_entity{name='medium-electric-pole',position={-47.5,-48.5},force='player'} end
local n=0 local nets={} for _,l in pairs(s.find_entities_filtered{name='lab'}) do n=n+1 nets[tostring(l.electric_network_id)]=(nets[tostring(l.electric_network_id)] or 0)+1 end
rcon.print('labs '..n..' (+'..made..') nets '..serpent.line(nets))""".split("\n")) % N))
