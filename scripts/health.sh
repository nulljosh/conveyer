#!/bin/bash
# One command for the loop tick. Prints the state of every moving part; with --fix it starts whatever is down and,
# if the world reverted after a crash, replays the builds. No daemon (house rule): it only runs when a tick or a person runs it.
# Every wait has a deadline. Exit code = number of problems still open.
cd "$(dirname "$0")/.."
FIX=0; [ "${1:-}" = "--fix" ] && FIX=1
W=.venv/bin/python; bad=0
say(){ printf '%-13s %s\n' "$1" "$2"; }
fail(){ say "$1" "DOWN $2"; bad=$((bad+1)); }
wait_for(){ local end=$((SECONDS+$1)); shift; until "$@" >/dev/null 2>&1; do [ $SECONDS -ge $end ] && return 1; sleep 3; done; }
rcon_ok(){ $W -c "import factorio_rcon as f; f.RCONClient('127.0.0.1',27000,'factorio',timeout=8).send_command('/silent-command rcon.print(1)')"; }
runner_ok(){ [ -f runner.pid ] && kill -0 "$(cat runner.pid)" 2>/dev/null; }
proc_ok(){ pgrep -f "$1" >/dev/null; }

if colima status >/dev/null 2>&1; then say colima up
elif [ $FIX = 1 ]; then colima start --network-address >/dev/null 2>&1 && say colima "started" || fail colima "start failed"
else fail colima "not running"; fi

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx conveyer-world; then say server up
elif [ $FIX = 1 ]; then SERVER_RESTARTED=1; scripts/world.sh 2>&1 | tail -1 | sed 's/^/server        /'; docker ps --format '{{.Names}}' 2>/dev/null | grep -qx conveyer-world || fail server "world.sh failed"
else fail server "container not running"; fi

if rcon_ok; then say rcon up; else fail rcon "no answer on 27000"; fi

# a runner that outlived a server restart is attached to a dead game: replace it
if [ "${SERVER_RESTARTED:-0}" = 1 ] && runner_ok; then kill "$(cat runner.pid)"; sleep 2; rm -f runner.pid runner.lock; fi
if runner_ok; then say runner "up, $(( $(ps -o rss= -p "$(cat runner.pid)") / 1024 )) MB"
elif [ $FIX = 1 ] && rcon_ok; then
  rm -f runner.lock runner.pid runner_cmd.json runner_result.json runner_seq.txt
  nohup $W runner.py --env-id open_play --keep-world > runner.log 2>&1 &
  disown; wait_for 150 grep -q "ready, waiting" runner.log && say runner started || fail runner "did not become ready in 150s"
else fail runner "not running"; fi
if runner_ok && [ "$(( $(ps -o rss= -p "$(cat runner.pid)") / 1024 ))" -gt 3000 ]; then fail runner "over 3 GB, restart it"; fi

if rcon_ok; then
  $W scripts/journal.py snapshot >/dev/null 2>&1 || true   # first, so a restore never loses anything newer
  if $W scripts/journal.py check >/dev/null 2>&1; then say world "intact"
  elif [ $FIX = 1 ]; then
    say world "REVERTED, replaying"
    $W scripts/journal.py restore; $W scripts/withdraw.py coal 300 | tail -1; $W scripts/fuel.py >/dev/null 2>&1
    $W scripts/oil.py | cut -c1-90; $W scripts/planner.py replay 2>&1 | tail -3 | cut -c1-90
  else fail world "REVERTED: run health.sh --fix"; fi
fi

for h in "research_status.py:nohup $W scripts/research_status.py >/tmp/conveyer_research.log 2>&1" \
         "snap.py:nohup $W scripts/snap.py >/dev/null 2>&1" \
         "livefeed.py:nohup $W scripts/livefeed.py >/dev/null 2>&1" \
         "keepbusy.sh:nohup scripts/keepbusy.sh >keepbusy.log 2>&1"; do
  n=${h%%:*}; cmd=${h#*:}
  if proc_ok "scripts/[${n:0:1}]${n:1}"; then say "$n" up
  elif [ $FIX = 1 ] && runner_ok; then eval "$cmd &"; disown; say "$n" started
  else fail "$n" "not running"; fi
done

say memory "$(memory_pressure | tail -1)"
say disk "$(df -g / | awk 'NR==2{print $4" GB free"}')"
say usage "$(bash ~/.claude/scripts/usage.sh 2>/dev/null || echo 'unknown (read the usage line on your messages)')"
[ -f research.json ] && say research "$($W -c "import json;r=json.load(open('research.json'));print(r['current'],str(r['percent'])+'%','| silo',r.get('silo_done'),'of',r.get('silo_total'),'| labs working',r['labs_working'],'of',r['labs'])")"
say problems "$bad"
exit $bad
