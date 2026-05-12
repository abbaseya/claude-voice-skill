#!/usr/bin/env python3
"""
your-voice baseline check.

Hashes corpus/*.md and annotations.md. Compares against the hash recorded
in the first lines of runtime/voice_model.md. Prints BASELINE_OK if the
voice model is current, or REGENERATE: <reason> otherwise.

Used as the gate before drafting in the your-voice protocol.
"""

import hashlib
import sys
from pathlib import Path
from typing import Optional

SKILL_DIR = Path(__file__).resolve().parent.parent
CORPUS_DIR = SKILL_DIR / "corpus"
ANNOTATIONS = SKILL_DIR / "annotations.md"
VOICE_MODEL = SKILL_DIR / "runtime" / "voice_model.md"


def compute_baseline_hash() -> str:
    h = hashlib.sha256()
    # Skip corpus/README.md (it's an instructional placeholder, not corpus content).
    files = sorted(f for f in CORPUS_DIR.glob("*.md") if f.name.lower() != "readme.md")
    if ANNOTATIONS.exists():
        files.append(ANNOTATIONS)
    for f in files:
        h.update(f.name.encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def stored_hash() -> Optional[str]:
    if not VOICE_MODEL.exists():
        return None
    try:
        for line in VOICE_MODEL.read_text().splitlines()[:6]:
            line = line.strip()
            if line.startswith("> Generated from corpus hash:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        return None
    return None


def main() -> int:
    current = compute_baseline_hash()
    stored = stored_hash()
    if stored is None:
        print("REGENERATE: voice_model.md not found or missing hash header")
        print("  Current corpus hash: " + current)
        return 0
    if stored != current:
        print("REGENERATE: corpus or annotations have changed since last build")
        print("  Stored:  " + stored)
        print("  Current: " + current)
        return 0
    print("BASELINE_OK")
    print("  Hash: " + current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
