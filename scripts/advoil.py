#!/usr/bin/env python3
"""advoil.py: one advanced oil refinery complex for rocket fuel and lubricant, built with blocks.py. The nearest water is the east shore network, so the
complex sits at the free field around (26,-54); water comes by a routed pipe from the sulfur line's end at (55.5,-5.5), crude by barrel like the other
refineries. Layout around the refinery center R=(rx,ry), all offsets read from the game: crude emptier under the crude port, water port south-west,
light oil vertical to a manifold at ry-5 with rocket fuel assemblers above it (solid fuel and light oil in, rocket fuel out), heavy oil into a storage
tank at the west corner (heavy only stops the refinery when the tank is full), gas along ry-3 east into three solid fuel plants.
Sites freeze in .world/advoil.json; idempotent replay. ponytail: heavy oil is stored, not cracked (45k heavy over the whole run fits two tanks)."""
import json, sys
from pathlib import Path
from blocks import Site

ROOT = Path(__file__).resolve().parent.parent
SITE, EMPT = ROOT / ".world" / "advoil.json", ROOT / ".world" / "emptiers.json"
s = Site()
site = json.loads(SITE.read_text()) if SITE.exists() else None
if not site:
    r = s.free_spot(36, 26, (50, -30), maxr=90, step=2)
    if r == "none": print("no free spot"); raise SystemExit
    X, Y = [float(v) for v in r.split(",")]
    site = {"rx": X + 18.5, "ry": Y + 13.5}
    SITE.write_text(json.dumps(site))
rx, ry = site["rx"], site["ry"]
out = s.run("""local rx,ry=%g,%g
put('oil-refinery',rx,ry,d.north,'advanced-oil-processing')
put('pipe',rx+1,ry+3)
local ex,ey=rx+1,ry+5
put('assembling-machine-2',ex,ey,d.south,'empty-crude-oil-barrel')
put('inserter',ex-1,ey+2,d.south) put('wooden-chest',ex-1,ey+3) put('inserter',ex+1,ey+2,d.north) put('wooden-chest',ex+1,ey+3)
power(ex+2,ey+3)
put('pipe',rx,ry-3) put('pipe',rx,ry-4)
for x=rx,rx+11 do put('pipe',x,ry-5) end
for _,ax in ipairs{rx+2,rx+6,rx+10} do
  put('assembling-machine-2',ax,ry-7,d.south,'rocket-fuel')
  put('inserter',ax-1,ry-9,d.north) put('wooden-chest',ax-1,ry-10) put('inserter',ax+1,ry-9,d.south) put('wooden-chest',ax+1,ry-10)
  power(ax,ry-9) end
put('pipe',rx-2,ry-3) put('storage-tank',rx-4,ry-4,d.north)
for x=rx+2,rx+14 do put('pipe',x,ry-3) end
for _,px in ipairs{rx+5,rx+9,rx+13} do
  put('chemical-plant',px,ry-1,d.north,'solid-fuel-from-petroleum-gas')
  put('inserter',px,ry+1,d.north) put('wooden-chest',px,ry+2)
  power(px+2,ry+1) end
power(rx-3,ry+3) power(rx+3,ry-3)
rcon.print(table.concat(out,' | '))""" % (rx, ry))
print("placed:", out or "ok")
emp = json.loads(EMPT.read_text()) if EMPT.exists() else []
e = [rx + 1, ry + 5]
if e not in emp: emp.append(e); EMPT.write_text(json.dumps(emp))
print(s.run("""local rx,ry=%g,%g local r=s.find_entities_filtered{name='oil-refinery',position={rx,ry},radius=0.5}[1] local fl={} for i=1,#r.fluidbox do local b=r.fluidbox[i] fl[#fl+1]=b and (b.name:sub(1,5)..math.floor(b.amount)) or '-' end
local ins={} for _,i in pairs(s.find_entities_filtered{name='inserter',area={{rx-6,ry-11},{rx+16,ry+9}}}) do local k=st(i) ins[k]=(ins[k] or 0)+1 end local t={} for k,v in pairs(ins) do t[#t+1]=k..'='..v end
rcon.print('refinery '..st(r)..' '..table.concat(fl,'/')..' | inserters '..table.concat(t,','))""" % (rx, ry)))

# stage two: lubricant plant fed by ONE pipe at the tank's free west port, two electric engine assemblers below it
print(s.run("""local rx,ry=%g,%g
put('pipe',rx-6,ry-5)
local px,py=rx-7,ry-3
for _,e in pairs(s.find_entities_filtered{area={{px-1.4,py-1.4},{px+1.4,py+1.4}},type='electric-pole'}) do e.destroy() end
put('chemical-plant',px,py,d.north,'lubricant')
for x=rx-9,rx-5 do put('pipe',x,ry-1) end
for _,ax in ipairs{rx-9,rx-5} do
  put('assembling-machine-2',ax,ry+1,d.north,'electric-engine-unit')
  put('inserter',ax-1,ry+3,d.south) put('wooden-chest',ax-1,ry+4) put('inserter',ax+1,ry+3,d.north) put('wooden-chest',ax+1,ry+4)
  power(ax,ry+3) end
power(px-2,py-2)
rcon.print(table.concat(out,' | '))""" % (rx, ry)))
# water last: every port target of every machine in the complex, except the water port, is kept clear
ports = s.run("""local rx,ry=%g,%g local o={} for _,e in pairs(s.find_entities_filtered{area={{rx-20,ry-14},{rx+18,ry+10}}}) do if e.type=='assembling-machine' or e.type=='storage-tank' then for i=1,#e.fluidbox do for _,c in ipairs(e.fluidbox.get_pipe_connections(i)) do local x,y=c.target_position.x,c.target_position.y if not (math.abs(x-(rx-1))<0.1 and math.abs(y-(ry+3))<0.1) then o[#o+1]=x..','..y end end end end end rcon.print(table.concat(o,';'))""" % (rx, ry))
PORTS = [tuple(float(v) for v in p.split(",")) for p in ports.split(";") if p]
RES = [(rx + 1, ry + 3), (rx, ry - 3), (rx, ry - 4), (rx - 2, ry - 3)] + [(x, ry - 5) for x in range(int(rx), int(rx) + 12)] + [(x, ry - 3) for x in range(int(rx) + 2, int(rx) + 15)] + [(rx - 9 + dx, ry - 1) for dx in range(0, 5)] + [(rx - 6, ry - 5)]   # ports of the machines stay out of this list: the stricter router found no path through that corridor
print("water:", s.pipe((rx - 1, ry + 3), (55.5, -5.5), box=70, reserved=RES))
print(s.run("""local rx,ry=%g,%g local o={}
local r=s.find_entities_filtered{name='oil-refinery',position={rx,ry},radius=0.5}[1] local fl={} for i=1,#r.fluidbox do local b=r.fluidbox[i] fl[#fl+1]=b and (b.name:sub(1,5)..math.floor(b.amount)) or '-' end o[#o+1]='refinery '..st(r)..' '..table.concat(fl,'/')
local tk=s.find_entities_filtered{name='storage-tank',position={rx-4,ry-4},radius=0.5}[1] o[#o+1]='tank '..(tk.fluidbox[1] and (tk.fluidbox[1].name..' '..math.floor(tk.fluidbox[1].amount)) or 'empty')
local p=s.find_entities_filtered{name='chemical-plant',position={rx-7,ry-3},radius=0.5}[1] o[#o+1]='lubricant '..st(p)
for _,ax in ipairs{rx-9,rx-5} do local a=s.find_entities_filtered{name='assembling-machine-2',position={ax,ry+1},radius=0.5}[1] o[#o+1]='EEU '..st(a) end
rcon.print(table.concat(o,' | '))""" % (rx, ry)))
