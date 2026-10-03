#!/bin/bash
# Refresh the landing page from the live base and deploy it. Run at every milestone.
# Order: fresh textured map -> landing_sync (page, base.png, og.png, README progress) -> commit -> wrangler deploy -> check live.
set -euo pipefail
cd "$(dirname "$0")/.."
[ preview_map.png -nt preview.png ] || .venv/bin/python scripts/terrain.py >/dev/null   # research_status.py repaints it while anyone watches; two painters at once collided on the temp file
.venv/bin/python scripts/landing_sync.py
git add web README.md
git commit -qm "Landing: refresh base map and progress at milestone ${1:-update}

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016LFXk1MbaTzYiXBe7RdzD2" || true
git push -q || true
npx --yes wrangler deploy 2>&1 | tail -2
sleep 5
curl -s https://conveyer.heyitsmejosh.com/ | grep -o "Road to the rocket" | head -1 || echo "live page check failed"
curl -sI https://conveyer.heyitsmejosh.com/base.png | grep -i "content-length\|HTTP"
