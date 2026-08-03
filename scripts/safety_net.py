#!/usr/bin/env python3
"""
my-voice safety net.

Mechanical checks for drift from the corpus baseline. NOT a voice judge. NOT a
quality scorer. Passing it does not mean the draft sounds like the writer;
failing it almost certainly means it does not.

Three layers, and they answer different questions:

  PER-DRAFT   Is THIS piece shaped like the writer's prose? Sentence rhythm,
              typography, structural mimicry of an input, hard rules.

  WINDOW      Have the LAST FEW pieces drifted together? Signature punctuation
              is absent from a large minority of any writer's real pieces, so
              a per-draft floor on it fails genuine writing about as often as
              it catches drift. Across a window the signal is clean.

  FORMULA     Have the recent pieces converged on ONE shape? A body of real
              writing varies piece to piece. Generated writing narrows toward
              whatever the generator finds easiest. No single draft looks
              wrong; the tenth reads as a template. This is the layer that
              corresponds to a reader saying it has started to feel samey.

Usage:
    python3 safety_net.py <draft.md>
    python3 safety_net.py <draft.md> --input <input.md>
    python3 safety_net.py <draft.md> --genre article

Outputs violations to stdout. Always exits 0 (advisory).
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import voice_metrics as vm  # noqa: E402

# Re-exported so the metric functions stay reachable at this module's top level.
from voice_metrics import (  # noqa: E402,F401
    MIN_WORDS_FOR_STATS,
    contraction_count,
    heading_density,
    list_density,
    normalize_apostrophes,
    paragraph_length_variance,
    paragraphs,
    piece_metrics,
    sentence_count,
    word_count,
)

# Your corpus and rules live outside the plugin so an update cannot delete them.
CORPUS_DIR = paths.corpus_dir()
HARD_RULES = paths.hard_rules()
# Derived from the corpus, so it belongs beside the corpus — in the plugin it
# would be silently discarded on every update.
STATS_CACHE = paths.stats_cache()
DRAFT_LOG = paths.runtime_dir() / "draft_log.jsonl"

# How many recent same-genre drafts the window and formula layers look at.
WINDOW = 8
# Below this many entries the window means are too noisy to act on.
MIN_WINDOW = 4
LOG_LIMIT = 60

# What counts as flowing prose rather than an enumerated document. Used BOTH to
# select the pieces that define the contraction baseline and to decide whether a
# draft is measured against it. One constant, so the two cannot drift apart.
PROSE_MAX_LIST_DENSITY = 0.15

# A band from a handful of pieces is noise wearing a percentile's clothes.
# Below this, fall back to the pooled corpus rather than invent a distribution.
MIN_PIECES_FOR_BAND = 6

# Marker of the machine-checked section of hard-rules.md.
HARD_RULES_BLOCK = re.compile(
    r"<!--\s*machine-checked-rules:start\s*-->(.*?)<!--\s*machine-checked-rules:end\s*-->",
    re.DOTALL,
)
HARD_RULE_ROW = re.compile(r"^\s*-\s*`([^`]+)`\s*(.*)$")

# Persona-neutral anti-tic patterns — generic markers that hold regardless of
# whose voice this is. Anything specific to one writer (typography, in-house
# terminology, capitalisation) belongs in that writer's hard-rules.md instead.
ANTI_TIC_PATTERNS: List[Tuple[str, str]] = [
    (
        r"\bis not a typo\b",
        "anti-corpus: 'is not a typo' construct.",
    ),
    (
        r"^[#]{2,6}\s",
        "headings: ## section headings rarely appear in corpus; light bold is preferred.",
    ),
]


# --------------------------------------------------------------- corpus stats

def corpus_pieces() -> Dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in paths.corpus_files()}


def build_corpus_stats() -> Dict:
    """Measure the corpus, grouped by genre.

    Genres exist because register genuinely differs between, say, a public
    essay and a colleague-facing comment. Pooling them produces thresholds
    describing an average of two people, which no real piece matches — the
    band ends up wide enough to admit anything.
    """
    genres = vm.load_genres(CORPUS_DIR / "genres.txt")
    texts = corpus_pieces()
    pieces = {name: vm.piece_metrics(t) for name, t in texts.items()}

    groups: Dict[str, List[str]] = {"_all": list(texts)}
    for name in texts:
        g = vm.genre_of(name, genres)
        groups.setdefault(g or "_ungrouped", []).append(name)

    thresholds: Dict[str, Dict] = {}
    for gname, names in groups.items():
        long_enough = [n for n in names
                       if pieces[n]["word_count"] >= vm.MIN_WORDS_FOR_STATS]
        if not long_enough:
            long_enough = names
        if not long_enough:
            continue

        # Loop variables bound as defaults: these closures are consumed inside
        # this iteration, but leaving them late-bound is the kind of thing that
        # silently starts reading the last genre's pieces the moment anything
        # here becomes lazy.
        def col(key: str, src: List[str] = long_enough) -> List[float]:
            return [pieces[n][key] for n in src]

        # Rhythm is measured only on pieces substantial enough for it to be
        # stable. Falls back to the whole genre when nothing qualifies, so a
        # thin genre still gets a band rather than none.
        rhythm_src = [n for n in names
                      if pieces[n]["word_count"] >= vm.MIN_WORDS_FOR_RHYTHM] or long_enough

        def rcol(key: str, src: List[str] = rhythm_src) -> List[float]:
            return [pieces[n][key] for n in src]

        # Prose pieces set the contraction baseline. An enumerated document
        # legitimately has none, and letting it set the floor defeats the check.
        #
        # PROSE_MAX_LIST_DENSITY has to be the same figure the check uses. It
        # was not: the band came from pieces under 0.15 while the check ran on
        # anything under 0.50, so every piece in between was compared against a
        # distribution built by excluding pieces like it. That alone accounted
        # for half the corpus rejections in this genre.
        prose = [n for n in long_enough
                 if pieces[n]["list_density"] < PROSE_MAX_LIST_DENSITY] or long_enough

        thresholds[gname] = {
            # Rhythm: two-sided. These separate a writer's prose from generic
            # model prose most sharply. The percentiles are wide and the slack
            # generous on purpose — calibration against the corpus is what set
            # them, and a band that rejects the writing it came from is not
            # strict, it is broken.
            "sent_mean": vm.band(rcol("sent_mean"), 5, 95, 0.85, 1.20),
            "sent_sd": vm.band(rcol("sent_sd"), 5, 95, 0.80, 1.35),
            "long_pct": vm.band(rcol("long_pct"), 10, 95, 0.50, 1.50),
            "_rhythm_n": len(rhythm_src),
            # Typography: retained from the original gate.
            "heading_density": vm.band(col("heading_density"), 0, 100, 1.0, 1.0),
            "list_density": vm.band(col("list_density"), 0, 100, 1.0, 1.0),
            "paragraph_variance": vm.band(col("paragraph_variance"), 0, 100, 1.0, 1.0),
            "contraction_ratio": vm.band(
                [pieces[n]["contraction_ratio"] for n in prose], 5, 95, 0.40, 1.60),
            # Markers: window-level only. Recorded here as the reference the
            # window is compared against, never applied to a single draft.
            "dotdot_per_1k": vm.band(col("dotdot_per_1k"), 25, 75, 1.0, 1.0),
            "bang_per_1k": vm.band(col("bang_per_1k"), 25, 75, 1.0, 1.0),
            "contraction_per_1k": vm.band(col("contraction_per_1k"), 25, 75, 1.0, 1.0),
        }
        sim = vm.self_similarity([texts[n] for n in long_enough])
        if sim is not None:
            thresholds[gname]["self_similarity"] = sim

    return {"pieces": pieces, "genres": sorted(groups), "thresholds": thresholds}


def get_corpus_stats() -> Dict:
    files = paths.corpus_files()
    if not files:
        return {"pieces": {}, "thresholds": {}}
    newest = max(p.stat().st_mtime for p in files)
    genres_file = CORPUS_DIR / "genres.txt"
    if genres_file.exists():
        newest = max(newest, genres_file.stat().st_mtime)
    if STATS_CACHE.exists():
        try:
            cached = json.loads(STATS_CACHE.read_text(encoding="utf-8"))
            # A cache whose schema predates the current measurements would
            # serve thresholds computed a different way, silently, because the
            # corpus mtime has not moved. Version it or do not trust it.
            if (cached.get("_schema") == vm.SCHEMA
                    and cached.get("_corpus_mtime", 0) >= newest):
                return cached
        except Exception:
            pass
    stats = build_corpus_stats()
    stats["_corpus_mtime"] = newest
    stats["_schema"] = vm.SCHEMA
    STATS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    STATS_CACHE.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def thresholds_for(stats: Dict, genre: Optional[str]) -> Dict:
    """The genre's own bands, or the pooled ones when the genre is too thin.

    A genre with three usable pieces produces percentiles that describe those
    three pieces and nothing else. Pooled bands are blunter but honest.
    """
    th = stats.get("thresholds", {})
    if genre and genre in th:
        band = th[genre]
        if band.get("_rhythm_n", 0) >= MIN_PIECES_FOR_BAND:
            return band
        pooled = dict(th.get("_all", {}))
        pooled["_fellback_from"] = genre
        return pooled or band
    return th.get("_all", {})


# ------------------------------------------------------------- structural drift

def _normalize_label(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("—", "-").replace("–", "-").replace("−", "-")
    return re.sub(r"\s+", " ", s)


def section_labels(text: str) -> List[str]:
    labels: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if m:
            labels.append(_normalize_label(m.group(1)))
            continue
        m = re.match(r"^\*\*([^*]+)\*\*\s*$", line)
        if m:
            labels.append(_normalize_label(m.group(1)))
    return labels


def list_item_count(text: str) -> int:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return sum(1 for ln in text.splitlines()
               if re.match(r"^\s*[-*+]\s", ln) or re.match(r"^\s*\d+[.)]\s", ln))


def structural_fingerprint(text: str) -> Dict:
    return {
        "labels": section_labels(text),
        "paragraph_count": len(vm.paragraphs(text)),
        "list_item_count": list_item_count(text),
    }


def jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(len(sa | sb), 1)


def ordered_overlap(a: List[str], b: List[str]) -> float:
    if not a:
        return 0.0
    j = matched = 0
    for label in a:
        for k in range(j, len(b)):
            if b[k] == label:
                matched += 1
                j = k + 1
                break
    return matched / len(a)


def sequence_retention(input_text: str, draft_text: str) -> float:
    """Fraction of the input's word sequence still present, in order, in the draft.

    The decisive measurement for the rewrite case. Section labels can all be
    replaced and the list reshaped while two thirds of the original wording
    survives untouched underneath — a voice pass applied as paint over a
    skeleton that was never rebuilt. Labels alone do not catch that; this does.
    """
    import difflib
    a = vm.words(vm.strip_noise(input_text))
    b = vm.words(vm.strip_noise(draft_text))
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def structural_drift(input_path: Path, draft_path: Path) -> List[str]:
    violations: List[str] = []
    input_text = input_path.read_text(encoding="utf-8")
    draft_text = draft_path.read_text(encoding="utf-8")

    inp = structural_fingerprint(input_text)
    drf = structural_fingerprint(draft_text)

    retention = sequence_retention(input_text, draft_text)
    if retention >= 0.50:
        violations.append(
            "sequence retention %.0f%%: half or more of the input's wording survives in "
            "order. The draft was edited, not rebuilt. Re-do the abstraction step — write "
            "ideas.md from scratch, close the input, and draft from ideas + the exemplars."
            % (100 * retention))

    if inp["labels"] and drf["labels"]:
        jac = jaccard(inp["labels"], drf["labels"])
        ordv = ordered_overlap(inp["labels"], drf["labels"])
        if jac >= 0.6 and ordv >= 0.6:
            violations.append(
                "structural mimicry: %d of %d input section labels reused (jaccard=%.2f, "
                "ordered overlap=%.2f). The draft inherits the input's structure instead of "
                "rebuilding it."
                % (len(set(inp["labels"]) & set(drf["labels"])), len(inp["labels"]), jac, ordv))

    if inp["list_item_count"] >= 3 and drf["list_item_count"] >= 3:
        diff_ratio = abs(inp["list_item_count"] - drf["list_item_count"]) / max(
            inp["list_item_count"], drf["list_item_count"])
        if diff_ratio <= 0.15:
            violations.append(
                "list-shape mimicry: input has %d list items, draft has %d. Preserving the "
                "input's list shape suggests structure was copied rather than rebuilt."
                % (inp["list_item_count"], drf["list_item_count"]))

    return violations


# ------------------------------------------------------------------ hard rules

def load_hard_rule_patterns() -> List[Tuple[str, str]]:
    """Load the writer's machine-checked hard rules from hard-rules.md."""
    if not HARD_RULES.exists():
        return []
    block = HARD_RULES_BLOCK.search(HARD_RULES.read_text(encoding="utf-8"))
    if not block:
        return []
    rules: List[Tuple[str, str]] = []
    for line in block.group(1).splitlines():
        m = HARD_RULE_ROW.match(line)
        if not m:
            continue
        pattern = m.group(1)
        message = m.group(2).strip().lstrip("-—:.").strip() or "hard-rule pattern matched"
        try:
            re.compile(pattern)
        except re.error:
            continue
        rules.append((pattern, "hard-rule: " + message))
    return rules


# ----------------------------------------------------------------- draft log

def read_log() -> List[Dict]:
    if not DRAFT_LOG.exists():
        return []
    out = []
    for line in DRAFT_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def record_draft(draft_path: Path, text: str, genre: Optional[str],
                 metrics: Dict[str, float]) -> List[Dict]:
    """Record this draft, replacing any previous entry for the same file.

    Keyed on path rather than appended blindly, so iterating on one draft
    leaves one entry. Otherwise a draft revised four times would count four
    times in the window and drown out the three pieces before it.
    """
    entries = [e for e in read_log() if e.get("path") != str(draft_path)]
    counts = vm.words(vm.strip_noise(text))
    from collections import Counter
    top = Counter(counts).most_common(300)
    entries.append({
        "path": str(draft_path),
        "genre": genre or "_ungrouped",
        "hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "metrics": {k: round(v, 4) for k, v in metrics.items()},
        "counts": dict(top),
        "total": len(counts),
    })
    entries = entries[-LOG_LIMIT:]
    DRAFT_LOG.parent.mkdir(parents=True, exist_ok=True)
    DRAFT_LOG.write_text(
        "\n".join(json.dumps(e, separators=(",", ":")) for e in entries) + "\n",
        encoding="utf-8")
    return entries


def window_report(entries: List[Dict], genre: Optional[str], th: Dict) -> List[str]:
    """Compare the trailing window of drafts against the corpus.

    Everything checked here is sparse enough that a single piece proves
    nothing. A run of pieces proves plenty.
    """
    notes: List[str] = []
    key = genre or "_ungrouped"
    recent = [e for e in entries if e.get("genre") == key][-WINDOW:]
    if len(recent) < MIN_WINDOW:
        return notes

    import statistics as st

    for metric, label, direction in (
        ("dotdot_per_1k", "'..' trailer", "low"),
        ("bang_per_1k", "'!' marker", "low"),
        ("contraction_per_1k", "contractions", "both"),
    ):
        ref = th.get(metric)
        if not ref:
            continue
        vals = [e["metrics"].get(metric, 0.0) for e in recent]
        mean = st.mean(vals)
        if direction in ("low", "both") and ref["lo"] > 0 and mean < ref["lo"]:
            notes.append(
                "%s is fading: last %d drafts average %.1f per 1k words, the corpus "
                "runs %.1f-%.1f (median %.1f). No single draft is wrong; the run is."
                % (label, len(recent), mean, ref["lo"], ref["hi"], ref["p50"]))
        if direction == "both" and ref["hi"] > 0 and mean > ref["hi"] * 1.5:
            notes.append(
                "%s are over-used: last %d drafts average %.1f per 1k words against a "
                "corpus range of %.1f-%.1f. Over-correction reads as a different kind of "
                "wrong, not as more natural."
                % (label, len(recent), mean, ref["lo"], ref["hi"]))

    return notes


def formula_report(entries: List[Dict], genre: Optional[str], th: Dict) -> List[str]:
    """Flag when recent drafts have converged on one shape.

    Real writing spreads out. If the last several pieces sit closer to each
    other than the corpus pieces do, the generator has found a template — the
    failure a reader notices across posts and never inside one.
    """
    key = genre or "_ungrouped"
    recent = [e for e in entries if e.get("genre") == key][-WINDOW:]
    corpus_sim = th.get("self_similarity")
    if len(recent) < MIN_WINDOW or not corpus_sim:
        return []

    vocab_pool: Dict[str, int] = {}
    for e in recent:
        for w, c in e.get("counts", {}).items():
            vocab_pool[w] = vocab_pool.get(w, 0) + c
    vocab = [w for w, _ in sorted(vocab_pool.items(), key=lambda kv: -kv[1])[:120]]
    if not vocab:
        return []

    profs = []
    for e in recent:
        total = max(e.get("total", 1), 1)
        counts = e.get("counts", {})
        profs.append([100.0 * counts.get(w, 0) / total for w in vocab])

    means, sds = vm.zparams(profs)
    pairs = [vm.delta(profs[i], profs[j], means, sds)
             for i in range(len(profs)) for j in range(i + 1, len(profs))]
    if not pairs:
        return []
    import statistics as st
    sim = st.mean(pairs)

    if sim < corpus_sim * 0.85:
        return [
            "formula: the last %d drafts are %.0f%% more alike than the corpus pieces are "
            "(pairwise delta %.3f against the corpus's %.3f). They have converged on one "
            "shape. Vary what the corpus varies: opening move, sentence lengths, where the "
            "claim lands." % (len(recent), 100 * (1 - sim / corpus_sim), sim, corpus_sim)
        ]
    return []


# ---------------------------------------------------------------------- checks

def _drift(draft_path: Path, text: str, genre: Optional[str],
           metrics: Dict[str, float], th: Dict) -> List[str]:
    entries = record_draft(draft_path, text, genre, metrics)
    return window_report(entries, genre, th) + formula_report(entries, genre, th)


def check(draft_path: Path, input_path: Optional[Path] = None,
          genre: Optional[str] = None,
          record: bool = True) -> Tuple[List[str], List[str]]:
    """Return (per-draft violations, window/formula drift notes).

    `record=False` runs the per-draft checks without touching the log, which is
    what calibration needs: the corpus must be measurable against its own bands
    without those measurements becoming history.
    """
    text = draft_path.read_text(encoding="utf-8")
    violations: List[str] = []

    if input_path is not None:
        violations.extend(structural_drift(input_path, draft_path))

    for pattern, msg in ANTI_TIC_PATTERNS + load_hard_rule_patterns():
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            violations.append(msg if msg.startswith("hard-rule:") else "anti-tic: " + msg)

    metrics = vm.piece_metrics(text)
    if metrics["word_count"] < vm.MIN_WORDS_FOR_STATS:
        return violations, []

    stats = get_corpus_stats()
    th = thresholds_for(stats, genre)
    if not th:
        return violations, []

    # --- rhythm, two-sided -------------------------------------------------
    # The measurements that separate a writer's prose from generic model prose
    # most sharply. Both directions matter: prose that is uniformly clipped and
    # prose that is uniformly sprawling are both unlike a writer who varies.
    #
    # Skipped entirely below MIN_WORDS_FOR_RHYTHM. In a short note two
    # sentences move the average by ten words, so the check would report drift
    # that is really sample size.
    if metrics["word_count"] < vm.MIN_WORDS_FOR_RHYTHM:
        return violations, ([] if not record else _drift(draft_path, text, genre, metrics, th))

    # Clipped rhythm, as a COMPOSITE rather than three separate floors.
    #
    # Measured on this corpus, no single rhythm metric separates cleanly: a
    # floor tight enough to catch generated prose also rejects a quarter of the
    # writer's own pieces, because a real writer's range is wide and genuinely
    # overlaps the model's. Requiring all three to sit in the bottom quartile
    # at once asks for convergent evidence instead, and that does separate —
    # 79% of generated articles caught against 83% of the corpus passing, where
    # the best single floor managed 32%.
    #
    # What it describes is prose that is short AND uniform AND never once
    # stretches out. Any one of those is a style. All three together is a
    # generator.
    sm, sd, lp = th.get("sent_mean"), th.get("sent_sd"), th.get("long_pct")
    enough_sentences = len(vm.sentences(text)) >= vm.MIN_SENTENCES_FOR_LONG_CHECK
    if sm and sd and lp and enough_sentences:
        # All three in the bottom quartile, and at least one well below that.
        # The second condition is not decoration: these three metrics are
        # correlated (short sentences produce low spread and no long ones), so
        # "all three below p25" lands on far more than a quarter of any real
        # corpus. Requiring one of them to be genuinely extreme restores the
        # separation without tightening the others.
        low = [
            metrics["sent_mean"] < sm["p25"],
            metrics["sent_sd"] < sd["p25"],
            metrics["long_pct"] < lp["p25"],
        ]
        deep = (metrics["sent_mean"] < sm["p15"]
                or metrics["sent_sd"] < sd["p15"]
                or metrics["long_pct"] < lp["p15"])
        if all(low) and deep:
            violations.append(
                "clipped rhythm: sentences average %.1f words (corpus median %.1f), stdev "
                "%.1f (corpus %.1f), and %.0f%% reach %d+ words (corpus %.0f%%). Short, "
                "uniform, and never stretching out — all three at once is the clearest "
                "signal of generated prose. Let some sentences run long and stack clauses."
                % (metrics["sent_mean"], sm["p50"], metrics["sent_sd"], sd["p50"],
                   metrics["long_pct"], vm.LONG_SENTENCE_WORDS, lp["p50"]))

    # The opposite failure, kept separate because the fix is different.
    if sm and metrics["sent_mean"] > sm["hi"]:
        violations.append(
            "sentences too long: %.1f words on average; the corpus runs %.1f-%.1f."
            % (metrics["sent_mean"], sm["lo"], sm["hi"]))

    # --- typography --------------------------------------------------------
    cr = th.get("contraction_ratio")
    # A floor is only meaningful where the writer reliably uses contractions in
    # this register. Where a quarter of their own pieces sit near zero — which
    # is the case for technical instruction-writing — sparse contractions are
    # normal and "too few" is evidence of nothing. Counting exact zeros was not
    # enough: the pieces clustered just above zero, not at it.
    contraction_floor_applies = bool(cr) and cr.get("p25", 0.0) > 0.05
    if cr and metrics["list_density"] < PROSE_MAX_LIST_DENSITY:
        # Deliberately near-zero rather than banded. This check was only ever
        # meant to catch one catastrophe — prose with every contraction
        # expanded, which reads as a corporate memo — and calibration showed a
        # banded floor firing on pieces that simply ran a little formal.
        # Twelve of twenty corpus rejections came from here, and the measured
        # failure in generated output was the opposite direction anyway.
        floor = min(max(cr["lo"], 0.02), 0.05)
        if contraction_floor_applies and metrics["contraction_ratio"] < floor:
            violations.append(
                "contractions too rare for prose: %.3f per sentence; the corpus prose runs "
                "%.3f-%.3f. Signals corporate-memo register rather than the writer's."
                % (metrics["contraction_ratio"], cr["lo"], cr["hi"]))
        # The ceiling stays on even where the floor is switched off, and that
        # asymmetry is the point. A gate with only a floor is a one-way
        # ratchet: every correction pushes the same direction, nothing pushes
        # back, and the metric sails past the corpus unflagged. Measured on
        # this corpus, that is exactly what happened — contractions ended up at
        # roughly twice the writer's own rate with no check able to see it.
        elif cr["hi"] > 0 and metrics["contraction_ratio"] > cr["hi"]:
            violations.append(
                "contractions over-used: %.3f per sentence; the corpus prose runs "
                "%.3f-%.3f. Over-correcting past the corpus is its own kind of off-voice."
                % (metrics["contraction_ratio"], cr["lo"], cr["hi"]))

    hd = th.get("heading_density")
    if hd and metrics["heading_density"] > hd["max"] * 1.5 + 0.02:
        violations.append(
            "heading density too high: %.3f; corpus max %.3f."
            % (metrics["heading_density"], hd["max"]))

    ld = th.get("list_density")
    if ld and metrics["list_density"] > ld["max"] * 1.3 + 0.05:
        violations.append(
            "list density too high: %.3f; corpus max %.3f."
            % (metrics["list_density"], ld["max"]))

    pv = th.get("paragraph_variance")
    if pv and metrics["paragraph_count"] >= 4 and metrics["paragraph_variance"] < pv["min"] * 0.5:
        violations.append(
            "paragraphs too uniform: stdev=%.1f words; corpus min %.1f."
            % (metrics["paragraph_variance"], pv["min"]))

    # --- window + formula --------------------------------------------------
    if not record:
        return violations, []
    return violations, _drift(draft_path, text, genre, metrics, th)


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("draft")
    ap.add_argument("--input", dest="input_path", default=None,
                    help="The source being rewritten, for the structural-drift check.")
    ap.add_argument("--genre", default=None,
                    help="Genre from corpus/genres.txt; scopes every threshold.")
    args = ap.parse_args()

    draft_path = Path(args.draft)
    if not draft_path.exists():
        print("Draft not found: %s" % draft_path, file=sys.stderr)
        return 2
    input_path = Path(args.input_path) if args.input_path else None
    if input_path is not None and not input_path.exists():
        print("Input not found: %s" % input_path, file=sys.stderr)
        return 2

    violations, drift = check(draft_path, input_path, args.genre)

    if violations:
        print("VIOLATIONS (%d):" % len(violations))
        for v in violations:
            print("  - " + v)
    else:
        print("NO_VIOLATIONS")

    if drift:
        print()
        print("DRIFT (%d) — about the recent run of drafts, not this one alone:" % len(drift))
        for d in drift:
            print("  - " + d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
