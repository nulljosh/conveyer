#!/usr/bin/env python3
"""make_video.py: cuts the launch footage. Plain gameplay: the recorded silo take with the build-up sped up and the launch at normal speed, one small
tag in the corner that says it is an assisted relaunch (the world was rolled back by the 21:11 crash; the legit launch was at 20:45, v2.0.0). No cards.
Input recordings/take3_silo.mp4 (scripts/record.sh style capture, 1080p). Output recordings/conveyer_gameplay.mp4 (1080p), recordings/conveyer_gameplay_share.mp4
(1080p, small enough to send) and the landing wallpaper web/live.mp4 + web/live-poster.jpg (720p, 20 s of the launch, silent).
Usage: make_video.py [take.mp4] [build_end_seconds]   (build_end: where the build-up stops and real time starts, default 170)"""
import subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
REC, WEB = ROOT / "recordings", ROOT / "web"
TAKE = Path(sys.argv[1]) if len(sys.argv) > 1 else REC / "take3_silo.mp4"
CUT = float(sys.argv[2]) if len(sys.argv) > 2 else 170.0
TAG = REC / "tag.png"


def ff(*a):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, a)], check=True)


im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
f = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
t = "Assisted relaunch. The legit launch was at 20:45."; w = d.textlength(t, font=f)
x0 = 1920 - w - 64; d.rounded_rectangle((x0, 24, x0 + w + 36, 70), 12, fill=(0, 0, 0, 150)); d.text((x0 + 18, 34), t, font=f, fill=(255, 255, 255, 235)); im.save(TAG)   # top right: the feed and the hotbar live at the bottom

dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", TAKE], text=True))
fc = (f"[0:v]trim=0:{CUT},setpts=(PTS-STARTPTS)/4[a];[0:v]trim={CUT}:{dur},setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0,fps=30[c];[c][1:v]overlay=0:0")
ff("-i", TAKE, "-i", TAG, "-filter_complex", fc, "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", REC / "conveyer_gameplay.mp4")
ff("-i", REC / "conveyer_gameplay.mp4", "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-maxrate", "2.6M", "-bufsize", "5M", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", REC / "conveyer_gameplay_share.mp4")
# landing wallpaper: the last 22 s of the take (the launch), no tag, small and silent
ff("-ss", max(0, dur - 22), "-t", 20, "-i", TAKE, "-vf", "scale=1280:720,fps=30", "-c:v", "libx264", "-preset", "medium", "-crf", "27", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", WEB / "live.mp4")
ff("-ss", 6, "-i", WEB / "live.mp4", "-frames:v", 1, "-q:v", 3, WEB / "live-poster.jpg")
print("done", [p.name for p in (REC / "conveyer_gameplay.mp4", REC / "conveyer_gameplay_share.mp4", WEB / "live.mp4")])
