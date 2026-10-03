#!/usr/bin/env python3
"""events.py: the activity feed for the live window. Every 10 s one RCON call reads a few counters; changes become short plain-English events in
events.json (newest last, 8 kept): the launch ledger moving, research finishing, pumpjacks lost, turrets firing, power coming and going. The menu bar
app shows them as fading toasts. Loops until runner.pid is gone; `events.py --once` prints one snapshot.
ponytail: counters and thresholds, no event bus; add a counter to LUA and a rule to rules() to add an event."""
import json, os, sys, time
from pathlib import Path
import factorio_rcon as f

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "events.json"
ITEMS = ["rocket-fuel", "low-density-structure", "processing-unit", "electric-engine-unit", "plastic-bar", "steel-plate"]
NICE = {"rocket-fuel": "Rocket fuel", "low-density-structure": "Low density structure", "processing-unit": "Processing units",
        "electric-engine-unit": "Electric engines", "plastic-bar": "Plastic", "steel-plate": "Steel"}
LUA = """/silent-command local s=game.surfaces[1] local F=game.forces.player local o={}
local tot={} for _,ch in pairs(s.find_entities_filtered{type='container',force='player'}) do local i=ch.get_inventory(defines.inventory.chest) for _,n in ipairs({%s}) do tot[n]=(tot[n] or 0)+i.get_item_count(n) end end
for _,n in ipairs({%s}) do o[#o+1]=n..'='..(tot[n] or 0) end
local mags=0 for _,t in pairs(s.find_entities_filtered{name='gun-turret',force='player'}) do mags=mags+t.get_inventory(defines.inventory.turret_ammo).get_item_count('piercing-rounds-magazine') end
local done=0 for _,t in pairs(F.technologies) do if t.researched then done=done+1 end end
local eng=0 for _,e in pairs(s.find_entities_filtered{name='steam-engine',force='player'}) do if e.status==defines.entity_status.working then eng=eng+1 end end
o[#o+1]='mags='..mags o[#o+1]='pumpjacks='..s.count_entities_filtered{name='pumpjack',force='player'} o[#o+1]='techs='..done o[#o+1]='engines='..eng
local si=s.find_entities_filtered{name='rocket-silo'}[1] o[#o+1]='nests='..s.count_entities_filtered{type='unit-spawner',force='enemy'} o[#o+1]='parts='..(si and si.rocket_parts or 0) o[#o+1]='rockets='..F.rockets_launched
o[#o+1]='research='..(F.current_research and F.current_research.name or '')
rcon.print(table.concat(o,';'))""" % (",".join("'%s'" % i for i in ITEMS), ",".join("'%s'" % i for i in ITEMS))


def read(c):
    d = {}
    for kv in c.send_command(" ".join(LUA.split("\n"))).strip().split(";"):
        k, _, v = kv.partition("=")
        d[k] = v if k == "research" else int(v or 0)
    return d


def rules(a, b):
    out = []   # (kind, text): ok good news, warn watch it, bad needs a look
    for i in ITEMS:
        n = b[i] - a[i]
        if i in ("rocket-fuel", "low-density-structure", "processing-unit", "electric-engine-unit") and n >= 5:
            out.append(("ok", "%s +%d (now %d)" % (NICE[i], n, b[i])))
    if a["nests"] - b["nests"] >= 3: out.append(("ok", "Assisted sweep: %d nests left" % b["nests"]))
    if b["rockets"] > a["rockets"]: out.append(("ok", "ROCKET LAUNCHED (%d total)" % b["rockets"]))
    if b["parts"] // 10 > a["parts"] // 10 and b["parts"] > 0: out.append(("ok", "Rocket parts: %d of 100" % b["parts"]))
    if b["techs"] > a["techs"]: out.append(("ok", "Research finished: %d techs done" % b["techs"]))
    if b["research"] and b["research"] != a["research"]: out.append(("ok", "Researching %s" % b["research"].replace("-", " ")))
    if b["pumpjacks"] < a["pumpjacks"]: out.append(("bad", "Pumpjack lost, %d left" % b["pumpjacks"]))
    if b["pumpjacks"] > a["pumpjacks"]: out.append(("ok", "Pumpjack rebuilt, %d running" % b["pumpjacks"]))
    if a["mags"] - b["mags"] >= 3: out.append(("warn", "Turrets firing: %d magazines spent" % (a["mags"] - b["mags"])))
    if b["engines"] >= a["engines"] + 4: out.append(("ok", "Power up: %d engines running" % b["engines"]))
    if b["engines"] <= a["engines"] - 4: out.append(("bad", "Power down: %d engines running" % b["engines"]))
    return out


def push(evts, new):
    now = time.time()
    evts = (evts + [{"t": now, "kind": k, "text": t} for k, t in new])[-8:]
    tmp = OUT.with_suffix(".tmp"); tmp.write_text(json.dumps({"events": evts})); os.replace(tmp, OUT)
    return evts


if __name__ == "__main__":
    c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=30)
    if "--once" in sys.argv:
        print(read(c)); sys.exit()
    prev, evts = None, []
    while (ROOT / "runner.pid").exists():
        try:
            cur = read(c)
            if prev: evts = push(evts, rules(prev, cur)) if rules(prev, cur) else evts
            else: evts = push([], [("ok", "Live feed on")])
            prev = cur
        except Exception as e:   # server restarting: reconnect next lap
            print("events:", e, file=sys.stderr)
            try: c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=30)
            except Exception: pass
        time.sleep(10)
