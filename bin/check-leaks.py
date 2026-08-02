#!/usr/bin/env python
"""Fail the build if anything personal leaked into this public repository.

This plugin was generalised out of one person's working setup. That is the exact
situation where a colleague's name, an employer's internal project, or a local
filesystem path survives into a template, a docstring, or an example — and once
pushed, it is public forever.

Authorship is not a leak: the author's own name in LICENSE and plugin.json is
deliberate. Everything else on the list below is.

    python bin/check-leaks.py [--extra NAME ...]
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Terms that must never appear anywhere in this repository.
FORBIDDEN = [
    # Employers / products the tool was generalised away from
    r"\bConvert\.com\b", r"\bconvertinsights\b", r"\bOGGEH\b", r"\bWebeyez\b",
    r"\bApexYard\b", r"\bCherto\b", r"\bTWIPLA\b", r"\bIntelligems\b",
    r"\bKnoxCET\b",
    # Colleagues
    r"\bDennis\b", r"\bClaudiu\b", r"\bTrina\b", r"\bMorgan\b", r"\bCarmel\b",
    r"\bCheneba\b", r"\bDmytro\b", r"\bKirill\b", r"\bLacey\b", r"\bTiffany\b",
    r"\bKarim\b",
    # Local paths from the machine this was built on
    r"/Users/[a-z]+/Sites", r"/Users/[a-z]+/Documents/Obsidian",
    r"~/Sites/", r"\.convert/",
    # Internal jargon that would mean nothing to anyone else
    r"\bLead Link\b", r"\bholacracy\b", r"\bEoR\b",
]

# (path glob, pattern) pairs that are legitimate and exempt.
ALLOW = [
    ("LICENSE", r"Ahmed Abbas"),
    (".claude-plugin/plugin.json", r"Ahmed Abbas"),
    ("README.md", r"Ahmed Abbas"),
    ("bin/check-leaks.py", r".*"),          # this file names them by definition
]

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".ico", ".pyc"}


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split("\n")
        files = [ROOT / f for f in out if f.strip()]
        if files:
            return files
    except Exception:
        pass
    # Not a git repo yet — walk the tree instead.
    return [p for p in ROOT.rglob("*")
            if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts]


def exempt(rel, pattern):
    for glob, allowed in ALLOW:
        if rel == glob and re.search(allowed, pattern) is not None:
            return True
        if rel == glob and allowed == r".*":
            return True
    return False


def main():
    extra = []
    if "--extra" in sys.argv:
        extra = [r"\b%s\b" % re.escape(x)
                 for x in sys.argv[sys.argv.index("--extra") + 1:]]
    patterns = [re.compile(p, re.I) for p in FORBIDDEN + extra]

    hits = []
    for f in tracked_files():
        if f.suffix.lower() in BINARY_SUFFIXES:
            continue
        rel = str(f.relative_to(ROOT))
        if rel.startswith("bin/check-leaks.py"):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.split("\n"), 1):
            for rx in patterns:
                m = rx.search(line)
                if m and not exempt(rel, m.group(0)):
                    hits.append((rel, i, m.group(0), line.strip()[:100]))

    if hits:
        print("Personal or internal references found in a public repository:\n")
        for rel, i, term, line in hits:
            print("  %s:%d  %r" % (rel, i, term))
            print("      %s" % line)
        print("\n%d leak(s). Genericise these before publishing." % len(hits))
        return 1
    print("No personal or internal references found. Safe to publish.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
