#!/usr/bin/env python3
"""withdraw.py ITEM COUNT: pull ITEM into the character's bag from chests and furnace outputs over RCON.
Shortcut: the character does not walk there. Use it when the real bottleneck is elsewhere (iron stock)."""
import sys, factorio_rcon
item, n = sys.argv[1], int(sys.argv[2])
LUA = ("/silent-command local ch=game.surfaces[1].find_entities_filtered{type='character'}[1] local inv=ch.get_main_inventory() local want=%d local got=0 "
 "for _,e in pairs(game.surfaces[1].find_entities_filtered{type={'container','furnace'},force='player'}) do if got>=want then break end "
 "local src=(e.type=='furnace') and e.get_output_inventory() or e.get_inventory(defines.inventory.chest) "
 "local have=src.get_item_count('%s') if have>0 then local take=math.min(have,want-got) local ins=inv.insert{name='%s',count=take} if ins>0 then src.remove{name='%s',count=ins} got=got+ins end end end rcon.print('%s withdrawn '..got)") % (n, item, item, item, item)
print(factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio").send_command(LUA))
