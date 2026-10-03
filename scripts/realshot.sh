#!/bin/bash
# DISABLED (2026-10-02): joining the server with the real client forces a map save, the scenario's on_save fails ("Cannot save map: The scenario level
# caused a non-recoverable error"), the server quits and the world falls back to the old copy. It cost a launch, a silo build and an oil field. Do not run it.
echo "realshot.sh is disabled: a client join kills the server (map save fails). See docs/LEARNINGS.md." >&2; exit 1
# One true-graphics screenshot: join the server with the real Factorio client, have the game render the base, close the client.
# Guards: aborts under 40% free RAM; the client lives at most 150 s and is always killed; game speed is set back after.
# Usage: scripts/realshot.sh OUT.png [x y [zoom]]   (default: the tile area)
cd "$(dirname "$0")/.."
W=.venv/bin/python; OUT=${1:?out.png}; X=${2:--33}; Y=${3:-4}; Z=${4:-0.4}
free=$(memory_pressure | awk '/free percentage/{gsub("%","",$5); print $5}')
[ "${free:-0}" -ge 40 ] || { echo "abort: only ${free}% RAM free"; exit 1; }
rc(){ $W -c "import factorio_rcon as f,sys; print(f.RCONClient('127.0.0.1',27000,'factorio',timeout=30).send_command(sys.argv[1]))" "$1"; }
SO="$HOME/Library/Application Support/factorio/script-output"; mkdir -p "$SO"; rm -f "$SO/conveyer_shot.png"
cleanup(){ pkill -x factorio 2>/dev/null; sleep 2; pkill -9 -x factorio 2>/dev/null; rc "/silent-command game.speed=10" >/dev/null 2>&1; }
trap cleanup EXIT
rc "/silent-command game.speed=1" >/dev/null
open -a "/Users/joshua/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app" --args --mp-connect 192.168.64.2:34197 --mod-directory "$PWD/.world/client-mods"
end=$((SECONDS+150)); n=0
until [ "$n" -ge 1 ]; do
  [ $SECONDS -ge $end ] && { echo "client never joined in 150 s"; docker logs --tail 5 conveyer-world 2>&1 | grep -v "RCON conn" | tail -3; exit 2; }
  n=$(rc "/silent-command rcon.print(#game.connected_players)" 2>/dev/null | tr -dc 0-9); n=${n:-0}; sleep 4
done
echo "client joined after $((150-(end-SECONDS))) s"
sleep 8
rc "/silent-command local p=game.connected_players[1] game.take_screenshot{player=p,surface=game.surfaces[1],position={$X,$Y},resolution={2560,1440},zoom=$Z,path='conveyer_shot.png',show_entity_info=true,daytime=0,water_tick=0,anti_alias=false,quality=95} rcon.print('requested')"
for _ in $(seq 1 20); do [ -s "$SO/conveyer_shot.png" ] && break; sleep 2; done
[ -s "$SO/conveyer_shot.png" ] && cp "$SO/conveyer_shot.png" "$OUT" && echo "saved $OUT" || { echo "no screenshot file"; exit 3; }
