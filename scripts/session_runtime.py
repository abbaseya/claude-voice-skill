#!/usr/bin/env python3
"""Resolve (and create) this session's runtime scratch dir; print its path.

Per-invocation artifacts (topic.md, engagement.md, ideas.md, critique.md,
draft.md) live under runtime/sessions/<session-id>/ so that two Claude Code
sessions running this skill at the same time don't clobber each other's draft
prep. The shared corpus cache (voice_model.md, corpus_notes.md) stays at the
runtime/ root, untouched, because it's keyed by corpus hash and identical
across sessions.

Session id source: $CLAUDE_CODE_SESSION_ID — the Claude Code session id, which
matches the transcript filename at
~/.claude/projects/<project>/<session-id>.jsonl. Falls back to
manual-<utc>-<pid> when the env var is absent (older CLI versions or
non-interactive entrypoints), which still isolates the run.
"""
import datetime
import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = SKILL_DIR / "runtime" / "sessions"


def session_id() -> str:
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if sid:
        # Guard against any path-separator surprise in an unexpected value.
        return sid.replace("/", "_")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"manual-{stamp}-{os.getpid()}"


def main() -> int:
    path = SESSIONS_DIR / session_id()
    path.mkdir(parents=True, exist_ok=True)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
