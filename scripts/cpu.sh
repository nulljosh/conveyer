#!/bin/bash
# cpu.sh [seconds=20]: average CPU (percent of one core) of each Conveyer process over the window, from cumulative CPU time.
cd "$(dirname "$0")/.."
W=${1:-20}
snap(){ ps -eo pid,time,command | awk -v pat="$1" '$0 ~ pat && $0 !~ /awk/ {split($2,t,/[:.]/); print $1, t[1]*60+t[2]+t[3]/100}' | head -1; }
declare -A p0 name
for n in "runner.py --env-id" "scripts/[r]esearch_status.py" "ConveyerMonitor.app/Contents/MacOS/ConveyerMonitor" "scripts/[k]eepbusy.sh" "scripts/[s]nap.py" "scripts/[l]ivefeed.py"; do
  r=$(snap "$n"); [ -n "$r" ] && { pid=${r% *}; p0[$pid]=${r#* }; name[$pid]=$n; }
done
sleep "$W"
for pid in "${!p0[@]}"; do
  t=$(ps -o time= -p "$pid" 2>/dev/null | awk '{split($1,t,/[:.]/); print t[1]*60+t[2]+t[3]/100}'); [ -z "$t" ] && continue
  printf '%-52s %5.1f%%\n' "${name[$pid]}" "$(echo "($t - ${p0[$pid]}) / $W * 100" | bc -l)"
done
printf '%-52s %5s\n' "system cpu idle" "$(top -l 2 -n 0 | awk '/CPU usage/{v=$7} END{print v}')"
