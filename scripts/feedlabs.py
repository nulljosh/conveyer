#!/usr/bin/env python3
"""Move every science pack the character carries into the labs, split evenly. FLE's get_entity
chokes on a lab that already holds packs (list vs dict), so this goes through RCON."""
import factorio_rcon
LUA = """/silent-command 
local ch = game.surfaces[1].find_entities_filtered{type='character'}[1]
local inv = ch.get_main_inventory()
local labs = game.surfaces[1].find_entities_filtered{name='lab'}
for _, pack in ipairs{'automation-science-pack','logistic-science-pack','chemical-science-pack','production-science-pack','utility-science-pack'} do
  local have = inv.get_item_count(pack)
  if have > 0 then
    local each = math.floor(have / #labs)
    local moved = 0
    for _, l in ipairs(labs) do
      local n = l.insert{name=pack, count=each}
      inv.remove{name=pack, count=n}; moved = moved + n
    end
    rcon.print(pack .. ' moved ' .. moved)
  end
end
"""
LUA = " ".join(LUA.split("\n"))
c = factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio")
print(c.send_command(LUA) or "nothing to feed")
