#!/usr/bin/env python3
"""queue.py: keep the research queue on the rocket-silo path. Takes every unresearched tech the silo needs whose packs we
can make now (red, green, blue; add purple and yellow to PACKS when their tiles run), prerequisites first, cheapest first.
Prints the queue. Cheap RCON call, safe to run every pass."""
import factorio_rcon as f
PACKS = ["automation-science-pack", "logistic-science-pack", "chemical-science-pack", "production-science-pack", "utility-science-pack"]
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=30)
lua = """/silent-command local F=game.forces.player local ok={%s} local need={} local seen={}
local function walk(t) if seen[t.name] then return end seen[t.name]=true need[#need+1]=t for _,p in pairs(t.prerequisites) do walk(p) end end walk(F.technologies['rocket-silo'])
local function cost(t) return t.research_unit_count*#t.research_unit_ingredients end
local function makeable(t) for _,i in ipairs(t.research_unit_ingredients) do if not ok[i.name] then return false end end return true end
local q,inq={},{} local moved=true
while moved do moved=false local best
  for _,t in ipairs(need) do if not t.researched and not inq[t.name] and makeable(t) then local ready=true for _,p in pairs(t.prerequisites) do if not p.researched and not inq[p.name] then ready=false end end
    if ready and (not best or cost(t)<cost(best)) then best=t end end end
  if best then q[#q+1]=best.name inq[best.name]=true moved=true end end
F.research_queue=q rcon.print(#q..' queued: '..table.concat(q,' ',1,math.min(#q,12)))"""
print(c.send_command(lua % ",".join(f"['{p}']=true" for p in PACKS)))
