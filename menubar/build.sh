#!/bin/bash
# Build + ad-hoc sign + relaunch the menu bar monitor. Signing (even ad-hoc)
# gives the binary a stable identity so macOS stops treating every rebuild as
# a brand-new unidentified app and re-prompting for permission.
set -e
cd "$(dirname "$0")"

swiftc -O -parse-as-library main.swift -o ConveyerMonitor.app/Contents/MacOS/ConveyerMonitor
codesign --force --deep --sign - ConveyerMonitor.app
xattr -cr ConveyerMonitor.app

pkill -f ConveyerMonitor 2>/dev/null || true
sleep 0.5
# Launch the binary directly rather than `open` — `open` routes through
# LaunchServices, which re-runs Gatekeeper's "unidentified developer" check
# on every rebuild (new hash = "never seen this before"), even after
# ad-hoc signing. A direct exec from Terminal skips that entirely.
nohup ./ConveyerMonitor.app/Contents/MacOS/ConveyerMonitor > /tmp/conveyer_monitor.log 2>&1 &
disown
