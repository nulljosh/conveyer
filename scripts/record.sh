#!/bin/bash
# record.sh: full-screen capture of the live window for the launch video. 30 fps hardware H.264 at the display's native size, 5 minute segments
# in recordings/take_NNN.mp4 so a crash loses at most one segment. Open the window first: menubar/ConveyerMonitor.app --open-live --fullscreen --zoom 1.2.
# Stop with: kill -INT $(pgrep -x ffmpeg). screencapture -v wrote nothing here, ffmpeg avfoundation works.
cd "$(dirname "$0")/.."
mkdir -p recordings
exec ffmpeg -hide_banner -loglevel error -f avfoundation -framerate 30 -capture_cursor 0 -i "0:none" \
  -c:v h264_videotoolbox -b:v 14M -pix_fmt yuv420p -f segment -segment_time 300 -reset_timestamps 1 recordings/take_%03d.mp4
