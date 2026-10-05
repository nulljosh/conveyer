#!/bin/bash
# mirror.sh: publish the newest game frame to the landing page (#13), so the page shows the running game.
# Usage: scripts/mirror.sh            one publish
#        scripts/mirror.sh --every 600 publish every 10 minutes until runner.pid is gone (run it as a Claude background task)
# The frame is the newest shots/timelapse JPEG (snap.py writes one every 10 minutes). Only web/live-frame.jpg changes; it is reset in git afterwards.
cd "$(dirname "$0")/.." || exit 1
publish() {
  f=$(ls -t shots/timelapse/*.jpg 2>/dev/null | head -1)
  if [ -z "$f" ]; then echo "mirror: no frame yet"; return 1; fi
  cp "$f" web/live-frame.jpg
  npx --yes wrangler deploy 2>&1 | tail -1
  git checkout -q -- web/live-frame.jpg 2>/dev/null || true
  echo "mirror: published $(basename "$f") at $(date +%T)"
}
if [ "$1" = "--every" ]; then
  while [ -f runner.pid ]; do publish; sleep "${2:-600}"; done
else
  publish
fi
