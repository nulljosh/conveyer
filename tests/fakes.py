"""Test doubles shared by the tests. install_rcon() puts a fake factorio_rcon in sys.modules, so scripts that connect at import
load in CI (no game, no server). FakeRCON answers send_command from a function or a list of replies and records every command."""
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class FakeRCON:
    def __init__(self, replies=None, *a, **k):
        self.replies, self.sent, self.closed = replies, [], False

    def send_command(self, cmd):
        self.sent.append(cmd)
        r = self.replies
        if callable(r): return r(cmd)
        if isinstance(r, list):
            v = r.pop(0) if r else ""
            if isinstance(v, Exception): raise v
            return v
        return r if r is not None else ""

    def close(self): self.closed = True


def install_rcon():
    mod = types.ModuleType("factorio_rcon")
    mod.RCONClient = lambda *a, **k: FakeRCON()
    sys.modules["factorio_rcon"] = mod
    return mod


def load(name):
    """Import scripts/<name>.py as a module, with scripts/ on the path like the scripts expect."""
    if str(ROOT / "scripts") not in sys.path: sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
