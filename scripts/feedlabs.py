#!/usr/bin/env python3
"""Move every science pack the character carries into the labs, split evenly. FLE's get_entity
chokes on a lab that already holds packs (list vs dict), so this goes through RCON."""
import factorio_rcon
LUA = """/silent-command 
local ch = game.surfaces[1].find_entities_filtered{type='character'}[1]
local inv = ch.get_main_inventory()
local labs = {} for _, l in pairs(game.surfaces[1].find_entities_filtered{name='lab'}) do if l.electric_network_id then labs[#labs+1] = l end end
for _, pack in ipairs{'automation-science-pack','logistic-science-pack','chemical-science-pack','production-science-pack','utility-science-pack'} do
  local have = inv.get_item_count(pack)
  if have > 0 then
    local each = math.floor(have / #labs)
    if each < 1 then each = 1 end
    local moved = 0
    for _, l in ipairs(labs) do
      local n = 0 if inv.get_item_count(pack) >= each then n = l.insert{name=pack, count=each} end
      if n > 0 then inv.remove{name=pack, count=n}; moved = moved + n end
    end
    rcon.print(pack .. ' moved ' .. moved)
  end
end
"""
LUA = " ".join(LUA.split("\n"))
c = factorio_rcon.RCONClient("127.0.0.1", 27000, "factorio")
print(c.send_command(LUA) or "nothing to feed")
