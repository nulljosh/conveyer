#!/usr/bin/env python3
"""ASSISTED silo launch. Finds clear ground near the powered base, creates a rocket-silo plus a pole, adds 100 rocket parts and a satellite
through RCON, launches, and prints rockets_launched. Run with `dry` to only find a spot. Everything it does is console-assisted and is labeled that way."""
import sys, factorio_rcon as f
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=60)
DRY = len(sys.argv) > 1 and sys.argv[1] == "dry"
LUA = """/silent-command local s=game.surfaces[1] local F=game.forces.player local spot
for r=12,90,6 do for dx=-r,r,6 do for _,dy in ipairs{-r,r} do local x,y=-40+dx,-8+dy if not spot and s.can_place_entity{name='rocket-silo',position={x+0.5,y+0.5},force=F} then spot={x+0.5,y+0.5} end end end end
if not spot then rcon.print('no spot') return end
if %s then rcon.print('spot '..spot[1]..','..spot[2]) return end
local silo=s.create_entity{name='rocket-silo',position=spot,force=F}
local pole
for dy=-6,6 do for _,dx in ipairs{-6,6} do if not pole and s.can_place_entity{name='medium-electric-pole',position={spot[1]+dx,spot[2]+dy},force=F} then pole=s.create_entity{name='medium-electric-pole',position={spot[1]+dx,spot[2]+dy},force=F} end end end
local near=s.find_entities_filtered{type='electric-pole',position=spot,radius=60,force=F}
local out={'silo '..tostring(silo and silo.valid)..' at '..spot[1]..','..spot[2]..' poles near '..#near}
if silo then silo.set_recipe('rocket-part') silo.rocket_parts=100 local inv=silo.get_inventory(defines.inventory.rocket_silo_rocket) if inv then inv.insert{name='satellite',count=1} end out[#out+1]='status '..tostring(silo.status) end
rcon.print(table.concat(out,' | '))"""
print(c.send_command(" ".join((LUA % ("true" if DRY else "false")).split("\n"))))
