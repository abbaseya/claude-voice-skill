#!/usr/bin/env python
"""Where the plugin lives, and where YOUR writing lives — deliberately not the same place.

As a plugin, this directory is replaced wholesale on every update. Anything of
yours stored inside it would be deleted the first time you update: your corpus,
your annotations, your accumulated anti-corpus. Years of calibration, gone
silently.

So the split is absolute:

    PLUGIN_ROOT   scripts and starter templates. Ours. Replaced on update.
    DATA_HOME     your corpus, your rules, your generated runtime cache. Yours.

DATA_HOME defaults to ~/.claude/my-voice and can be pointed anywhere with
MY_VOICE_HOME — useful if you keep your writing in a synced folder, and required
by the test suite so it never touches a real corpus.
"""
import os
import shutil
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"

# Before this was a plugin, the README told people to copy the repo into
# ~/.claude/skills/my-voice/ and drop their corpus inside it. Their writing is
# therefore sitting in the old location, and a fresh plugin install would look
# straight past it and report NO_CORPUS. We find it and bring it across.
LEGACY_HOME = Path(
    os.environ.get("MY_VOICE_LEGACY_HOME")
    or Path.home() / ".claude" / "skills" / "my-voice"
).expanduser()

# Everything a user owns. Anything not on this list is ours and is not migrated.
USER_OWNED = ["corpus", "annotations.md", "anti-corpus.md", "hard-rules.md", "runtime"]


def data_home() -> Path:
    override = os.environ.get("MY_VOICE_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "my-voice"


def corpus_dir() -> Path:
    return data_home() / "corpus"


def annotations() -> Path:
    return data_home() / "annotations.md"


def anti_corpus() -> Path:
    return data_home() / "anti-corpus.md"


def hard_rules() -> Path:
    return data_home() / "hard-rules.md"


def runtime_dir() -> Path:
    return data_home() / "runtime"


def voice_model() -> Path:
    return runtime_dir() / "voice_model.md"


def corpus_notes() -> Path:
    return runtime_dir() / "corpus_notes.md"


def sessions_dir() -> Path:
    return runtime_dir() / "sessions"


def stats_cache() -> Path:
    # Derived from the corpus, so it belongs with the corpus rather than in the
    # plugin — otherwise an update silently invalidates it.
    return runtime_dir() / "corpus_stats.json"


def corpus_files() -> list:
    """Every corpus piece, excluding the instructional README."""
    d = corpus_dir()
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.md") if p.name.lower() != "readme.md")


def is_configured() -> bool:
    return bool(corpus_files())


def legacy_corpus_present() -> bool:
    """A pre-plugin install with real writing in it (not just the template README)."""
    d = LEGACY_HOME / "corpus"
    if not d.is_dir():
        return False
    return any(p.name.lower() != "readme.md" for p in d.glob("*.md"))


def migrate_from_legacy(dry_run: bool = False) -> list:
    """Copy a pre-plugin install's writing into the data home.

    COPIES rather than moves, and never overwrites. Someone's corpus is often
    the only place a piece of their writing still exists; a tool that relocates
    it without being watched has no way to be sorry. The old directory is left
    exactly as it was, and the caller tells the user they can delete it.

    Returns the list of item names brought across (empty if nothing to do).
    """
    if not legacy_corpus_present() or is_configured():
        return []
    moved = []
    dest_root = data_home()
    for name in USER_OWNED:
        src = LEGACY_HOME / name
        dst = dest_root / name
        if not src.exists() or dst.exists():
            continue
        if not dry_run:
            dest_root.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        moved.append(name)
    return moved


if __name__ == "__main__":
    print("plugin root : %s" % PLUGIN_ROOT)
    print("data home   : %s" % data_home())
    print("corpus      : %s (%d piece(s))" % (corpus_dir(), len(corpus_files())))
    print("configured  : %s" % ("yes" if is_configured() else "NO_CORPUS"))
    if legacy_corpus_present():
        print("legacy      : %s (pre-plugin install found)" % LEGACY_HOME)
        pending = migrate_from_legacy(dry_run=True)
        print("would copy  : %s" % (", ".join(pending) or "nothing (already migrated)"))
