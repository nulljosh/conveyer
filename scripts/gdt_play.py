#!/usr/bin/env python3
"""gdt_play.py: a deterministic driver for Game Dev Tycoon over the conveyer-bridge mod (see games/gdt/README.md).
It reads the visible screen text from state.json, presses the routine buttons, starts the next game when the studio is idle, and
logs every decision to runs/gdt/<start>.jsonl. Screens it does not know are logged and left alone (the loop stops after a few in a row).
The game only makes progress while its window is visible, so run it with the display awake and the game in front.
Assisted label: the policy reads what the player sees on screen, a public-guide table of good topic and genre pairs (GOOD), plus read-only game state (GameManager.state for the idle check,
company cash and week). It never writes cash, dates or saves. The bank's bailout is a normal in-game choice.
  gdt_play.py [--minutes 30] [--new]"""
import argparse, json, random, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gdt

ROOT = Path(__file__).resolve().parent.parent
ROUTINE = ("ok", "continue", "close", "done", "got it", "release", "release game", "yes", "sure", "finish", ":-(")   # not "No, thanks": the newsletter popup is in the page but never visible
# Topic and genre pairs the game rates well, from public Game Dev Tycoon guides (assisted-by-guide data, not read from the game).
GOOD = {
    "Action": "Airplanes Aliens Alternate History Assassin Crime Cyberpunk Dungeon Extreme Sports Fantasy Horror Hunting Martial Arts Medieval Military Music Mythology Ninja Post Apocalyptic Prison Rhythm Sci-Fi Space Sports Spy Superheroes UFO Vampire Werewolf Zombies",
    "Adventure": "Abstract Comedy Detective Fantasy Horror Law Life Mad Science Medieval Mystery Pirate Prison Romance School Sci-Fi Spy Time Travel",
    "RPG": "Aliens Alternate History Assassin Cyberpunk Detective Dungeon Fantasy Fashion Martial Arts Medieval Mystery Post Apocalyptic School Sci-Fi Spy Thief Time Travel Vampire Werewolf Wild West",
    "Simulation": "Airplane Business City Colonization Construction Cooking Dance Disasters Dungeon Dystopian Evolution Extreme Sports Farming Fashion Game Dev Government Hacking History Hospital Hunting Life Martial Arts Military Movies Music Prison Racing Rhythm School Sci-Fi Space Shorts Surgery Technology Transport Virtual Pet Vocabulary",
    "Strategy": "Airplane Business City Colonization Disasters Dungeon Evolution Expedition Fantasy Government Hacking History Medieval Military School Sci-Fi Space Transport UFO Vocabulary",
    "Casual": "Airplane Comedy Cooking Dance Farming Fashion Martial Arts Movies Music Racing Rhythm Sports Virtual Pet Vocabulary Zombies",
}
GOOD = {g: {t.strip() for t in v.replace("Extreme Sports", "Extreme_Sports").replace("Martial Arts", "Martial_Arts").replace("Alternate History", "Alternate_History").replace("Post Apocalyptic", "Post_Apocalyptic").replace("Mad Science", "Mad_Science").replace("Time Travel", "Time_Travel").replace("Wild West", "Wild_West").replace("Virtual Pet", "Virtual_Pet").replace("Game Dev", "Game_Dev").replace("Sci-Fi", "Sci-Fi").split()} for g, v in GOOD.items()}
GOOD = {g: {t.replace("_", " ") for t in ts} for g, ts in GOOD.items()}
GENRE_ORDER = ["RPG", "Action", "Adventure", "Strategy", "Simulation", "Casual"]
DESK_POINTS = [(761, 470), (780, 480), (740, 460), (800, 500)]   # the computer in the garage; later offices differ, the scan tries each


def items(s):
    """Pressable things that are actually inside the window (the newsletter popup sits off screen and clicking it does nothing)."""
    return [it for it in s["items"] if it["i"] > 2 and 0 <= it["x"] <= s["w"] and 0 <= it["y"] <= s["h"]]


def find(s, *needles):
    for it in items(s):
        t = it["text"].strip().lower()
        if any(t == n or t.startswith(n) for n in needles): return it
    return None


def idle():
    r = gdt.send("inspect", path="GameManager.state", wait=4)
    return (r.get("data") or {}).get("value") == "Idle"


def company():
    r = gdt.send("inspect", path="GameManager.company", max=60, wait=4)
    return r.get("data") or {}


class Driver:
    def __init__(self, minutes, want_new):
        out = ROOT / "runs" / "gdt"; out.mkdir(parents=True, exist_ok=True)
        self.log = open(out / f"{int(time.time())}.jsonl", "a")
        self.end, self.want_new, self.unknown, self.last = time.time() + minutes * 60, want_new, 0, None
        self.used = {}      # (kind, name) -> times picked
        self.rng, self.topic, self.attempts, self.max_attempts, self.last_over = random.Random(7), None, 0, 6, None

    def note(self, **kw):
        kw["t"] = round(time.time()); self.log.write(json.dumps(kw) + "\n"); self.log.flush()

    def click(self, it, why):
        s = gdt.state(); r = gdt.send("click", i=it["i"], gen=s["gen"])
        self.note(action="click", item=it["text"][:40], why=why, ok=r.get("ok")); time.sleep(1.0); return r.get("ok")

    def pick(self, kind, picker_text):
        """Open a picker (topic, genre, platform) and choose from what it lists: the least used, cheapest-first for platforms."""
        s = gdt.state(); opener = find(s, picker_text.lower())
        if not opener: return False
        before = {it["i"] for it in items(s)}
        self.click(opener, f"open {kind}"); time.sleep(0.8)
        s = gdt.state()
        options = [it for it in items(s) if it["i"] not in before and it["text"].strip() and "close" not in it["cls"]]
        if not options: return False
        if kind == "platform":
            def cost(it):
                import re
                m = re.search(r"cost: (\d+)K", it["text"]); return int(m.group(1)) if m else 99
            cash = self.cash(s)
            ok = [o for o in options if cost(o) * 1000 <= max(cash + 40000, 0)] or options
            choice = min(ok, key=cost) if cash < 60000 else max(ok, key=cost)
        elif kind == "topic":
            def strong(o): return sum(o["text"].strip() in GOOD[g] for g in GOOD)   # topics the game pairs well with the most genres
            choice = min(options, key=lambda o: (self.used.get((kind, o["text"]), 0), -strong(o), self.rng.random()))
        else:
            topic = self.topic or ""
            fits = [o for o in options if topic in GOOD.get(o["text"].strip(), set())]
            pool = fits or options
            choice = min(pool, key=lambda o: (GENRE_ORDER.index(o["text"].strip()) if o["text"].strip() in GENRE_ORDER else 9, self.used.get((kind, o["text"]), 0)))
        self.used[(kind, choice["text"])] = self.used.get((kind, choice["text"]), 0) + 1
        if kind == "topic": self.topic = choice["text"].strip()
        self.click(choice, f"choose {kind}"); return True

    def cash(self, s):
        import re
        m = re.search(r"Cash: (-?[\d.]+)K", s["text"]); return float(m.group(1)) * 1000 if m else 0.0

    def start_game(self):
        s = gdt.state()
        it = find(s, "develop new game")
        if not it:
            for (x, y) in DESK_POINTS:
                gdt.send("clickAt", x=x, y=y, wait=3); time.sleep(1.2)
                it = find(gdt.state(), "develop new game")
                if it: break
        if not it: self.note(action="no desk", why="could not open the new game dialog"); return False
        self.click(it, "develop new game"); time.sleep(1.2)
        for kind, text in (("topic", "pick topic"), ("genre", "pick genre"), ("platform", "pick platform")):
            if not self.pick(kind, text): self.note(action="pick failed", kind=kind); return False
        s = gdt.state(); nxt = find(s, "next")
        if nxt: self.click(nxt, "next to features"); time.sleep(1.2)
        s = gdt.state(); go = find(s, "start development")
        if go: self.click(go, "start development"); return True
        return False

    def start_over(self):
        """After a bankruptcy: dismiss it, open the main menu and press New. The company dialog, welcome pages and save slot are handled by step()."""
        s = gdt.state()
        over = find(s, "start over")
        if over: self.click(over, "start over"); self.want_new = False; return True   # the Game Over dialog's own Start over button
        sad = find(s, ":-(")
        if sad: self.click(sad, "dismiss game over"); time.sleep(1.5)
        s = gdt.state()
        menu = next((i for i in s["items"] if "mainMenuButton" in i["cls"]), None)
        if menu:
            self.click(menu, "open main menu"); time.sleep(1.5)
        s = gdt.state(); new = find(s, "new")
        if new: self.click(new, "new game after bankruptcy"); self.want_new = False; return True
        self.note(action="start over failed"); return True

    def step(self):
        s = gdt.state()
        if not gdt.alive(s): print("game not answering"); return False
        sig = (s["gen"], s["text"][:200])
        # the newsletter popup is in the page text but never on screen: drop it before classifying the screen
        text = "\n".join(l for l in s["text"].splitlines() if "newsletter" not in l.lower() and l.strip().lower() not in ("sign up no, thanks", "sign up"))
        rec = {"screen": text[:260].replace("\n", " | ")}
        low = text.lower()
        it = None
        if "click to continue" in low and find(s, "click to continue"): it = find(s, "click to continue")
        elif self.want_new and find(s, "new") and find(s, "continue") and find(s, "save"):
            it = find(s, "new"); self.want_new = False
        elif "overwrite this game" in low and find(s, "yes"):
            it = find(s, "yes")   # the confirmation shows over the slot list, so it is checked first; the slot choice below only picks our own studio's slot
        elif "choose save slot" in low:   # only ever our own studio's slot, newest first; slot 3 holds Joshua's real 2014 save and is never touched
            mine = [i for i in items(s) if i["text"].lower().startswith("slot ") and "conveyer games" in i["text"].lower()]
            it = next((i for i in mine if "minute" in i["text"] or "second" in i["text"]), mine[0] if mine else None)
        elif "bank offer" in low or "bailout" in low and find(s, "agree"): it = find(s, "agree")
        elif "company details" in low and find(s, "continue"):
            for label, value in (("company", "Conveyer Games"), ("player", "Joshua")):
                inp = next((i for i in items(s) if i["kind"] == "input" and label in i["text"].lower()), None)
                if inp: gdt.send("text", i=inp["i"], value=value, gen=s["gen"]); time.sleep(0.4)
            male = find(gdt.state(), "\u2642")
            if male: self.click(male, "male character")
            it = find(gdt.state(), "continue")
        elif any(i["text"].strip() == "Finish" and i["y"] < 200 for i in s["items"]):
            it = next(i for i in s["items"] if i["text"].strip() == "Finish" and i["y"] < 200)   # the green Finish button under the top bar: the game waits for it, it does not release by itself
        else:
            it = next((i for i in items(s) if i["text"].strip().lower() in ROUTINE), None)
        if it:
            self.click(it, "routine"); self.unknown = 0; return True
        hud_only = len([l for l in text.splitlines() if l.strip()]) <= 4 or "monthly costs" in text
        if hud_only and "game over" not in low:
            if idle():
                self.note(action="idle", cash=self.cash(s)); self.start_game()
            return True
        if "game over" in low:
            self.note(action="GAME OVER", screen=rec["screen"]); print("game over:", rec["screen"], flush=True)
            if self.last_over is None or time.time() - self.last_over > 60:
                self.attempts += 1; self.note(action="attempt over", attempts=self.attempts)
            self.last_over = time.time()
            if self.attempts > self.max_attempts: return False
            return self.start_over()
        self.unknown += 1
        if self.unknown >= 6:   # an event dialog we have no rule for: press its first button (the first choice is the friendly one in this game), never the newsletter or menu
            guess = next((i for i in items(s) if i["kind"] == "button" and 200 < i["y"] < 950 and "mainMenu" not in i["cls"]
                          and i["text"].strip().lower() not in ("sign up", "no, thanks", "trash game") and "no (go bankrupt)" not in i["text"].lower()
                          and 0 < len(i["text"].strip()) < 60), None)
            if guess: self.click(guess, "guess for unknown dialog"); self.note(action="guessed", screen=rec["screen"], pressed=guess["text"][:40])
        self.note(action="unknown", **rec, items=[(i["i"], i["text"][:30]) for i in items(s)][:12])
        if self.unknown >= 40:   # dialogs that animate (reviews, sales) take a while before their button appears
            print("stuck on an unknown screen:", rec["screen"]); return False
        return True

    def run(self):
        while time.time() < self.end:
            try:
                if not self.step(): break
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(1.5)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--minutes", type=float, default=30); ap.add_argument("--new", action="store_true"); a = ap.parse_args()
    Driver(a.minutes, a.new).run()
