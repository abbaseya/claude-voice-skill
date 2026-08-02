#!/usr/bin/env python3
"""
my-voice baseline check.

Two gates, both must pass for BASELINE_OK:

1. Hash freshness — corpus/*.md and annotations.md hashed and compared to the
   hash recorded in the first lines of runtime/voice_model.md.
2. Coverage — runtime/corpus_notes.md must have a '## <filename>' section for
   every corpus/*.md file, each with at least one quoted excerpt (>= 15 chars)
   that appears verbatim in the source. Catches silent batching: collapsing
   multiple files into one summary, or producing sections without real quotes.

Used as the gate before drafting in the my-voice protocol.
"""

import hashlib
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

# Resolved lazily through paths.py: your writing lives outside the plugin, so a
# plugin update cannot delete it. See scripts/paths.py for why.
CORPUS_DIR = paths.corpus_dir()
ANNOTATIONS = paths.annotations()
VOICE_MODEL = paths.voice_model()
CORPUS_NOTES = paths.corpus_notes()

MIN_QUOTE_LEN = 15

QUOTE_RE = re.compile(r'"([^"\n]{%d,})"' % MIN_QUOTE_LEN)
SECTION_RE = re.compile(r'^## (.+?)\s*$', re.MULTILINE)

CURLY_QUOTE_TABLE = str.maketrans({
    '“': '"', '”': '"',
    '‘': "'", '’': "'",
})


def corpus_files() -> list:
    """All corpus pieces. Skips README.md (instructional placeholder)."""
    return sorted(f for f in CORPUS_DIR.glob("*.md") if f.name.lower() != "readme.md")


def compute_baseline_hash() -> str:
    h = hashlib.sha256()
    files = corpus_files()
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


def parse_sections(text: str) -> dict:
    sections = {}
    matches = list(SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[title] = text[start:end]
    return sections


def normalize(s: str) -> str:
    s = s.translate(CURLY_QUOTE_TABLE)
    return re.sub(r"\s+", " ", s).strip()


def coverage_problems() -> list:
    """Return list of (category, [filenames]) tuples, or [] if coverage is complete."""
    if not CORPUS_NOTES.exists():
        return [("corpus_notes_missing", ["runtime/corpus_notes.md does not exist"])]

    notes = CORPUS_NOTES.read_text()
    sections = parse_sections(notes)
    files = corpus_files()

    missing_section = []
    missing_quote = []
    fabricated_quote = []

    for cf in files:
        if cf.name not in sections:
            missing_section.append(cf.name)
            continue
        body = sections[cf.name]
        quotes = QUOTE_RE.findall(body)
        if not quotes:
            missing_quote.append(cf.name)
            continue
        corpus_text = normalize(cf.read_text())
        if not any(normalize(q) in corpus_text for q in quotes):
            fabricated_quote.append(cf.name)

    problems = []
    if missing_section:
        problems.append(("missing_section", missing_section))
    if missing_quote:
        problems.append(("missing_quote", missing_quote))
    if fabricated_quote:
        problems.append(("fabricated_quote", fabricated_quote))
    return problems


def format_problem(category: str, names: list) -> str:
    descriptions = {
        "missing_section": "missing '## <filename>' section in corpus_notes.md",
        "missing_quote": f"section exists but no quoted excerpt (>= {MIN_QUOTE_LEN} chars) — looks skim-summarized",
        "fabricated_quote": "quoted excerpts do not appear verbatim in source — either fabricated or paraphrased",
        "corpus_notes_missing": "runtime/corpus_notes.md does not exist",
    }
    desc = descriptions.get(category, category)
    if category == "corpus_notes_missing":
        return f"  - {desc}"
    head = f"  - {len(names)} file(s) with: {desc}"
    body = "\n".join(f"      {n}" for n in names[:10])
    if len(names) > 10:
        body += f"\n      ... and {len(names) - 10} more"
    return f"{head}\n{body}"


def main() -> int:
    # Anyone who installed this before it was a plugin has their writing in
    # ~/.claude/skills/my-voice/. Bring it across on the first run rather than
    # telling them they have no corpus while it sits there untouched.
    brought = paths.migrate_from_legacy()
    if brought:
        print("MIGRATED: found a pre-plugin install and copied your writing across.")
        print("  From: %s" % paths.LEGACY_HOME)
        print("  To:   %s" % paths.data_home())
        print("  Copied: %s" % ", ".join(brought))
        print("  The originals were NOT deleted. Once you have confirmed the drafts")
        print("  still sound like you, you can remove the old directory yourself.")
        print()

    if not paths.is_configured():
        print("NO_CORPUS")
        print("  No writing samples found in %s" % paths.corpus_dir())
        print("  Run /my-voice:setup to get started, then add 8-15 pieces of your own")
        print("  writing. Without a corpus this skill cannot match a voice, and it")
        print("  must not pretend to.")
        return 0

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

    problems = coverage_problems()
    if problems:
        print("REGENERATE: coverage incomplete (hash matches but corpus_notes.md is partial or fabricated)")
        for category, names in problems:
            print(format_problem(category, names))
        print()
        print("Fix: re-read each flagged corpus file individually with the Read tool and update")
        print("corpus_notes.md per step 2 of SKILL.md — one '## <filename>' section per file, each")
        print("with quoted excerpts taken verbatim from the source.")
        return 0

    n = len(corpus_files())
    print("BASELINE_OK")
    print("  Hash: " + current)
    print(f"  Coverage: {n} corpus files, all with verified-quoted excerpts in corpus_notes.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
