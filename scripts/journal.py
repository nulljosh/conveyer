#!/usr/bin/env python3
"""journal.py snapshot | check | restore
The server cannot save under FLE, so a crash reverts the world to the 10:55 copy and every tech researched since is gone.
snapshot: union the researched techs and the research queue into .world/journal.json (only ever grows).
check:    exit 3 if the game has fewer researched techs than the journal, which means the world reverted.
restore:  mark the journaled techs researched again and put the queue back."""
import json, sys
from pathlib import Path
import factorio_rcon as f

J = Path(__file__).resolve().parent.parent / ".world" / "journal.json"
c = f.RCONClient("127.0.0.1", 27000, "factorio", timeout=60)
run = lambda lua: c.send_command(" ".join(lua.split("\n")))

def game():
    return json.loads(run("""/silent-command local F=game.forces.player local t={} for n,x in pairs(F.technologies) do if x.researched then t[#t+1]=n end end
    local q={} for _,x in pairs(F.research_queue) do q[#q+1]=x.name end rcon.print(helpers.table_to_json{techs=t,queue=q})"""))

def saved(): return json.loads(J.read_text()) if J.exists() else {"techs": [], "queue": []}

cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
if cmd == "snapshot":
    g, s = game(), saved()
    J.parent.mkdir(exist_ok=True)
    J.write_text(json.dumps({"techs": sorted(set(s["techs"]) | set(g["techs"])), "queue": g["queue"] or s["queue"]}))
    print("journal:", len(set(s["techs"]) | set(g["techs"])), "techs")
elif cmd == "check":
    g, s = game(), saved()
    lost = set(s["techs"]) - set(g["techs"])
    print(f"game {len(g['techs'])} techs, journal {len(s['techs'])}, lost {len(lost)}")
    sys.exit(3 if lost else 0)
elif cmd == "restore":
    s = saved(); names = ",".join(f"'{n}'" for n in s["techs"]); q = ",".join(f"'{n}'" for n in s["queue"])
    print(run("""/silent-command local F=game.forces.player local n=0 for _,name in ipairs{%s} do local t=F.technologies[name] if t and not t.researched then t.researched=true n=n+1 end end
    if #{%s}>0 then F.research_queue={%s} end rcon.print('restored '..n..' techs')""" % (names, q, q)))
