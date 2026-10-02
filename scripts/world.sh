#!/bin/bash
# Run FLE against a copy of your own Factorio save instead of the open_world scenario.
#   scripts/world.sh [save.zip]   swap the server onto a copy of the save (default: a.zip)
#   scripts/world.sh back         return to FLE's stock open_world container
# The original save is never touched; the server only ever sees conveyer-world.zip.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FLE="$ROOT/.venv/lib/python3.14/site-packages/fle"
STOCK=cluster-factorio_0-1
NAME=conveyer-world

if [ "${1:-}" = back ]; then
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  rm -f "$ROOT/.world/active"
  docker start "$STOCK"
  exit 0
fi

SAVE="${1:-$HOME/Library/Application Support/factorio/saves/a.zip}"
docker stop "$STOCK" >/dev/null 2>&1 || true
docker rm -f "$NAME" >/dev/null 2>&1 || true
mkdir -p "$ROOT/.world" && cp "$SAVE" "$ROOT/.world/conveyer-world.zip"
docker create --name "$NAME" -m 1536m \
  -p 34197:34197/udp -p 27000:27015/tcp \
  -v "$ROOT/.world:/opt/factorio/saves" \
  -v "$FLE/cluster/config:/opt/factorio/config" \
  -v "$FLE/cluster/mods:/opt/factorio/mods" \
  -v "$FLE/.fle/data/_screenshots:/opt/factorio/script-output" \
  --entrypoint /bin/sh factoriotools/factorio:2.0.77 -c \
  'rm -rf /opt/factorio/data/elevated-rails /opt/factorio/data/quality /opt/factorio/data/space-age && exec /bin/box64 /opt/factorio/bin/x64/factorio --start-server /opt/factorio/saves/conveyer-world.zip --port 34197 --server-settings /opt/factorio/config/server-settings.json --rcon-port 27015 --rcon-password factorio --server-whitelist /opt/factorio/config/server-whitelist.json --use-server-whitelist --server-adminlist /opt/factorio/config/server-adminlist.json --mod-directory /opt/factorio/mods' >/dev/null
docker start "$NAME" >/dev/null
touch "$ROOT/.world/active"
for _ in $(seq 1 90); do
  docker logs "$NAME" 2>&1 | grep -q "Starting RCON interface" && { echo "world up: $(basename "$SAVE") (copy)"; exit 0; }
  sleep 2
done
echo "server didn't come up, last log:"; docker logs --tail 20 "$NAME"; exit 1
