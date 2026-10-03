#!/usr/bin/env python3
"""make_video.py: cuts the launch video. Title card, a timelapse of the day from shots/ (the 5 minute frames snap.py saved), the rocket launch from
recordings/launch_take.mp4 with a speed ramp, an end card. Captions are drawn with PIL because this ffmpeg has no drawtext. The launch is labelled
as what it is: an ASSISTED relaunch recorded after the 21:11 crash rolled the world back; the legit launch was at 20:45 (v2.0.0).
Output: recordings/conveyer_v2.mp4 (1920x1080, 30 fps), plus web/live.mp4 and web/live-poster.jpg for the landing wallpaper (launch only, no captions).
`make_video.py` builds everything; needs recordings/launch_take.mp4. Segments are cached in recordings/seg/."""
import glob, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
REC, SEG, WEB = ROOT / "recordings", ROOT / "recordings" / "seg", ROOT / "web"
SEG.mkdir(parents=True, exist_ok=True)
FONT = "/System/Library/Fonts/Helvetica.ttc"
TAKE = REC / "launch_take.mp4"
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-an"]


def ff(*a):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, a)], check=True)


def font(size, bold=False):
    return ImageFont.truetype(FONT, size, index=1 if bold else 0)


def card(path, lines, sizes):
    im = Image.new("RGB", (1920, 1080), (22, 24, 28)); d = ImageDraw.Draw(im)
    total = sum(sizes) + 30 * (len(lines) - 1); y = (1080 - total) // 2
    for t, sz in zip(lines, sizes):
        f = font(sz, bold=sz > 80); w = d.textlength(t, font=f)
        d.text(((1920 - w) / 2, y), t, font=f, fill=(245, 240, 228) if sz > 60 else (255, 202, 48)); y += sz + 30
    im.save(path)


def caption(path, text, dy=0, left=False):
    im = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = font(38, bold=True)
    w = d.textlength(text, font=f); x0 = 40 if left else (1920 - w) / 2 - 36
    d.rounded_rectangle((x0, 940 - dy, x0 + w + 72, 1020 - dy), 18, fill=(0, 0, 0, 170)); d.text((x0 + 36, 960 - dy), text, font=f, fill=(255, 255, 255, 255))
    im.save(path)


# title and end cards
card(SEG / "title.png", ["Conveyer", "An AI plays Factorio and launches a rocket"], [130, 46])
card(SEG / "end.png", ["v2.0.0", "conveyer.heyitsmejosh.com"], [130, 46])
for n in ("title", "end"):
    ff("-loop", 1, "-t", 3, "-i", SEG / f"{n}.png", "-vf", "fade=in:0:15,fade=out:st=2.5:d=0.5", *ENC, SEG / f"{n}.mp4")

# timelapse of the day
caption(SEG / "cap_day.png", "2 October 2026, 11:00 to 20:30. The factory builds itself.")
frames = sorted(glob.glob(str(ROOT / "shots" / "2026*.png")))
(SEG / "frames.txt").write_text("".join(f"file '{p}'\nduration 0.075\n" for p in frames) + f"file '{frames[-1]}'\n")
ff("-f", "concat", "-safe", 0, "-i", SEG / "frames.txt", "-i", SEG / "cap_day.png", "-filter_complex",
   "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30[v];[v][1:v]overlay=0:0", *ENC, SEG / "day.mp4")

# the launch: 2x through the wait, slow motion through liftoff
caption(SEG / "cap_launch.png", "Assisted relaunch for the camera. The legit launch was at 20:45.", dy=90, left=True)   # above the hotbar
ff("-ss", 84, "-t", 14, "-i", TAKE, "-i", SEG / "cap_launch.png", "-filter_complex", "[0:v]setpts=0.5*PTS[v];[v][1:v]overlay=0:0", *ENC, SEG / "wait.mp4")
ff("-ss", 98, "-t", 12, "-i", TAKE, "-i", SEG / "cap_launch.png", "-filter_complex", "[0:v]setpts=1.5*PTS[v];[v][1:v]overlay=0:0", *ENC, SEG / "liftoff.mp4")

# landing wallpaper: the launch alone, no captions, small and silent
ff("-ss", 90, "-t", 20, "-i", TAKE, "-vf", "scale=1280:720,fps=30", "-c:v", "libx264", "-preset", "medium", "-crf", "27", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", WEB / "live.mp4")
ff("-ss", 8.5, "-i", WEB / "live.mp4", "-frames:v", 1, "-q:v", 3, WEB / "live-poster.jpg")

# final
(SEG / "list.txt").write_text("".join(f"file '{SEG / n}.mp4'\n" for n in ("title", "day", "wait", "liftoff", "end")))
ff("-f", "concat", "-safe", 0, "-i", SEG / "list.txt", "-c", "copy", "-movflags", "+faststart", REC / "conveyer_v2.mp4")
print("done", REC / "conveyer_v2.mp4")
