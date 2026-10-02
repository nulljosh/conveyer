#!/usr/bin/env python3
"""Builds web/index.html from real data: research.json (live research), shots/bench.jsonl (entity count),
roadmap.md (next milestones + ETAs) and the live map (preview_map.png -> web/base.png, web/og.png).
Run it, then: npx wrangler deploy."""
import html, json, re, shutil, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
esc = html.escape
nice = lambda n: esc(n.replace("-", " "))

r = json.loads((ROOT / "research.json").read_text()) if (ROOT / "research.json").exists() else {}
bench = (ROOT / "shots" / "bench.jsonl")
entities = json.loads(bench.read_text().splitlines()[-1])["entities"] if bench.exists() else 0

src = ROOT / "preview_map.png"
if src.exists():
    shutil.copy(src, WEB / "base.png")
    subprocess.run(["magick", str(src), "-resize", "1200x", "-gravity", "center", "-crop", "1200x630+0+0", "+repage", str(WEB / "og.png")], check=False)

# next milestones from the roadmap (open items only), no parentheses jargon
road = (ROOT / "roadmap.md").read_text()
sec = road.split("## Real save run", 1)[1].split("\n## ", 1)[0]
nxt = []
for line in sec.splitlines():
    t = line.strip()
    if t.startswith("- [ ]"):
        left, _, eta = t[6:].partition(" ETA ")
        title = re.sub(r"\s*\([^)]*\)", "", left.split(". ")[0]).strip(". ")
        for cut in (":", " so ", " to the "):  # headline only, the detail lives in the roadmap
            title = title.split(cut)[0]
        nxt.append((title, eta.strip(". ")))
nxt = [n for n in nxt if "fine-tune" not in n[0]][:5]

DONE = ["Plays on a real 2,300 entity save", "Hand-fed science to chemical science", "First iron plate from a vanilla start",
        "Drill, belt, inserter, furnace chain with no hand feeding", "Six clean unattended runs in a row"]
done_li = "\n".join(f"<li>{esc(d)}</li>" for d in DONE)
next_li = "\n".join(f"<li>{esc(t)}{f' <span>{esc(e)}</span>' if e else ''}</li>" for t, e in nxt)

cur = nice(r["current"]).capitalize() if r.get("current") else "Between research"
pct = r.get("percent", 0)
queue = [nice(q) for q in r.get("queue", [])[1:2]]
labs = "Labs idle, waiting for science packs" if not r.get("labs_working") else f"{r['labs_working']} of {r['labs']} labs working"
today = time.strftime("%-d %b %Y")

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conveyer, an LLM that plays Factorio</title>
<meta name="description" content="An LLM plays Factorio on a real save. It reads the game, picks one move from a short list, and repeats.">
<meta name="theme-color" content="#f5f0e4">
<meta property="og:title" content="Conveyer">
<meta property="og:description" content="An LLM plays Factorio on a real save.">
<meta property="og:image" content="https://conveyer.heyitsmejosh.com/og.png">
<meta property="og:url" content="https://conveyer.heyitsmejosh.com/">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://conveyer.heyitsmejosh.com/og.png">
<link rel="icon" href="icon.svg">
<link rel="stylesheet" href="https://heyitsmejosh.com/tokens.css">
<script>document.documentElement.className="js"</script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  body { background: var(--bg, #f5f0e4); color: var(--text, #1f1b16); font-family: var(--font-body, -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif); line-height: 1.6; -webkit-font-smoothing: antialiased; }
  a { color: inherit; }
  ::selection { background: var(--bulb, #ffca30); color: var(--text, #1f1b16); }
  h1, h2, h3 { text-wrap: balance; }
  code { font-family: var(--font-code, ui-monospace, "SF Mono", Menlo, monospace); font-size: .9em; background: var(--color-code-bg, #ebe4d3); padding: .1em .35em; border-radius: 4px; }
  .sheet-rule { display: flex; align-items: center; gap: 16px; padding: 14px 20px 0; font-size: 13px; letter-spacing: .08em; font-variant: var(--caption, small-caps); font-weight: 500; color: var(--text2, rgba(31,27,22,.6)); }
  .sheet-rule::before { content: ""; order: 1; flex: 1; height: 1px; background: var(--border, #dcd2bd); }
  .sheet-rule > :first-child { order: 0; } .sheet-rule > :last-child { order: 2; }
  .sheet-rule a { text-decoration: none; display: inline-block; padding: 12px 6px; margin: -12px -6px; } .sheet-rule a:hover { text-decoration: underline; }
  .hero { text-align: center; padding: 88px 20px 48px; display: flex; flex-direction: column; align-items: center; }
  .mark { width: 92px; height: 92px; border-radius: 22px; }
  .hero h1 { font-size: clamp(2.6rem, 8vw, 5rem); line-height: 1.02; letter-spacing: -.035em; font-weight: 700; margin-top: 18px; }
  .eyebrow { margin-top: 14px; font-size: 14px; font-variant: var(--caption, small-caps); letter-spacing: .08em; font-weight: 600; }
  .lede { font-size: 1.2rem; color: var(--text2, rgba(31,27,22,.6)); max-width: 30ch; margin: 18px auto 0; }
  .cta { margin-top: 28px; display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; }
  .btn { display: inline-block; padding: 10px 18px; border-radius: var(--radius-pill, 999px); border: 1px solid var(--text, #1f1b16); text-decoration: none; font-size: .95rem; font-weight: 500; }
  .btn.solid { background: var(--text, #1f1b16); color: var(--bg, #f5f0e4); } .btn:hover { opacity: .85; }
  .stage { max-width: 1040px; margin: 0 auto; padding: 0 16px; }
  .win { border: 1px solid var(--border2, #ebe4d3); border-radius: var(--radius-lg, 18px); background: var(--bg2, #ebe4d3); overflow: hidden; box-shadow: var(--shadow-lg, 0 12px 36px rgba(60,40,20,.12)); }
  .bar { display: flex; align-items: center; gap: 6px; padding: 10px 14px; border-bottom: 1px solid var(--border, #dcd2bd); font-size: .8rem; color: var(--text2, rgba(31,27,22,.6)); }
  .bar i { width: 11px; height: 11px; border-radius: 50%; background: var(--border, #dcd2bd); } .bar span { margin-left: 10px; }
  .panes { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); }
  .map img { display: block; width: 100%; height: 100%; object-fit: cover; object-position: 50% 12%; aspect-ratio: 1.15; }
  .live { padding: 22px 22px 24px; border-left: 1px solid var(--border, #dcd2bd); display: flex; flex-direction: column; gap: 6px; }
  .live small { font-size: .8rem; font-variant: var(--caption, small-caps); letter-spacing: .06em; color: var(--text2, rgba(31,27,22,.6)); font-weight: 600; }
  .live b.big { font-size: 1.5rem; letter-spacing: -.02em; line-height: 1.15; }
  .meter { height: 8px; border-radius: 99px; background: var(--border, #dcd2bd); overflow: hidden; margin: 6px 0 2px; }
  .meter i { display: block; height: 100%; width: __PCT__%; background: var(--accent, #b3461f); border-radius: 99px; }
  .live p { font-size: .9rem; color: var(--text2, rgba(31,27,22,.6)); }
  .live ol { margin: 4px 0 0 1.1rem; font-size: .9rem; } .live li { margin-top: 4px; } .live li span { color: var(--text2, rgba(31,27,22,.6)); }
  .plate-cap { margin: 14px 0 0; text-align: center; font-size: 13px; letter-spacing: .08em; font-variant: var(--caption, small-caps); font-weight: 500; color: var(--text2, rgba(31,27,22,.6)); }
  .wrap { max-width: 640px; margin: 0 auto; padding: 0 20px; }
  .facts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; max-width: 760px; margin: 72px auto 0; padding: 0 20px; }
  .fact { border: 1px solid var(--border, #dcd2bd); border-radius: var(--radius, 12px); padding: 16px 14px; background: var(--bg2, #ebe4d3); text-align: center; }
  .fact b { display: block; font-size: 1.6rem; letter-spacing: -.03em; line-height: 1.1; } .fact span { font-size: .8rem; color: var(--text2, rgba(31,27,22,.6)); }
  section.copy { padding-top: 72px; } section.copy h2 { font-size: 1.7rem; letter-spacing: -.025em; margin-bottom: 14px; }
  .steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 8px; }
  .step { border-top: 2px solid var(--accent, #b3461f); padding-top: 10px; } .step b { display: block; font-size: .95rem; } .step span { font-size: .85rem; color: var(--text2, rgba(31,27,22,.6)); }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 8px; }
  .card { border: 1px solid var(--border, #dcd2bd); border-radius: var(--radius, 12px); background: var(--bg2, #ebe4d3); padding: 14px 16px; min-width: 0; }
  .card h3 { font-size: .95rem; margin-bottom: 6px; } .card ul { list-style: none; } .card li { font-size: .9rem; padding: 4px 0; } .card li span { display: block; font-size: .8rem; color: var(--text2, rgba(31,27,22,.6)); }
  .done li::before { content: "\\2713"; margin-right: 8px; color: var(--accent, #b3461f); font-weight: 700; }
  .run pre { font-family: var(--font-code, ui-monospace, "SF Mono", Menlo, monospace); font-size: .85rem; line-height: 1.6; overflow: auto; border: 1px solid var(--border2, #ebe4d3); border-radius: var(--radius, 12px); background: var(--bg2, #ebe4d3); padding: 14px 16px; }
  footer { margin: 96px 0 40px; }
  footer .foot-rule { display: flex; align-items: center; gap: 16px; max-width: 880px; margin: 0 auto; padding: 14px 20px 28px; font-size: 13px; letter-spacing: .06em; font-weight: 500; color: var(--text2, rgba(31,27,22,.6)); }
  footer .foot-rule::before { content: ""; order: 1; flex: 1; height: 1px; background: var(--border, #dcd2bd); } footer .foot-rule > :first-child { order: 0; } footer .foot-rule > :last-child { order: 2; }
  .foot-dir { display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px 24px; max-width: 880px; margin: 0 auto; padding: 0 20px 28px; }
  .foot-col h3 { margin: 0 0 8px; font-size: 12px; font-weight: 600; letter-spacing: .02em; } .foot-col ul { list-style: none; }
  .foot-col a { display: inline-block; padding: 8px 0; color: var(--text2, rgba(31,27,22,.6)); text-decoration: none; font-size: 13px; line-height: 1.35; } .foot-col a:hover { color: var(--text, #1f1b16); text-decoration: underline; }
  .foot-bar { max-width: 880px; margin: 0 auto; padding: 18px 20px 0; border-top: 1px solid var(--border, #dcd2bd); color: var(--text2, rgba(31,27,22,.6)); font-size: 12.5px; }
  .js .reveal { opacity: 0; transform: translateY(14px); transition: opacity .6s ease, transform .6s ease; } .js .reveal.in { opacity: 1; transform: none; }
  @media (max-width: 720px) {
    .hero { padding: 48px 16px 32px; } .hero h1 { font-size: clamp(2.4rem, 12vw, 3.2rem); } .lede { font-size: 1.05rem; } .mark { width: 72px; height: 72px; }
    .btn { padding: 13px 20px; min-height: 44px; } .stage { padding: 0 12px; } .wrap { padding: 0 16px; }
    .panes { grid-template-columns: minmax(0, 1fr); } .live { border-left: 0; border-top: 1px solid var(--border, #dcd2bd); }
    .facts, .steps { grid-template-columns: repeat(2, minmax(0, 1fr)); } .cols { grid-template-columns: minmax(0, 1fr); } .foot-dir { grid-template-columns: repeat(2, 1fr); }
  }
  @media (prefers-reduced-motion: reduce) { .js .reveal { opacity: 1; transform: none; transition: none; } }
</style>
</head>
<body id="top">
<div class="sheet-rule" aria-hidden="true"><span>Conveyer</span><span><a href="https://github.com/nulljosh/conveyer" tabindex="-1">GitHub</a></span></div>
<main>
<header class="hero">
  <img class="mark" src="icon.svg" alt="">
  <h1>Introducing<br>Conveyer.</h1>
  <p class="eyebrow">An LLM plays Factorio.</p>
  <p class="lede">On a real save. It reads the game, picks one move, and repeats.</p>
  <div class="cta"><a class="btn solid" href="https://github.com/nulljosh/conveyer">View on GitHub</a><a class="btn" href="#run">Run it</a></div>
</header>

<div class="stage">
  <div class="win">
    <div class="bar"><i></i><i></i><i></i><span>The base, live from the game</span></div>
    <div class="panes">
      <div class="map"><img src="base.png" width="1024" height="1024" alt="Top-down map of the real Factorio base, drawn from game state"></div>
      <div class="live">
        <small>Researching</small>
        <b class="big">__CUR__</b>
        <div class="meter" role="img" aria-label="__PCT__ percent"><i></i></div>
        <p>__PCT__%__THEN__ &middot; __LABS__</p>
        <small style="margin-top:14px">Next</small>
        <ol>__NEXT3__</ol>
      </div>
    </div>
  </div>
  <p class="plate-cap">Drawn from game state, __TODAY__</p>
</div>

<div class="facts reveal">
  <div class="fact"><b>__TECHS__</b><span>techs researched</span></div>
  <div class="fact"><b>__ENT__</b><span>things on the base</span></div>
  <div class="fact"><b>0</b><span>pixels read</span></div>
  <div class="fact"><b>0</b><span>rockets launched</span></div>
</div>

<section class="copy wrap reveal">
  <h2>How it plays</h2>
  <div class="steps">
    <div class="step"><b>Read</b><span>The real game state.</span></div>
    <div class="step"><b>Pick</b><span>One move from a short list.</span></div>
    <div class="step"><b>Check</b><span>The move proves it worked.</span></div>
    <div class="step"><b>Repeat</b><span>The base grows.</span></div>
  </div>
</section>

<section class="copy wrap reveal">
  <h2>Where it is</h2>
  <div class="cols">
    <div class="card done"><h3>Done</h3><ul>__DONE__</ul></div>
    <div class="card"><h3>Next</h3><ul>__NEXT__</ul></div>
  </div>
</section>

<section class="copy wrap run reveal" id="run">
  <h2>Run it</h2>
<pre>pip install -r requirements.txt
fle cluster start -n 1 -s open_world
python3 runner.py --env-id open_play
./step.sh '{"skill":"inspect","params":{}}'</pre>
</section>
</main>

<footer>
  <div class="foot-rule" aria-hidden="true"><span>Conveyer</span><span>Built on FLE</span></div>
  <nav class="foot-dir" aria-label="Footer">
    <div class="foot-col"><h3>Conveyer</h3><ul>
      <li><a href="https://github.com/nulljosh/conveyer/blob/main/roadmap.md">Roadmap</a></li>
      <li><a href="https://github.com/nulljosh/conveyer/blob/main/WHITEPAPER.md">Whitepaper</a></li>
      <li><a href="https://github.com/nulljosh/conveyer/blob/main/docs/LEARNINGS.md">What we learned</a></li></ul></div>
    <div class="foot-col"><h3>Built on</h3><ul>
      <li><a href="https://github.com/JackHopkins/factorio-learning-environment">Factorio Learning Environment</a></li>
      <li><a href="https://github.com/nulljosh/conveyer">Source</a></li>
      <li><a href="https://github.com/nulljosh/conveyer/issues">Report a bug</a></li></ul></div>
    <div class="foot-col"><h3>Project</h3><ul>
      <li><a href="https://github.com/nulljosh/conveyer/blob/main/LICENSE">License (MIT)</a></li>
      <li><a href="https://heyitsmejosh.com">Portfolio</a></li>
      <li><a href="#top">Back to top</a></li></ul></div>
  </nav>
  <div class="foot-bar">Conveyer &middot; MIT License &middot; &copy; 2026 Joshua Trommel &middot; Unaffiliated with Wube Software</div>
</footer>
<script>
(function () {
  var els = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) { els.forEach(function (e) { e.classList.add("in"); }); return; }
  var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }); }, { threshold: .08 });
  els.forEach(function (e) { io.observe(e); });
})();
</script>
</body>
</html>
"""
out = (PAGE.replace("__CUR__", cur).replace("__PCT__", str(pct)).replace("__LABS__", esc(labs))
       .replace("__THEN__", f" &middot; then {queue[0]}" if queue else "")
       .replace("__NEXT3__", "".join(f"<li>{esc(t)}</li>" for t, _ in nxt[:3]))
       .replace("__TODAY__", today).replace("__TECHS__", str(r.get("techs", "")))
       .replace("__ENT__", f"{entities:,}").replace("__DONE__", done_li).replace("__NEXT__", next_li))
(WEB / "index.html").write_text(out)
print("built", len(out), "bytes;", len(nxt), "next items")
