#!/usr/bin/env python3
"""steelfeed.py: keep the steel furnaces fed with iron plates, every keepbusy pass. Steel (5 iron plates each) is 2 per low density structure and
nothing else made it: the old stockpile ran out and the 8 steel furnaces sat idle. A furnace that last smelted steel-plate takes iron plates
into its source slot (100 max, 20 steel a fill) from any chest, never from another furnace's output. The planner's supply() already pulls the
finished steel out of furnace outputs. Fuel is fuel.py's job. Prints one line and never raises: a dead server just means skip this pass."""
import sys
import factorio_rcon as f

# previous_recipe.name is a recipe prototype in 2.0, not a string, hence pr.name.name; no Lua comments here, the script is joined onto one line
LUA = """/silent-command local s=game.surfaces[1] local fed,short=0,0
local function pull(n) local got=0 for _,c in pairs(s.find_entities_filtered{type='container',force='player'}) do if got>=n then break end
  local ci=c.get_inventory(defines.inventory.chest) local h=ci.get_item_count('iron-plate') if h>0 then local k=ci.remove{name='iron-plate',count=math.min(h,n-got)} got=got+k end end return got end
for _,fu in pairs(s.find_entities_filtered{name='steel-furnace',force='player'}) do local pr=fu.previous_recipe local nm=pr and (type(pr.name)=='string' and pr.name or pr.name and pr.name.name)
  if nm=='steel-plate' or fu.get_recipe() and fu.get_recipe().name=='steel-plate' then
    local src=fu.get_inventory(defines.inventory.furnace_source) local need=100-src.get_item_count('iron-plate')
    if need>=50 then local got=pull(need) if got>0 then local k=src.insert{name='iron-plate',count=got} fed=fed+k if k<got then local bag=s.find_entities_filtered{type='container',force='player'}[1] if bag then bag.insert{name='iron-plate',count=got-k} end end else short=short+1 end end end end
rcon.print('steel furnaces fed '..fed..' plates, '..short..' starved of iron')"""


def feed(run):
    """Run the feeding pass through `run` (a callable taking Lua and returning text); return a one-line report, or the error text if it failed."""
    try:
        return run(LUA) or "no reply"
    except Exception as e:  # server down, RCON timeout, Lua error: the loop must not die on a missed pass
        return f"steelfeed skipped: {e}"


def main():
    """Connect over RCON like the other scripts and print the report."""
    try:
        c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=60)
    except Exception as e:
        print(f"steelfeed skipped: {e}"); return
    print(feed(lambda lua: c.send_command(" ".join(lua.split("\n")))))


if __name__ == "__main__":
    main()
