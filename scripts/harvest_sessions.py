#!/usr/bin/env python3
"""
Build corpus pieces out of what you have typed to Claude Code.

Most people setting this skill up cannot find 8-15 pieces of their own
writing. They usually have far more than they think, sitting in their session
transcripts: months of unedited, first-person, unpolished prose written
without any thought of how it would read. That is a better sample of how
somebody writes than anything they would deliberately submit.

It is also the sample most likely to embarrass them, so the defaults are
cautious:

  ONLY WHAT YOU TYPED   Tool results, pasted files, command output, system
                        reminders and prompts written by an agent to another
                        agent are all excluded. Those are not your writing.

  NOTHING HEATED        Frustration aimed at the assistant is dropped. Nobody
                        wants a bad afternoon feeding into how they sound in
                        public, and venting has a register of its own that
                        would pull every draft toward it.

  SECRETS REDACTED      Keys, tokens, emails and long identifiers are removed
                        before anything is written to disk. This is a lossy,
                        best-effort pass over text that was never meant to be
                        published — read the output before you trust it.

  ITS OWN GENRE         Written to a genre of its own, because instructing an
                        agent is not the register you write an article in.
                        Pooled with public prose it would flatten both.

Usage:
    python3 harvest_sessions.py --dry-run
    python3 harvest_sessions.py --out ~/.claude/my-voice/corpus --genre session
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_PROJECTS = Path.home() / ".claude" / "projects"

# Roughly the length of a real corpus piece. Grouping to this keeps per-file
# sampling honest: one enormous file gets read once and counts for as little
# as a fifty-word note, while thousands of tiny ones make the reading step
# unusable.
TARGET_PIECE_WORDS = 800
MIN_MESSAGE_WORDS = 20

# Wrappers the CLI puts in the user turn that the user did not type.
MACHINE_PREFIXES = (
    "<command-name>", "<local-command-", "<system-reminder>", "<command-message>",
    "<command-args>", "<bash-input>", "<bash-stdout>", "<bash-stderr>",
    "Caveat: The messages below", "<user-prompt-submit-hook>",
)

# Blocks the runtime injects into the user turn. They arrive as user-role text
# and read like prose to any filter that only checks the record type, so they
# have to be removed by name. A message that is nothing else falls under the
# word floor afterwards and drops out on its own.
MACHINE_TAGS = (
    "system-reminder", "task-notification", "attachment", "diagnostics",
    "usage", "result", "note", "function_results", "function_calls",
    "ide_selection", "ide_opened_file", "user-prompt-submit-hook",
)

STRIP_BLOCKS = [
    re.compile(r"<(%s)\b.*?</\1>" % "|".join(MACHINE_TAGS), re.DOTALL | re.IGNORECASE),
    # Self-closing or unterminated variants of the same injections.
    re.compile(r"<(?:task-id|tool-use-id|output-file|status|summary|subagent_tokens|"
               r"tool_uses|duration_ms|agent_count|agents_[a-z_]+)>[^<]*</[a-z_-]+>",
               re.IGNORECASE),
    re.compile(r"<local-command-[a-z]+>.*?</local-command-[a-z]+>", re.DOTALL),
    re.compile(r"<command-[a-z]+>.*?</command-[a-z]+>", re.DOTALL),
    # Fenced code, pasted logs, stack traces — pasted, not written.
    re.compile(r"```.*?```", re.DOTALL),
    # CLI placeholders for content the user attached rather than typed.
    re.compile(r"\[(?:Pasted text[^\]]*|Image #\d+[^\]]*|Request interrupted[^\]]*)\]"),
]

# Redaction runs before anything reaches disk. Ordered longest-pattern-first so
# a key inside a URL is caught as a key rather than half-caught as a URL.
REDACTIONS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[email]"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|ghu|ghs|xox[baprs])[-_][A-Za-z0-9_-]{16,}\b"), "[key]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[aws-key]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[jwt]"),
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "[hash]"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "[uuid]"),
    (re.compile(r"https?://\S*[?&](?:token|key|secret|password|auth)=\S+"), "[url-with-token]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[ip]"),
]

# Mechanical slips only — transpositions, dropped letters, missing apostrophes.
#
# What is deliberately NOT corrected: grammar, idiom, article use, subject-verb
# agreement, regional spelling. Those are not errors, they are the writer, and
# they are a large part of what separates their prose from generated prose.
# "it worth the shot" and "such concept" survive; "wiht" does not.
#
# Nothing lands here on the strength of a spellchecker alone. Every entry was
# checked against the writer's actual usage, because the automatic candidates
# included "it's"->"its", "apps"->"apis" and "behaviour"->"behavior", each of
# which would have corrupted correct text.
TYPO_MAP = {
    # transpositions and dropped letters
    "otehr": "other", "chanegs": "changes", "managament": "management",
    "yoru": "your", "shold": "should", "shoudl": "should", "genearted": "generated",
    "curent": "current", "mermain": "mermaid", "sesison": "session",
    "numebrs": "numbers", "alrwady": "already", "frature": "feature",
    "indedd": "indeed", "necesary": "necessary", "necesasry": "necessary",
    "necesarily": "necessarily", "convenstional": "conventional",
    "convension": "convention", "valut": "vault", "easlier": "easier",
    "connetced": "connected", "befoer": "before", "sicne": "since",
    "cluade": "claude", "cladue": "claude", "youself": "yourself",
    "enforement": "enforcement", "proeprly": "properly", "freamework": "framework",
    "theit": "their", "betetr": "better", "commadn": "command", "beanch": "branch",
    "banch": "branch", "mesage": "message", "mssages": "messages",
    "sumulate": "simulate", "commeit": "commit", "commti": "commit",
    "commtis": "commits", "reviw": "review", "custoemr": "customer",
    "custoemrs": "customers", "scustomer": "customer", "delovery": "delivery",
    "delivert": "delivery", "exosting": "existing", "slose": "close",
    "whic": "which", "whle": "while", "evey": "every", "reqeust": "request",
    "cldeaner": "cleaner", "epecially": "especially", "espeically": "especially",
    "procedd": "proceed", "powerfull": "powerful", "guture": "future",
    "breacking": "breaking", "rthat": "that", "wortks": "works",
    "nucketing": "bucketing", "improvment": "improvement",
    "udnerstand": "understand", "understang": "understand", "innstall": "install",
    "instrall": "install", "welll": "well", "explaning": "explaining",
    "breifly": "briefly", "eaxctly": "exactly", "workign": "working",
    "mustr": "must", "howwver": "however", "dscription": "description",
    "ploject": "project", "usses": "uses", "tivial": "trivial",
    "exprience": "experience", "lookig": "looking", "wuick": "quick",
    "equick": "quick", "stiull": "still", "stil": "still", "separaet": "separate",
    "seesm": "seems", "corerctly": "correctly", "corerct": "correct",
    "hten": "then", "thse": "these", "momnent": "moment", "histpry": "history",
    "flase": "false", "reotate": "rotate", "mentioed": "mentioned",
    "instaged": "unstaged", "securoty": "security", "deployaed": "deployed",
    "thiis": "this", "direcvtly": "directly", "smimilar": "similar",
    "canno": "cannot", "prblem": "problem", "setip": "setup", "lcost": "cost",
    "compse": "compose", "decising": "deciding", "kickc": "kick",
    "nrelease": "release", "updatign": "updating", "wiht": "with",
    "hte": "the", "nto": "not", "agains": "against", "extrated": "extracted",
    "usefull": "useful", "sceintific": "scientific", "requiremets": "requirements",
    "fodlers": "folders", "cmoponenet": "component", "prouced": "produced",
    "resuts": "results", "performace": "performance", "loit": "lot",
    # missing apostrophes. "wont", "lets", "ill" and "id" are excluded on
    # purpose — each is also a real word, and guessing wrong rewrites a
    # correct sentence into a broken one.
    "dont": "don't", "doesnt": "doesn't", "didnt": "didn't", "isnt": "isn't",
    "arent": "aren't", "wasnt": "wasn't", "werent": "weren't",
    "cant": "can't", "couldnt": "couldn't", "wouldnt": "wouldn't",
    "shouldnt": "shouldn't", "hasnt": "hasn't", "havent": "haven't",
    "hadnt": "hadn't", "thats": "that's", "whats": "what's",
    "theres": "there's", "heres": "here's", "youre": "you're",
    "theyre": "they're", "ive": "I've", "didn;t": "didn't",
}

PROFANITY = {
    "fuck", "fucking", "fucked", "fucks", "shit", "shitty", "bullshit", "crap",
    "damn", "damned", "goddamn", "ass", "asshole", "bastard", "bitch", "dick",
    "piss", "pissed", "wtf", "stfu", "idiot", "idiotic", "stupid", "moron",
    "dumb", "useless", "garbage", "trash", "pathetic", "nonsense", "ridiculous",
}

# Frustration aimed at the assistant. Individually weak, so a message needs
# more than one before it is dropped — "you keep" alone is ordinary feedback.
ANGER_MARKERS = [
    re.compile(r"\byou (keep|again|always|never|still)\b", re.I),
    re.compile(r"\b(again|still)\?!", re.I),
    re.compile(r"\b(i (told|asked) you)\b", re.I),
    re.compile(r"\b(how many times|for the (last|third|fourth) time)\b", re.I),
    re.compile(r"\b(stop|enough|forget it|never mind)\b\W*$", re.I),
    re.compile(r"[!?]{3,}"),
    re.compile(r"\b(waste|wasted|wasting) (my )?(time|hours|money)\b", re.I),
    re.compile(r"\b(broke|broken|destroyed|ruined) (everything|it again|my)\b", re.I),
]


def strip_machine_text(text: str) -> str:
    for rx in STRIP_BLOCKS:
        text = rx.sub(" ", text)
    return text.strip()


def redact(text: str) -> str:
    for rx, repl in REDACTIONS:
        text = rx.sub(repl, text)
    return text


_TYPO_RX = re.compile(
    r"\b(%s)\b" % "|".join(sorted((re.escape(k) for k in TYPO_MAP), key=len, reverse=True)),
    re.IGNORECASE)


def fix_typos(text: str, extra: Optional[Dict[str, str]] = None) -> Tuple[str, int]:
    """Repair mechanical slips, preserving the case the writer used.

    Whole-word only. A substring pass would turn "internal" into "in'ternal"
    the moment a contraction entry matched inside another word.
    """
    table = dict(TYPO_MAP)
    if extra:
        table.update(extra)
    count = 0

    def repl(m: "re.Match") -> str:
        nonlocal count
        found = m.group(0)
        fixed = table.get(found.lower())
        if fixed is None:
            return found
        count += 1
        if found.isupper() and len(found) > 1:
            return fixed.upper()
        if found[0].isupper():
            return fixed[0].upper() + fixed[1:]
        return fixed

    rx = _TYPO_RX if extra is None else re.compile(
        r"\b(%s)\b" % "|".join(sorted((re.escape(k) for k in table), key=len, reverse=True)),
        re.IGNORECASE)
    return rx.sub(repl, text), count


def load_extra_typos(path: Optional[Path]) -> Dict[str, str]:
    """Optional `wrong -> right` overrides, one per line as `wrong=right`."""
    if path is None or not path.exists():
        return {}
    out: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        bad, good = line.split("=", 1)
        if bad.strip():
            out[bad.strip().lower()] = good.strip()
    return out


def shouting_ratio(text: str) -> float:
    words = re.findall(r"\b[A-Za-z]{3,}\b", text)
    if not words:
        return 0.0
    return sum(1 for w in words if w.isupper()) / len(words)


def is_heated(text: str) -> bool:
    lowered = set(re.findall(r"\b[a-z']+\b", text.lower()))
    if lowered & PROFANITY:
        return True
    hits = sum(1 for rx in ANGER_MARKERS if rx.search(text))
    if hits >= 2:
        return True
    # Sustained shouting in a message of any substance.
    if shouting_ratio(text) > 0.25 and len(text.split()) >= 8:
        return True
    return False


def is_user_authored(rec: dict) -> bool:
    """True only for text a person typed into the prompt.

    A user-role record can also be a tool result, a slash-command stub, a hook
    firing, or one agent's instructions to another. All of those would read as
    the user's writing and none of them are.
    """
    if rec.get("type") != "user" or rec.get("isMeta"):
        return False
    if rec.get("isSidechain"):
        return False
    if "toolUseResult" in rec:
        return False
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") != "text" for b in content):
            return False
        content = " ".join(b.get("text", "") for b in content
                           if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str) or not content.strip():
        return False
    if content.lstrip().startswith(MACHINE_PREFIXES):
        return False
    return True


def message_text(rec: dict) -> str:
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content
                           if isinstance(b, dict) and b.get("type") == "text")
    return content if isinstance(content, str) else ""


def harvest(projects_dir: Path,
            extra_typos: Optional[Dict[str, str]] = None) -> Tuple[List[dict], Counter]:
    stats: Counter = Counter()
    kept: List[dict] = []
    seen: set = set()

    for path in sorted(projects_dir.rglob("*.jsonl")):
        stats["files"] += 1
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError:
            stats["unreadable"] += 1
            continue
        with handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("type") == "user":
                    stats["user_records"] += 1
                if not is_user_authored(rec):
                    continue
                stats["typed"] += 1

                text = strip_machine_text(message_text(rec))
                if not text:
                    stats["dropped_machine_only"] += 1
                    continue
                if len(text.split()) < MIN_MESSAGE_WORDS:
                    stats["dropped_too_short"] += 1
                    continue
                if is_heated(text):
                    stats["dropped_heated"] += 1
                    continue

                text = redact(text)
                text, fixed = fix_typos(text, extra_typos)
                stats["typos_fixed"] += fixed
                key = re.sub(r"\s+", " ", text.lower())[:220]
                if key in seen:
                    stats["dropped_duplicate"] += 1
                    continue
                seen.add(key)

                kept.append({
                    "text": text,
                    "timestamp": rec.get("timestamp") or "",
                    "project": path.parent.name,
                    "words": len(text.split()),
                })
                stats["kept"] += 1
    return kept, stats


# A message this long was composed, not dashed off. It stands on its own.
STANDALONE_WORDS = 250


def group_into_pieces(messages: List[dict], target_words: int
                      ) -> Tuple[List[List[dict]], List[dict]]:
    """Split into standalone long messages and grouped short ones.

    Chunking everything chronologically mixes a considered five-paragraph
    explanation with a run of one-line instructions, and the resulting file
    describes a rhythm the writer never actually wrote — measurably so: those
    blended chunks came out with sentence averages a third below anything in
    the writer's real prose.

    Long messages are also the most valuable thing in here. They are the
    long-form first-person writing that corpora built from published work
    almost never contain, because nobody publishes at that length as often as
    they explain something properly in a chat window.
    """
    ordered = sorted(messages, key=lambda m: m["timestamp"])
    standalone = [m for m in ordered if m["words"] >= STANDALONE_WORDS]
    short = [m for m in ordered if m["words"] < STANDALONE_WORDS]

    grouped: List[List[dict]] = []
    current: List[dict] = []
    running = 0
    for msg in short:
        current.append(msg)
        running += msg["words"]
        if running >= target_words:
            grouped.append(current)
            current, running = [], 0
    if current:
        grouped.append(current)
    return grouped, standalone


def render_standalone(msg: dict) -> str:
    return "# Session note (%s)\n\n%s\n" % ((msg["timestamp"] or "")[:10],
                                            msg["text"].strip())


def render_piece(piece: List[dict], index: int) -> str:
    first = (piece[0]["timestamp"] or "")[:10]
    last = (piece[-1]["timestamp"] or "")[:10]
    span = first if first == last else "%s to %s" % (first, last)
    out = ["# Session notes %03d (%s)" % (index, span), ""]
    out.append("Unedited messages I typed while working. Verbatim apart from "
               "redaction and typo correction.")
    out.append("")
    for msg in piece:
        out.append(msg["text"].strip())
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projects", type=Path, default=DEFAULT_PROJECTS)
    ap.add_argument("--out", type=Path, default=None,
                    help="Corpus directory to write pieces into.")
    ap.add_argument("--prefix", default="session",
                    help="Filename prefix for generated pieces (default 'session').")
    ap.add_argument("--target-words", type=int, default=TARGET_PIECE_WORDS)
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be harvested, write nothing.")
    ap.add_argument("--sample", type=int, default=0,
                    help="Print N harvested messages so you can see what it captured.")
    ap.add_argument("--typos", type=Path, default=None,
                    help="Extra `wrong=right` typo corrections, one per line.")
    args = ap.parse_args()

    if not args.projects.is_dir():
        print("No session transcripts at %s" % args.projects, file=sys.stderr)
        return 2

    messages, stats = harvest(args.projects, load_extra_typos(args.typos))
    total_words = sum(m["words"] for m in messages)

    print("HARVEST")
    print("  transcripts scanned      %d" % stats["files"])
    print("  user-role records        %d" % stats["user_records"])
    print("  typed by you             %d" % stats["typed"])
    print("  dropped, machine-only    %d" % stats["dropped_machine_only"])
    print("  dropped, under %2d words  %d" % (MIN_MESSAGE_WORDS, stats["dropped_too_short"]))
    print("  dropped, heated          %d" % stats["dropped_heated"])
    print("  dropped, duplicate       %d" % stats["dropped_duplicate"])
    print("  typos corrected          %d" % stats["typos_fixed"])
    print("  KEPT                     %d messages, %d words" % (stats["kept"], total_words))

    if args.sample:
        print()
        print("SAMPLE")
        step = max(len(messages) // args.sample, 1)
        for msg in messages[::step][:args.sample]:
            print("  --- %s (%d words)" % (msg["timestamp"][:19], msg["words"]))
            for line in msg["text"].splitlines()[:6]:
                print("    " + line[:110])

    grouped, standalone = group_into_pieces(messages, args.target_words)
    print()
    print("  %d long messages (>=%d words) kept whole as their own pieces"
          % (len(standalone), STANDALONE_WORDS))
    print("  %d shorter messages grouped into %d pieces of roughly %d words"
          % (sum(len(g) for g in grouped), len(grouped), args.target_words))

    if args.dry_run or args.out is None:
        print()
        print("  (dry run — nothing written)")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    written = []
    for i, msg in enumerate(standalone, start=1):
        dest = args.out / ("%s-long-%03d.md" % (args.prefix, i))
        dest.write_text(render_standalone(msg), encoding="utf-8")
        written.append(dest.name)
    for i, piece in enumerate(grouped, start=1):
        dest = args.out / ("%s-notes-%03d.md" % (args.prefix, i))
        dest.write_text(render_piece(piece, i), encoding="utf-8")
        written.append(dest.name)
    print()
    print("  wrote %d files to %s" % (len(written), args.out))
    print("  Read a few before trusting them. Redaction is best-effort over text")
    print("  that was never written to be published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
