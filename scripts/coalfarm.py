#!/usr/bin/env python3
"""coalfarm.py [N=10]: electric drills on the coal patch near (-93,198), each dropping straight into a wooden chest. Coal ran from 50,000 to 6,000
in two hours (ten steam boilers at 10x game speed eat about 4 coal a second) and the four old drills sit blocked on a jammed belt. The loop's
supply code pulls coal from any chest holding more than 120. Slots freeze in .world/coalfarm.json; idempotent replay. Uses blocks.py."""
import json, sys
from pathlib import Path
from blocks import Site

ROOT = Path(__file__).resolve().parent.parent
SL = ROOT / ".world" / "coalfarm.json"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
s = Site()
slots = json.loads(SL.read_text()) if SL.exists() else []
if len(slots) < n:
    r = s.run("""local want=%d local have={} local found={}
for gx=-130,-60,4 do for gy=170,230,4 do if #found<want*3 then local cnt=s.count_entities_filtered{name='coal',area={{gx-1.5,gy-1.5},{gx+1.5,gy+1.5}}} if cnt>=6 then found[#found+1]={gx+0.5,gy+0.5,cnt} end end end end
table.sort(found,function(a,b) return a[3]>b[3] end) local made={}
for _,f in ipairs(found) do if #made<want then local e=s.find_entities_filtered{name='electric-mining-drill',position={f[1],f[2]},radius=0.4}[1]
  if not e and s.can_place_entity{name='electric-mining-drill',position={f[1],f[2]},direction=d.east,force=F} then e=s.create_entity{name='electric-mining-drill',position={f[1],f[2]},direction=d.east,force=F} end
  if e then local dp=e.drop_position local cx,cy=math.floor(dp.x)+0.5,math.floor(dp.y)+0.5
    local ch=s.find_entities_filtered{name='wooden-chest',position={cx,cy},radius=0.3}[1]
    if not ch and s.can_place_entity{name='wooden-chest',position={cx,cy},force=F} then ch=s.create_entity{name='wooden-chest',position={cx,cy},force=F} end
    if ch then power(f[1],f[2]) made[#made+1]=f[1]..','..f[2]..','..cx..','..cy else e.destroy() end end end end
rcon.print(table.concat(made,';'))""" % n)
    slots = [[float(v) for v in x.split(",")] for x in r.split(";") if x]
    if slots: SL.write_text(json.dumps(slots))
    print("slots", len(slots))
print(s.run("""local c={} local tot=0 for _,e in pairs(s.find_entities_filtered{name='electric-mining-drill',area={{-135,165},{-55,235}}}) do local k=st(e) c[k]=(c[k] or 0)+1 end
local t={} for k,v in pairs(c) do t[#t+1]=k..'='..v end rcon.print('coal drills '..table.concat(t,','))"""))
