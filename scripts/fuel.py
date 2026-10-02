#!/usr/bin/env python3
"""Top every boiler (to 40 coal) and every fuel-hungry furnace (to 20) up from the character's bag,
over RCON. Dry boilers and furnaces stall the whole factory (0 working furnaces seen on the real save)."""
import factorio_rcon
LUA = ("/silent-command local ch=game.surfaces[1].find_entities_filtered{type='character'}[1] local inv=ch.get_main_inventory() "
 "for _,b in pairs(game.surfaces[1].find_entities_filtered{name={'boiler','steel-furnace','stone-furnace'}}) do local have=(b.get_fuel_inventory() and b.get_fuel_inventory().get_item_count('coal') or 99) "
 "local cap=(b.name=='boiler') and 40 or 20 if have<cap then local n=b.insert{name='coal',count=math.min(cap-have,inv.get_item_count('coal'))} inv.remove{name='coal',count=n} rcon.print(math.floor(b.position.x)..','..math.floor(b.position.y)..' +'..n) end end")
print(factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio").send_command(LUA) or "all topped up")
