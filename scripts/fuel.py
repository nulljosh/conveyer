#!/usr/bin/env python3
"""Top every boiler and fuel-hungry furnace to a full 50-coal stack (a boiler burns 40 coal in 90 s of game time, 9 s real at 10x) up from the character's bag,
over RCON. Dry boilers and furnaces stall the whole factory (0 working furnaces seen on the real save)."""
import factorio_rcon
LUA = ("/silent-command local s=game.surfaces[1] local ch=s.find_entities_filtered{type='character'}[1] local inv=ch.get_main_inventory() "
 "local stores=s.find_entities_filtered{type='container',force='player'} "
 "local function take(n) local got=0 local bg=inv.get_item_count('coal') if bg>0 then got=inv.remove{name='coal',count=math.min(n,bg)} end "
 "for _,c in pairs(stores) do if got>=n then break end local ci=c.get_inventory(defines.inventory.chest) local h=ci.get_item_count('coal') if h>400 then got=got+ci.remove{name='coal',count=math.min(n-got,h-300)} end end return got end "
 "local out={} for _,b in pairs(s.find_entities_filtered{name={'boiler','steel-furnace','stone-furnace'}}) do local fi=b.get_fuel_inventory() local have=fi and fi.get_item_count('coal') or 99 "
 "if have<50 then local n=take(50-have) if n>0 then b.insert{name='coal',count=n} out[#out+1]=math.floor(b.position.x)..','..math.floor(b.position.y)..' +'..n end end end rcon.print(table.concat(out,' ')) ")  # stores are the source, not just the bag: the bag ran dry and the far copper furnaces sat at no_fuel with 49k coal in chests
print(factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio").send_command(LUA) or "all topped up")
