#!/usr/bin/env python3
"""
Shared text measurements for the my-voice gates.

Pure functions only — nothing here knows where the corpus lives. That is
safety_net.py's job. Keeping the measurements path-free means this file is
byte-identical across every packaging of the skill, so a threshold tuned in
one place behaves the same everywhere.

Two families of measurement, and the split between them is deliberate:

  RHYTHM   sentence length, its spread, the share of long sentences. Measured
           on every corpus piece without exception, so a per-draft band built
           from them will not fail the corpus that defined it.

  MARKERS  a writer's signature punctuation (a trailing "..", a soft "!"),
           contractions, hedges. These are ABSENT from a large minority of
           real pieces — a writer who uses "!" in half of what they write is
           still that writer in the other half. A per-draft floor on a marker
           therefore fails genuine writing roughly as often as it catches
           drift, which is why markers are checked across a WINDOW of recent
           drafts instead (see trailing_window_report).
"""
import fnmatch
import re
import statistics
from collections import Counter
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Bump when a measurement changes shape. Any cache carrying a different value
# is recomputed rather than trusted — otherwise a corpus whose mtime has not
# moved keeps serving thresholds derived from the previous definitions.
SCHEMA = 2

# A sentence at or above this many words counts as "long". The figure is not
# arbitrary: it is the point at which the corpus and Claude-default prose
# separate most cleanly.
LONG_SENTENCE_WORDS = 35
SHORT_SENTENCE_WORDS = 7

# Below this, a piece is too small for its rates to mean anything.
MIN_WORDS_FOR_STATS = 80

# Rhythm bands are built from, and applied to, pieces at least this long.
# Calibration is what set the figure: banded on everything down to 80 words,
# the corpus rejected nearly half of itself, because a 90-word note swings
# between a 10-word average and a 36-word one on the strength of two
# sentences. Nothing being gated here is that short.
MIN_WORDS_FOR_RHYTHM = 250

# A piece needs at least this many sentences before "it contains no long
# sentence" means anything. Below it, absence is sample size, not style.
MIN_SENTENCES_FOR_LONG_CHECK = 15

CONTRACTIONS = {
    "i'm", "i've", "i'd", "i'll",
    "we're", "we've", "we'd", "we'll",
    "you're", "you've", "you'd", "you'll",
    "they're", "they've", "they'd", "they'll",
    "he's", "she's", "it's", "that's", "there's", "here's",
    "what's", "who's", "where's", "how's",
    "isn't", "aren't", "wasn't", "weren't",
    "doesn't", "don't", "didn't",
    "can't", "couldn't", "won't", "wouldn't", "shouldn't",
    "hasn't", "haven't", "hadn't",
    "let's", "y'all",
}

HEDGE = re.compile(
    r"\b(i believe|i think|i suppose|i find that|i guess|i'd say|i would say|"
    r"most likely|i'm not sure|i am not sure|i cannot say|i can't say|it seems|"
    r"probably|perhaps|maybe|i assume|as far as i)\b", re.IGNORECASE)

# A trailing ".." — two dots, not an ellipsis, not the tail of a longer run.
DOTDOT = re.compile(r"(?<!\.)\.\.(?!\.)")


def normalize_apostrophes(text: str) -> str:
    return text.replace("’", "'").replace("ʼ", "'")


def strip_noise(text: str) -> str:
    """Remove everything that would corrupt a sentence or word count.

    URLs matter more than they look: an unstripped link splits into four or
    five "sentences" at its dots, which drags mean sentence length down and
    makes a link-heavy piece look clipped when it is not.
    """
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"^\s*\|.*\|\s*$", " ", text, flags=re.MULTILINE)
    return text


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def words(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def is_label_line(line: str) -> bool:
    """A heading, date marker or bold caption — not a sentence.

    These wreck rhythm measurement. "Day 1. Ground Zero" splits into two
    two-word "sentences", and a piece with a dozen such markers reports an
    average sentence length half its real one. The band built from that
    corpus then rejects the writer's own prose for being too long.

    The test is deliberately narrow: short, and not ending in terminal
    punctuation. A genuine short sentence ("It's that simple.") ends in a
    full stop and survives.
    """
    s = line.strip()
    if not s:
        return False
    if re.match(r"^#{1,6}\s", s):
        return True
    if re.match(r"^\*\*[^*]+\*\*:?$", s):
        return True
    return len(s.split()) < 8 and not re.search(r"[.!?]$", s)


def sentences(text: str) -> List[str]:
    """Split into sentences, treating ".." as a terminator like any other.

    A writer whose habitual terminator is ".." would otherwise have every
    trailing thought glued to the sentence after it.
    """
    kept = [ln for ln in strip_noise(text).splitlines() if not is_label_line(ln)]
    parts = re.split(r"[.!?]+", "\n".join(kept))
    return [p.strip() for p in parts if p.strip()]


def sentence_count(text: str) -> int:
    return max(len(sentences(text)), 1)


def sentence_lengths(text: str) -> List[int]:
    return [len(s.split()) for s in sentences(text)]


def contraction_count(text: str) -> int:
    text = normalize_apostrophes(strip_noise(text))
    tokens = re.findall(r"\b[\w']+\b", text.lower())
    return sum(1 for t in tokens if t in CONTRACTIONS)


def paragraphs(text: str) -> List[str]:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def heading_density(text: str) -> float:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    return sum(1 for ln in lines if re.match(r"^#{1,6}\s", ln)) / len(lines)


def list_density(text: str) -> float:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    n = sum(1 for ln in lines
            if re.match(r"^\s*[-*+]\s", ln) or re.match(r"^\s*\d+[.)]\s", ln))
    return n / len(lines)


def paragraph_length_variance(text: str) -> float:
    lengths = [word_count(p) for p in paragraphs(text)]
    if len(lengths) < 2:
        return 0.0
    return statistics.stdev(lengths)


def piece_metrics(text: str) -> Dict[str, float]:
    wc = word_count(strip_noise(text))
    sc = sentence_count(text)
    lens = sentence_lengths(text)
    per_1k = (lambda n: 1000.0 * n / wc) if wc else (lambda n: 0.0)
    return {
        "word_count": wc,
        # Rhythm — dense, no zeros, safe to band per draft.
        "sent_mean": statistics.mean(lens) if lens else 0.0,
        "sent_sd": statistics.stdev(lens) if len(lens) > 1 else 0.0,
        "long_pct": 100.0 * sum(1 for x in lens if x >= LONG_SENTENCE_WORDS) / max(len(lens), 1),
        "short_pct": 100.0 * sum(1 for x in lens if x < SHORT_SENTENCE_WORDS) / max(len(lens), 1),
        # Markers — sparse, frequently zero, only meaningful across a window.
        "dotdot_per_1k": per_1k(len(DOTDOT.findall(text))),
        "bang_per_1k": per_1k(text.count("!")),
        "hedge_per_1k": per_1k(len(HEDGE.findall(strip_noise(text)))),
        "contraction_per_1k": per_1k(contraction_count(text)),
        # Retained from the original gate.
        "contraction_ratio": contraction_count(text) / sc,
        "heading_density": heading_density(text),
        "list_density": list_density(text),
        "paragraph_variance": paragraph_length_variance(text),
        "paragraph_count": len(paragraphs(text)),
    }


# ---------------------------------------------------------------- percentiles

def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return float(vals[0])
    k = (len(vals) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def band(values: Sequence[float], p_lo: float, p_hi: float,
         slack_lo: float, slack_hi: float) -> Dict[str, float]:
    """A tolerance band from a corpus distribution.

    Percentiles rather than min/max so one unusual piece cannot widen the band
    until it accepts anything, then slack on each side so a draft sitting just
    outside the observed range is not called a violation.
    """
    return {
        "lo": percentile(values, p_lo) * slack_lo,
        "hi": percentile(values, p_hi) * slack_hi,
        "p15": percentile(values, 15),
        "p25": percentile(values, 25),
        "zero_share": (sum(1 for v in values if v == 0) / len(values)) if values else 0.0,
        "p50": percentile(values, 50),
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
        "n": len(values),
    }


# --------------------------------------------------------------------- genres

def load_genres(genres_file) -> Dict[str, List[str]]:
    """Parse an optional `genre: glob, glob` map.

    Absent file means one undifferentiated pool, which is what the gate did
    before genres existed. Register varies enough between a public essay and a
    colleague-facing comment that pooling them makes every threshold describe
    a writer who does not exist, but that is the user's call to make, not a
    default to impose.
    """
    if genres_file is None or not genres_file.exists():
        return {}
    out: Dict[str, List[str]] = {}
    for raw in genres_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        name, globs = line.split(":", 1)
        pats = [g.strip() for g in globs.split(",") if g.strip()]
        if name.strip() and pats:
            out[name.strip()] = pats
    return out


def genre_of(filename: str, genres: Dict[str, List[str]]) -> Optional[str]:
    for name, pats in genres.items():
        if any(fnmatch.fnmatch(filename, p) for p in pats):
            return name
    return None


# ------------------------------------------------------- stylistic similarity

def frequency_profile(text: str, vocabulary: Sequence[str]) -> List[float]:
    ws = words(strip_noise(text))
    n = max(len(ws), 1)
    counts = Counter(ws)
    return [100.0 * counts[w] / n for w in vocabulary]


def build_vocabulary(texts: Iterable[str], top_n: int = 120) -> List[str]:
    pooled: Counter = Counter()
    for t in texts:
        pooled.update(words(strip_noise(t)))
    return [w for w, _ in pooled.most_common(top_n)]


def delta(profile_a: Sequence[float], profile_b: Sequence[float],
          means: Sequence[float], sds: Sequence[float]) -> float:
    """Burrows's Delta: mean absolute difference of z-scored word frequencies.

    Burrows, J.F. (2002), "'Delta': a Measure of Stylistic Difference and a
    Guide to Likely Authorship". The standard authorship measure, used here for
    the one thing it is uniquely good at: telling whether two texts were shaped
    the same way, independent of what they are about.
    """
    n = len(profile_a)
    if not n:
        return 0.0
    total = 0.0
    for i in range(n):
        s = sds[i] if sds[i] > 1e-9 else 1e-9
        total += abs((profile_a[i] - means[i]) / s - (profile_b[i] - means[i]) / s)
    return total / n


def zparams(profiles: Sequence[Sequence[float]]) -> Tuple[List[float], List[float]]:
    if not profiles:
        return [], []
    n = len(profiles[0])
    means = [statistics.mean(p[i] for p in profiles) for i in range(n)]
    sds = [statistics.stdev([p[i] for p in profiles]) if len(profiles) > 1 else 1.0
           for i in range(n)]
    return means, [s if s > 1e-9 else 1e-9 for s in sds]


def self_similarity(texts: Sequence[str], top_n: int = 120) -> Optional[float]:
    """Mean pairwise Delta within a set of texts.

    A body of real writing varies from piece to piece. Generated writing
    converges on whatever shape the generator finds easiest, and converges
    tighter the more of it there is. That convergence is invisible in any one
    piece and obvious across ten, which is why it is measured over a set: this
    is the number that corresponds to a reader saying the posts have started
    to feel the same.
    """
    if len(texts) < 3:
        return None
    vocab = build_vocabulary(texts, top_n)
    profs = [frequency_profile(t, vocab) for t in texts]
    means, sds = zparams(profs)
    pairs = [delta(profs[i], profs[j], means, sds)
             for i in range(len(profs)) for j in range(i + 1, len(profs))]
    return statistics.mean(pairs) if pairs else None
