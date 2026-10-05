#!/usr/bin/env python3
"""gdt_play.py: a deterministic driver for Game Dev Tycoon over the conveyer-bridge mod (see games/gdt/README.md).
It reads the visible screen text from state.json, presses the routine buttons, starts the next game when the studio is idle, and
logs every decision to runs/gdt/<start>.jsonl. Screens it does not know are logged and left alone (the loop stops after a few in a row).
The game only makes progress while its window is visible, so run it with the display awake and the game in front.
Assisted label: the policy reads what the player sees on screen, a public-guide table of good topic and genre pairs (GOOD), plus read-only game state (GameManager.state for the idle check,
company cash and week). It never writes cash, dates or saves. The bank's bailout is a normal in-game choice.
  gdt_play.py [--minutes 30] [--new]"""
import argparse, json, random, re, subprocess, sys, time
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
DESK_POINTS = [(761, 470), (1207, 823), (1166, 782), (780, 480), (960, 760), (740, 460), (800, 500)]   # garage desk, then guesses for the first office   # the computer in the garage; later offices differ, the scan tries each


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
        self.end, self.want_new, self.unknown_since, self.last, self.last_guess = time.time() + minutes * 60, want_new, None, None, 0.0
        self.used = {}      # (kind, name) -> times picked
        self.rng, self.topic, self.attempts, self.max_attempts, self.last_over, self.repicked, self.same, self.last_click = random.Random(7), None, 0, 6, None, False, 0, None

    def note(self, **kw):
        kw["t"] = round(time.time()); self.log.write(json.dumps(kw) + "\n"); self.log.flush()

    def click(self, it, why):
        key = (why, it["text"][:40])
        self.same = self.same + 1 if key == self.last_click else 0
        self.last_click = key
        if self.same >= 12:
            self.same = 0; s = gdt.state()
            close = next((i for i in s["items"] if "closeDialogButton" in i["cls"]), None)
            self.note(action="loop detected", item=key[1], why=why, closing=bool(close))
            if close: gdt.send("click", i=close["i"], gen=s["gen"]); time.sleep(0.6)
            return False
        s = gdt.state(); r = gdt.send("click", i=it["i"], gen=s["gen"])
        self.note(action="click", item=it["text"][:40], why=why, ok=r.get("ok")); time.sleep(0.5); return r.get("ok")

    def open_options(self, s, kind):
        """The choices a picker is showing right now, found by what they look like, not by list position (the picker may already be open)."""
        central = [i for i in items(s) if 300 < i["x"] < 1650 and 180 < i["y"] < 960 and i["kind"] == "button" and i["text"].strip()]
        if kind == "platform":   # the list scrolls once there are more than three platforms, so take the off-screen ones too
            return [i for i in s["items"] if i["kind"] == "button" and "dev. cost" in i["text"].lower() and i["text"].lower().count("dev. cost") == 1]
        skip = ("pick ", "next", "start development", "trash", "finish", "ok", "close")
        out = []
        for i in central:
            t = i["text"].strip()
            on_slot = 900 < i["x"] < 1020 and any(abs(i["y"] - y) < 20 for y in (368, 440, 512))   # the three chosen-value buttons sit under the picker
            if on_slot or len(t) > 24 or "?" in t or t.lower().startswith(skip) or i["x"] > 1400 or not 300 < i["y"] < 800: continue
            if (t in GENRE_ORDER) == (kind == "genre"): out.append(i)
        return out

    def pick(self, kind, picker_text):
        """Choose from a picker (topic, genre, platform), opening it first if it is not already open."""
        s = gdt.state(); options = self.open_options(s, kind)
        if not options:
            opener = find(s, picker_text.lower())
            if not opener: return False
            self.click(opener, f"open {kind}"); time.sleep(0.4)
            s = gdt.state(); options = self.open_options(s, kind)
        if not options: return False
        if kind == "platform":
            def cost(it):   # dev cost plus any licence still to buy, in thousands
                import re
                return sum(float(x) for x in re.findall(r"cost: ([\d.]+)K", it["text"])) or 99
            def share(it):
                import re
                m = re.search(r"Marketshare: ([\d.]+)", it["text"]); return float(m.group(1)) if m else 0
            cash = self.cash(s)
            def licence(it):
                import re
                m = re.search(r"License cost: ([\d.]+)K", it["text"]); return float(m.group(1)) if m else 0.0
            rich = [o for o in options if (cost(o) - licence(o)) * 1000 <= cash * 0.15 and licence(o) * 1000 <= cash * 0.05]   # dev cost within 15% of cash, a licence within 5%
            choice = max(rich, key=share) if rich else min(options, key=cost)
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
        m = re.search(r"Cash: (-?[\d.,]+)([KMB]?)", s["text"])   # 937K, 1M, 1.2M
        return float(m.group(1).replace(",", "")) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)] if m else 0.0

    def start_game(self):
        s = gdt.state()
        it = find(s, "develop new game")
        if not it:
            for (x, y) in DESK_POINTS:
                gdt.send("clickAt", x=x, y=y, wait=3); time.sleep(1.2)
                it = find(gdt.state(), "develop new game")
                if it: break
        if not it: self.note(action="no desk", why="could not open the new game dialog"); return False
        self.repicked = False
        self.click(it, "develop new game"); return True

    def concept(self, s):
        """The new game dialog, whatever state it is in: fill the missing picks, keep the platform affordable, then Next and Start Development."""
        import re
        for kind, text in (("topic", "pick topic"), ("genre", "pick genre"), ("platform", "pick platform")):
            if find(s, text): self.pick(kind, text); return True
        m = re.search(r"Cost: ([\d.]+)K", s["text"]); cost = float(m.group(1)) * 1000 if m else 0
        cash = self.cash(s)
        slots = sorted([i for i in items(s) if 900 < i["x"] < 1020 and 340 < i["y"] < 540 and i["kind"] == "button"], key=lambda i: i["y"])
        if cost > max(cash, 0) + 20000 and len(slots) == 3 and not self.repicked:
            self.repicked = True; self.note(action="platform too dear", cost=cost, cash=cash)
            self.pick("platform", slots[2]["text"].strip().lower()); return True
        nxt = find(s, "next"); go = find(s, "start development")
        if nxt and nxt["x"] < 1400: self.click(nxt, "next to features"); return True
        if go: self.repicked = False; self.click(go, "start development"); return True
        return True

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
        import re
        sig = re.sub(r"\d+", "#", s["text"][:300])   # the same screen even while its numbers animate
        # the newsletter popup is in the page text but never on screen: drop it before classifying the screen
        text = "\n".join(l for l in s["text"].splitlines() if "newsletter" not in l.lower() and l.strip().lower() not in ("sign up no, thanks", "sign up"))
        rec = {"screen": text[:260].replace("\n", " | ")}
        low = text.lower()
        it = None
        if "which one would you like to load" in low:   # cloud and local autosaves differ after a restart: only ever our own studio's
            mine = next((i for i in items(s) if "conveyer games" in i["text"].lower() and len(i["text"]) < 200 and "which one" not in i["text"].lower()), None)
            if mine: self.click(mine, "load our own autosave"); return True
        if "acquire license?" in low:
            def exact(word): return next((i for i in items(s) if i["text"].strip().lower() == word), None)   # not find(): "no" also starts "No, thanks"
            m = re.search(r"pay ([\d,]+)", s["text"]); price = float(m.group(1).replace(",", "")) if m else 1e12
            yes, no = exact("yes"), exact("no")
            if yes and price <= self.cash(s) * 0.05:   # a licence is worth it only when it is small change
                self.click(yes, "buy licence"); self.note(action="licence bought", price=price); return True
            if no: self.click(no, "no licence purchase"); self.repicked = False; return True
        if "game concept" in low and (find(s, "next") or find(s, "start development")):
            self.unknown_since = None; return self.concept(s)
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
            self.click(it, "routine"); self.unknown_since = None; return True
        central = [i for i in items(s) if 300 < i["x"] < 1650 and 180 < i["y"] < 960]
        hud_only = not central   # nothing pressable in the middle of the window: only the top bar and side notes are showing
        if hud_only and "game over" not in low:
            self.unknown_since = None
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
        # a screen with no rule: wait (dialogs animate before their button shows), guess after 10 s, give up after 2 minutes
        now = time.time()
        if self.unknown_since is None or sig != self.last:
            self.unknown_since, self.last = now, sig
            self.note(action="unknown", **rec, items=[(i["i"], i["text"][:30]) for i in items(s)][:12])
        waited = now - self.unknown_since
        if waited > 10 and now - self.last_guess > 10:
            self.last_guess = now
            import re as _re
            cands = [i for i in items(s) if i["kind"] == "button" and 300 < i["x"] < 1650 and 200 < i["y"] < 950 and "mainMenu" not in i["cls"]
                     and i["text"].strip().lower() not in ("sign up", "no, thanks", "trash game") and "no (go bankrupt)" not in i["text"].lower()
                     and 0 < len(i["text"].strip()) < 60]
            def price(i):   # "Transfer (29K)" asks for money: an event choice that costs something is taken last (the first run paid a scam 29K)
                m = _re.search(r"([\d.]+)\s*([KM])\b", i["text"]); return float(m.group(1)) * {"K": 1e3, "M": 1e6}[m.group(2)] if m else 0.0   # "Transfer (29K)", "Move (pay 150K)"
            guess = min(cands, key=price) if cands else None
            if guess: self.click(guess, "guess for unknown dialog"); self.note(action="guessed", screen=rec["screen"], pressed=guess["text"][:40])
        if waited > 120: print("stuck on an unknown screen:", rec["screen"], flush=True); return False
        return True

    def run(self):
        while time.time() < self.end:
            try:
                if not self.step(): break
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(0.6)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--minutes", type=float, default=30); ap.add_argument("--new", action="store_true"); a = ap.parse_args()
    Driver(a.minutes, a.new).run()
