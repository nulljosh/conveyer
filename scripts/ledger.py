#!/usr/bin/env python3
"""ledger.py: what a legit launch needs against what exists, counted across every chest and machine over RCON. Prints one line per item with
percent done, and the single worst gap. Needs: silo (1000 steel, 200 processing units, 200 electric engines, 100 pipes, 1000 concrete), 100 rocket
parts (1000 processing units, 1000 low density structures, 1000 rocket fuel), a satellite (100 processing units, 100 low density structures, 50 rocket
fuel, 100 solar panels, 100 accumulators, 5 radars)."""
import sys
from blocks import Site

NEED = {"processing-unit": 1200, "low-density-structure": 1000, "rocket-fuel": 1000, "electric-engine-unit": 200, "concrete": 1000, "steel-plate": 1000,
        "pipe": 100}   # no satellite: an empty rocket wins, so no solar, accumulator, radar or battery
s = Site()
items = ",".join("'%s'" % k for k in NEED)
raw = s.run("""local o={} for _,n in ipairs{%s} do local k=0 for _,e in pairs(s.find_entities_filtered{type={'container','furnace','assembling-machine'},force=F}) do local c=0
  if e.type=='container' then c=e.get_inventory(defines.inventory.chest).get_item_count(n) elseif e.type=='furnace' then c=e.get_output_inventory().get_item_count(n) else local oi=e.get_output_inventory() c=oi and oi.get_item_count(n) or 0 end k=k+c end o[#o+1]=n..'='..k end rcon.print(table.concat(o,' '))""" % items)
have = {kv.split("=")[0]: int(kv.split("=")[1]) for kv in raw.split()}
worst = None
for k, need in NEED.items():
    pct = min(100, 100 * have.get(k, 0) // need)
    print(f"{k:24} {have.get(k,0):6} / {need:5}  {pct:3}%")
    if worst is None or pct < worst[1]: worst = (k, pct)
print(f"worst gap: {worst[0]} at {worst[1]}%")
