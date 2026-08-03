#!/usr/bin/env python3
"""
Choose which corpus pieces to put in front of the model before it drafts.

Why this exists: a generated summary of how someone writes is a description,
and a description is something a model obeys rather than imitates. Obeying
"varies sentence length deliberately" produces sentences of uniform length,
because the instruction carries no rhythm to copy — only an intention to
satisfy. Actual passages carry the rhythm. So the draft step reads real
pieces, and this script decides which ones.

Selection is by SHAPE, never by subject. A piece about Arabic font rendering
is the right exemplar for a piece about bucketing arithmetic if both are the
same length, register and density. Matching on topic instead pulls the draft
toward reusing the exemplar's content, which is the failure this is meant to
avoid.

Usage:
    python3 pick_exemplars.py --words 1000
    python3 pick_exemplars.py --words 1000 --genre article --n 5
"""
import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import voice_metrics as vm  # noqa: E402


def shape_distance(piece: dict, target_words: int, target_list_density: float) -> float:
    """Lower is a better exemplar.

    Length is compared on a log scale: 500 words against a 1000-word target is
    the same mismatch as 2000 against 1000, which is how a reader experiences
    it. Density separates flowing prose from enumerated writing, which are
    different modes for most writers and should not stand in for each other.
    """
    ratio = max(piece["word_count"], 1) / max(target_words, 1)
    length_gap = abs(math.log2(ratio))
    density_gap = abs(piece["list_density"] - target_list_density) * 3.0
    return length_gap + density_gap


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--words", type=int, required=True,
                    help="Roughly how long the piece being written will be.")
    ap.add_argument("--genre", default=None,
                    help="Preferred genre from corpus/genres.txt. A same-genre piece "
                         "wins over an equally-shaped one elsewhere, but a much better "
                         "shape match from another register can still surface.")
    ap.add_argument("--strict", action="store_true",
                    help="Exclude other genres outright instead of penalising them.")
    ap.add_argument("--n", type=int, default=4, help="How many exemplars (default 4).")
    ap.add_argument("--list-density", type=float, default=0.0,
                    help="Expected list density of the target, 0.0 for flowing prose.")
    args = ap.parse_args()

    corpus = paths.corpus_files()
    if not corpus:
        print("NO_CORPUS")
        return 0

    genres = vm.load_genres(paths.corpus_dir() / "genres.txt")
    rows = []
    for path in corpus:
        text = path.read_text(encoding="utf-8")
        m = vm.piece_metrics(text)
        g = vm.genre_of(path.name, genres)
        if args.genre and args.strict and g != args.genre:
            continue
        rows.append({
            "path": path, "name": path.name, "genre": g,
            "word_count": m["word_count"], "list_density": m["list_density"],
            "sent_mean": m["sent_mean"], "sent_sd": m["sent_sd"],
        })

    if not rows:
        print("NO_MATCH: no corpus piece carries genre %r." % args.genre)
        print("  Either add the genre to %s, or re-run without --genre."
              % (paths.corpus_dir() / "genres.txt"))
        return 0

    # A genre mismatch is a penalty, not a disqualification. Hard-filtering
    # looks tidier and produces worse exemplars: where the target genre has
    # nothing near the requested length, it returns the four closest short
    # pieces and the model has nothing to imitate past their last paragraph.
    # A well-matched piece from an adjacent register beats a badly-matched one
    # from the right register.
    GENRE_PENALTY = 0.60
    for r in rows:
        r["distance"] = shape_distance(r, args.words, args.list_density)
        if args.genre and r["genre"] != args.genre:
            r["distance"] += GENRE_PENALTY
            r["off_genre"] = True
    rows.sort(key=lambda r: r["distance"])
    chosen = rows[:max(args.n, 1)]

    # Depth is reported for the genre actually asked for, not the whole corpus.
    # The point of the number is to say how much evidence exists in the
    # register being written, and counting everything hides exactly the gap it
    # is there to expose.
    in_genre = [r for r in rows if not args.genre or r["genre"] == args.genre]
    pool = in_genre or rows
    pool_words = sum(r["word_count"] for r in pool)
    longest = max(pool, key=lambda r: r["word_count"])

    print("EXEMPLARS (read every one of these in full before drafting)")
    for r in chosen:
        print("  %s" % r["path"])
        print("      %d words, sentences avg %.1f (sd %.1f), shape distance %.2f%s"
              % (r["word_count"], r["sent_mean"], r["sent_sd"], r["distance"],
                 ", genre %s" % r["genre"] if r["genre"] else ""))

    print()
    print("EVIDENCE DEPTH")
    print("  %d pieces, %d words%s."
          % (len(pool), pool_words, " in genre %r" % args.genre if args.genre else ""))
    off = [r for r in chosen if r.get("off_genre")]
    if off:
        print("  %d of the chosen exemplars come from another register (%s) because"
              % (len(off), ", ".join(sorted({r["genre"] or "unlabelled" for r in off}))))
        print("  they match the target shape better than anything in %r." % args.genre)

    # The honest warning. Asking for 1000 words of someone's voice when the
    # longest thing they have written in that register is 700 means the model
    # has to invent the back half of the shape, and what it invents is its own
    # default. Saying so at draft time is worth more than discovering it in the
    # finished piece.
    if longest["word_count"] < args.words * 0.8:
        print()
        print("  WARNING: target is %d words; the longest matching corpus piece is %d"
              % (args.words, longest["word_count"]))
        print("  (%s). Past roughly that length the draft has no example to" % longest["name"])
        print("  imitate and will drift toward the model's own defaults. Either shorten")
        print("  the target, or add longer pieces in this register to the corpus.")

    thin = [r for r in chosen if r["word_count"] < vm.MIN_WORDS_FOR_STATS]
    if thin:
        print()
        print("  NOTE: %d of the chosen exemplars are under %d words and carry little"
              % (len(thin), vm.MIN_WORDS_FOR_STATS))
        print("  rhythm to imitate: %s" % ", ".join(r["name"] for r in thin))

    return 0


if __name__ == "__main__":
    sys.exit(main())
