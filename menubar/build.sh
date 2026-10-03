#!/bin/bash
# Build + ad-hoc sign + relaunch the menu bar monitor. Signing (even ad-hoc)
# gives the binary a stable identity so macOS stops treating every rebuild as
# a brand-new unidentified app and re-prompting for permission.
set -e
cd "$(dirname "$0")"

swiftc -O -parse-as-library main.swift -o ConveyerMonitor.app/Contents/MacOS/ConveyerMonitor
# The engineer sprite sheets come from the installed game, copied into the bundle for runtime use and kept out of git.
GFX="$HOME/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app/Contents/data/base/graphics/entity/character"
ICONS="$HOME/Library/Application Support/Steam/steamapps/common/Factorio/factorio.app/Contents/data/base/graphics/icons"
mkdir -p ConveyerMonitor.app/Contents/Resources
[ -f "$GFX/level1_running.png" ] && cp "$GFX/level1_running.png" ConveyerMonitor.app/Contents/Resources/engineer_running.png
[ -f "$GFX/level1_idle.png" ] && cp "$GFX/level1_idle.png" ConveyerMonitor.app/Contents/Resources/engineer_idle.png
[ -d "$ICONS" ] && cp -r "$ICONS" ConveyerMonitor.app/Contents/Resources/icons
ID="Developer ID Application: Joshua Trommel (QMM486NPYC)"   # a stable identity: macOS keeps the Documents/Finder permission across rebuilds. Ad-hoc ("-") asked again after every build.
security find-identity -v -p codesigning | grep -q "$ID" || ID=-
codesign --force --deep --sign "$ID" ConveyerMonitor.app
xattr -cr ConveyerMonitor.app

pkill -f ConveyerMonitor 2>/dev/null || true
sleep 0.5
# Launch the binary directly rather than `open` — `open` routes through
# LaunchServices, which re-runs Gatekeeper's "unidentified developer" check
# on every rebuild (new hash = "never seen this before"), even after
# ad-hoc signing. A direct exec from Terminal skips that entirely.
nohup ./ConveyerMonitor.app/Contents/MacOS/ConveyerMonitor > /tmp/conveyer_monitor.log 2>&1 &
disown
