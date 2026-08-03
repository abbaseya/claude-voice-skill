#!/usr/bin/env python3
"""
Check the gate against the corpus that defined it.

A threshold derived from a body of writing must accept that writing. If the
corpus fails its own bands, the bands are wrong — and a gate that fires on
correct work is worse than no gate, because the first few false alarms teach
everyone to skip reading it.

Run this after changing a threshold, adding corpus pieces, or editing
genres.txt. Anything below the pass rate printed at the end wants looking at
before it ships.

Usage:
    python3 calibrate.py
    python3 calibrate.py --verbose
"""
import argparse
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import safety_net as sn  # noqa: E402
import voice_metrics as vm  # noqa: E402

# Below this share of its own corpus passing, a band is miscalibrated rather
# than strict. Some genuine outliers are expected — a corpus with none has
# usually been tidied.
TARGET_PASS_RATE = 0.80

# Below this many measurable pieces, a genre's pass rate carries no
# information — it can only land on a handful of values, none of them
# meaningful.
MIN_PIECES_TO_JUDGE = 5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true",
                    help="Name every corpus piece that fails, and why.")
    args = ap.parse_args()

    files = paths.corpus_files()
    if not files:
        print("NO_CORPUS")
        return 0

    genres = vm.load_genres(paths.corpus_dir() / "genres.txt")
    by_genre = defaultdict(list)
    for f in files:
        by_genre[vm.genre_of(f.name, genres) or "_ungrouped"].append(f)

    reasons: Counter = Counter()
    overall_pass = overall_total = 0
    worst = 1.0

    print("CALIBRATION — does the corpus pass the bands built from it?")
    print()

    with tempfile.TemporaryDirectory() as td:
        for genre in sorted(by_genre):
            pieces = by_genre[genre]
            testable = [p for p in pieces
                        if vm.piece_metrics(p.read_text(encoding="utf-8"))["word_count"]
                        >= vm.MIN_WORDS_FOR_STATS]
            if not testable:
                print("  %-12s no piece long enough to measure" % genre)
                continue

            passed, failures = 0, []
            for piece in testable:
                # Copied to a temp path so the corpus itself is never the thing
                # being logged or rewritten.
                tmp = Path(td) / piece.name
                tmp.write_text(piece.read_text(encoding="utf-8"), encoding="utf-8")
                violations, _ = sn.check(tmp, None, genre, record=False)
                # Hard rules and anti-tics are the writer's own deliberate
                # constraints; a corpus written before they existed will break
                # them and that says nothing about the statistical bands.
                stat_violations = [v for v in violations
                                   if not v.startswith(("hard-rule:", "anti-tic:"))]
                if stat_violations:
                    failures.append((piece.name, stat_violations))
                    for v in stat_violations:
                        reasons[v.split(":")[0]] += 1
                else:
                    passed += 1

            rate = passed / len(testable)
            overall_pass += passed
            overall_total += len(testable)
            # A genre with a couple of measurable pieces cannot report a
            # meaningful rate — it is 0% or 100% and neither says anything
            # about the band. Those genres fall back to the pooled bands at
            # check time anyway, so judging them here would just add noise.
            if len(testable) < MIN_PIECES_TO_JUDGE:
                print("  %-12s %2d/%2d  (too few pieces to judge; uses pooled bands)"
                      % (genre, passed, len(testable)))
                continue
            worst = min(worst, rate)
            flag = "ok" if rate >= TARGET_PASS_RATE else "MISCALIBRATED"
            print("  %-12s %2d/%2d pass (%3.0f%%)  %s"
                  % (genre, passed, len(testable), 100 * rate, flag))
            if args.verbose:
                for name, vs in failures:
                    print("      %s" % name)
                    for v in vs:
                        print("        - %s" % v[:150])

    print()
    if overall_total:
        print("  overall %d/%d (%.0f%%)"
              % (overall_pass, overall_total, 100 * overall_pass / overall_total))
    if reasons:
        print("  failures by check: %s"
              % ", ".join("%s=%d" % kv for kv in reasons.most_common()))
    print()
    if worst < TARGET_PASS_RATE:
        print("  At least one genre rejects more than %d%% of its own corpus."
              % int(100 * (1 - TARGET_PASS_RATE)))
        print("  Widen the band, or split the genre — do not ship it as is.")
    else:
        print("  Every genre accepts its own corpus. Bands are usable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
