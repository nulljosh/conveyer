#!/usr/bin/env bash
# ponytail: polls docker stats every 10s, kills the cluster if the Factorio
# container sustains >85% CPU or the host is under memory pressure for 3
# straight checks. No daemon, no separate process manager — run it alongside
# agent.py in its own terminal/tab and Ctrl-C both when done.
set -euo pipefail

CONTAINER="cluster-factorio_0-1"
THRESHOLD_CPU=85
STRIKES=0
MAX_STRIKES=3

while true; do
  sleep 10
  if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "[cpu_guard] container not running, exiting"
    exit 0
  fi
  cpu=$(docker stats "$CONTAINER" --no-stream --format '{{.CPUPerc}}' | tr -d '%')
  cpu_int=${cpu%.*}
  echo "[cpu_guard] ${CONTAINER} CPU: ${cpu}%"
  if [ "$cpu_int" -ge "$THRESHOLD_CPU" ]; then
    STRIKES=$((STRIKES + 1))
    echo "[cpu_guard] strike $STRIKES/$MAX_STRIKES"
  else
    STRIKES=0
  fi
  if [ "$STRIKES" -ge "$MAX_STRIKES" ]; then
    echo "[cpu_guard] sustained high CPU, stopping cluster to protect the machine"
    fle cluster stop || docker stop "$CONTAINER"
    exit 1
  fi
done
