#!/usr/bin/env python3
"""
your-voice safety net.

Mechanical typography + structural-drift check for catastrophic drift from
the corpus baseline. NOT a voice judge. NOT a quality scorer. A smoke alarm
for known catastrophe modes (zero contractions in long prose, headings
everywhere, formal numbered lists where the corpus would use prose, and —
when an input is provided — structural mimicry of that input).

Usage:
    python3 safety_net.py <draft.md>
    python3 safety_net.py <draft.md> --input <input.md>

The --input flag is for the rewrite case: the script then also compares
the draft's structural fingerprint (section labels, list shape, paragraph
count) to the input's, and flags excessive overlap.

Outputs violations to stdout. Always exits 0 (advisory).

Adding new anti-tic patterns: append to ANTI_TIC_PATTERNS below.
"""

import json
import re
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parent.parent
CORPUS_DIR = SKILL_DIR / "corpus"
STATS_CACHE = Path(__file__).resolve().parent / "corpus_stats.json"

# Common contractions. Lowercased.
CONTRACTIONS = {
    "i'm", "i've", "i'd", "i'll",
    "you're", "you've", "you'd", "you'll",
    "we're", "we've", "we'd", "we'll",
    "they're", "they've", "they'd", "they'll",
    "he's", "she's", "it's", "that's", "there's", "here's",
    "what's", "who's", "where's", "how's",
    "isn't", "aren't", "wasn't", "weren't",
    "doesn't", "don't", "didn't",
    "can't", "couldn't", "won't", "wouldn't", "shouldn't",
    "hasn't", "haven't", "hadn't",
    "let's", "y'all",
}

# Patterns flagged by anti-corpus. Add more as they're identified.
ANTI_TIC_PATTERNS: List[Tuple[str, str]] = [
    (
        r"\bis not a typo\b",
        "anti-corpus: 'is not a typo' construct. The writer prefers 'yes, you read that correctly' (if that pattern is in the corpus).",
    ),
    (
        r"^[#]{2,6}\s",  # any line starting with ## through ######
        "headings: ## section headings rarely appear in corpus; light bold is preferred.",
    ),
]

# Pieces shorter than this are excluded from variance/density stats
# (too small to give a reliable signal).
MIN_WORDS_FOR_STATS = 80


def normalize_apostrophes(text: str) -> str:
    # U+2019 (right single quote) and U+02BC (modifier letter apostrophe)
    # → straight apostrophe, so contraction matching is uniform.
    return text.replace("’", "'").replace("ʼ", "'")


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def sentence_count(text: str) -> int:
    stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    sentences = [s for s in re.split(r"[.!?]+", stripped) if s.strip()]
    return max(len(sentences), 1)


def contraction_count(text: str) -> int:
    text = normalize_apostrophes(text)
    tokens = re.findall(r"\b[\w']+\b", text.lower())
    return sum(1 for t in tokens if t in CONTRACTIONS)


def paragraphs(text: str) -> List[str]:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def heading_density(text: str) -> float:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    headings = sum(1 for ln in lines if re.match(r"^#{1,6}\s", ln))
    return headings / len(lines)


def list_density(text: str) -> float:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    list_lines = sum(
        1 for ln in lines
        if re.match(r"^\s*[-*+]\s", ln) or re.match(r"^\s*\d+[.)]\s", ln)
    )
    return list_lines / len(lines)


def paragraph_length_variance(text: str) -> float:
    paras = paragraphs(text)
    lengths = [word_count(p) for p in paras]
    if len(lengths) < 2:
        return 0.0
    return statistics.stdev(lengths)


def piece_metrics(text: str) -> Dict[str, float]:
    wc = word_count(text)
    sc = sentence_count(text)
    return {
        "word_count": wc,
        "contraction_ratio": contraction_count(text) / sc,
        "heading_density": heading_density(text),
        "list_density": list_density(text),
        "paragraph_variance": paragraph_length_variance(text),
        "paragraph_count": len(paragraphs(text)),
    }


def build_corpus_stats() -> Dict:
    pieces: Dict[str, Dict[str, float]] = {}
    for path in sorted(f for f in CORPUS_DIR.glob("*.md") if f.name.lower() != "readme.md"):
        text = path.read_text()
        pieces[path.name] = piece_metrics(text)

    long_pieces = [m for m in pieces.values() if m["word_count"] >= MIN_WORDS_FOR_STATS]
    if not long_pieces:
        long_pieces = list(pieces.values())

    # Prose-style pieces: low list density. These are the right baseline for
    # contraction usage in flowing prose. Formal-list pieces (10-the-edge,
    # 09-async) legitimately have zero contractions because they're enumerated
    # business docs — letting them set the floor would defeat the check.
    prose_pieces = [m for m in long_pieces if m["list_density"] < 0.15]
    if not prose_pieces:
        prose_pieces = long_pieces

    def span(key: str, src) -> Dict[str, float]:
        vals = [m[key] for m in src]
        return {
            "min": min(vals),
            "max": max(vals),
            "mean": statistics.mean(vals),
        }

    return {
        "pieces": pieces,
        "thresholds": {
            "contraction_ratio_prose": span("contraction_ratio", prose_pieces),
            "heading_density": span("heading_density", long_pieces),
            "list_density": span("list_density", long_pieces),
            "paragraph_variance": span("paragraph_variance", long_pieces),
        },
    }


def get_corpus_stats() -> Dict:
    corpus_files = [f for f in CORPUS_DIR.glob("*.md") if f.name.lower() != "readme.md"]
    if not corpus_files:
        return {"pieces": {}, "thresholds": {}}
    corpus_mtime = max(p.stat().st_mtime for p in corpus_files)
    if STATS_CACHE.exists():
        try:
            cached = json.loads(STATS_CACHE.read_text())
            if cached.get("_corpus_mtime", 0) >= corpus_mtime:
                return cached
        except Exception:
            pass
    stats = build_corpus_stats()
    stats["_corpus_mtime"] = corpus_mtime
    STATS_CACHE.write_text(json.dumps(stats, indent=2))
    return stats


def _normalize_label(s: str) -> str:
    # Lowercase, normalize dash variants (em, en, hyphen) to a single form, collapse whitespace.
    s = s.strip().lower()
    s = s.replace("—", "-").replace("–", "-").replace("−", "-")
    s = re.sub(r"\s+", " ", s)
    return s


def section_labels(text: str) -> List[str]:
    """
    Extract ordered section labels from a draft.
    Recognizes both `## Heading` and standalone `**Bold Label**` lines.
    Normalized to lowercase with dashes folded so em-dash / en-dash variants
    do not count as different labels.
    """
    labels: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if m:
            labels.append(_normalize_label(m.group(1)))
            continue
        # Standalone bold-only line, treated as a section label
        m = re.match(r"^\*\*([^*]+)\*\*\s*$", line)
        if m:
            labels.append(_normalize_label(m.group(1)))
    return labels


def list_item_count(text: str) -> int:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return sum(
        1 for ln in text.splitlines()
        if re.match(r"^\s*[-*+]\s", ln) or re.match(r"^\s*\d+[.)]\s", ln)
    )


def structural_fingerprint(text: str) -> Dict:
    return {
        "labels": section_labels(text),
        "paragraph_count": len(paragraphs(text)),
        "list_item_count": list_item_count(text),
    }


def jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(len(sa | sb), 1)


def ordered_overlap(a: List[str], b: List[str]) -> float:
    """
    Fraction of input labels (a) that also appear in (b) in the same relative
    order. Skips labels that aren't in b without losing position for the rest.
    Returns 1.0 when every input label is present in b in its original order.
    """
    if not a:
        return 0.0
    j = 0
    matched = 0
    for label in a:
        # Search forward in b starting at j; if found, match and advance past it.
        for k in range(j, len(b)):
            if b[k] == label:
                matched += 1
                j = k + 1
                break
    return matched / len(a)


def structural_drift(input_path: Path, draft_path: Path) -> List[str]:
    """
    Compare structural fingerprint of input vs draft. Flag excessive overlap —
    the failure mode where voice gets applied as a coat of paint over a
    preserved input skeleton.
    """
    violations: List[str] = []
    input_text = input_path.read_text()
    draft_text = draft_path.read_text()

    inp = structural_fingerprint(input_text)
    drf = structural_fingerprint(draft_text)

    if inp["labels"] and drf["labels"]:
        jac = jaccard(inp["labels"], drf["labels"])
        ord_ovl = ordered_overlap(inp["labels"], drf["labels"])
        if jac >= 0.6 and ord_ovl >= 0.6:
            violations.append(
                "structural mimicry: %d of %d input section labels reused (jaccard=%.2f, ordered overlap=%.2f). "
                "The draft inherits the input's section structure instead of rebuilding from voice_model.md. "
                "Re-do the abstraction step (write ideas.md from scratch, then draft from ideas + voice_model — "
                "do not reopen the input)."
                % (
                    len(set(inp["labels"]) & set(drf["labels"])),
                    len(inp["labels"]),
                    jac,
                    ord_ovl,
                )
            )

    # List-shape mimicry: if both input and draft have lists with similar item counts
    if inp["list_item_count"] >= 3 and drf["list_item_count"] >= 3:
        diff_ratio = abs(inp["list_item_count"] - drf["list_item_count"]) / max(
            inp["list_item_count"], drf["list_item_count"]
        )
        if diff_ratio <= 0.15:  # within 15% of input's list count
            violations.append(
                "list-shape mimicry: input has %d list items, draft has %d. "
                "Per the writer's annotations, the writer favors storytelling over bullet lists; "
                "preserving the input's list shape suggests structure was copied rather than rebuilt."
                % (inp["list_item_count"], drf["list_item_count"])
            )

    return violations


def check(draft_path: Path, input_path: Optional[Path] = None) -> List[str]:
    text = draft_path.read_text()
    violations: List[str] = []

    # Structural drift check (only when an input is provided)
    if input_path is not None:
        violations.extend(structural_drift(input_path, draft_path))

    # Anti-tic pattern matches (run on every draft, regardless of length)
    for pattern, msg in ANTI_TIC_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            violations.append("anti-tic: " + msg)

    wc = word_count(text)
    if wc < MIN_WORDS_FOR_STATS:
        return violations

    stats = get_corpus_stats()
    th = stats.get("thresholds", {})
    if not th:
        return violations

    metrics = piece_metrics(text)

    # Contraction ratio: the cleanest catastrophe signal.
    # Bypassed only when the draft is a list-dominated genre (formal enumerated
    # docs). Anything else needs contractions — long-form prose with a single
    # embedded list still counts as prose.
    cr = th.get("contraction_ratio_prose", {})
    if cr and metrics["list_density"] < 0.50:
        floor = max(cr["min"] * 0.5, 0.05)  # ≈ 1 contraction per 20 sentences floor
        if metrics["contraction_ratio"] < floor:
            violations.append(
                "contractions too rare for prose: %.3f per sentence; "
                "The writer's prose corpus runs %.3f-%.3f. "
                "Strong signal of corporate-memo voice rather than the writer's natural register."
                % (metrics["contraction_ratio"], cr["min"], cr["max"])
            )

    # Heading density (also picked up by anti-tic, but flag the proportion too)
    hd = th.get("heading_density", {})
    if hd and metrics["heading_density"] > hd["max"] * 1.5 + 0.02:
        violations.append(
            "heading density too high: %.3f; corpus max %.3f. "
            "Light bold is preferred over ## section headings."
            % (metrics["heading_density"], hd["max"])
        )

    # List density
    ld = th.get("list_density", {})
    if ld and metrics["list_density"] > ld["max"] * 1.3 + 0.05:
        violations.append(
            "list density too high: %.3f; corpus max %.3f. "
            "Per the writer's annotations, the writer favors storytelling over bullet lists."
            % (metrics["list_density"], ld["max"])
        )

    # Paragraph variance (uniformity check)
    pv = th.get("paragraph_variance", {})
    if pv and metrics["paragraph_count"] >= 4:
        if metrics["paragraph_variance"] < pv["min"] * 0.5:
            violations.append(
                "paragraphs too uniform: stdev=%.1f words; corpus min %.1f. "
                "The writer mixes one-line punches with longer prose; the draft reads as block-shaped."
                % (metrics["paragraph_variance"], pv["min"])
            )

    return violations


def main() -> int:
    args = sys.argv[1:]
    input_path: Optional[Path] = None
    positional: List[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--input":
            i += 1
            if i >= len(args):
                print("Usage: safety_net.py <draft.md> [--input <input.md>]", file=sys.stderr)
                return 2
            input_path = Path(args[i])
        else:
            positional.append(a)
        i += 1

    if len(positional) != 1:
        print("Usage: safety_net.py <draft.md> [--input <input.md>]", file=sys.stderr)
        return 2

    draft_path = Path(positional[0])
    if not draft_path.exists():
        print("Draft not found: " + str(draft_path), file=sys.stderr)
        return 2
    if input_path is not None and not input_path.exists():
        print("Input not found: " + str(input_path), file=sys.stderr)
        return 2

    violations = check(draft_path, input_path)
    if not violations:
        print("NO_VIOLATIONS")
        return 0
    print("VIOLATIONS (%d):" % len(violations))
    for v in violations:
        print("  - " + v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
