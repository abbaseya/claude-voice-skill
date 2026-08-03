#!/usr/bin/env python
"""The measurements the gate is built on.

Every threshold in the safety net is a percentile of one of these numbers. A
measurement that is quietly wrong does not announce itself — it moves a band,
and the gate then either fires on correct writing or stops firing at all. Both
end the same way, with everybody ignoring it.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import voice_metrics as vm  # noqa: E402


class SentenceSplitting(unittest.TestCase):

    def test_two_dot_trailer_terminates_a_sentence(self):
        """Some writers end thoughts with '..'. Not treating it as terminal
        glues every trailing thought to the sentence after it and inflates
        mean sentence length across the whole corpus."""
        text = "The thing is slow .. that matters more than it sounds."
        self.assertEqual(len(vm.sentences(text)), 2)

    def test_label_lines_are_not_sentences(self):
        """'Day 1. Ground Zero' is a heading. Counted as two two-word
        sentences it halves the reported average for the piece, and a band
        built from that rejects the writer's own prose for running long."""
        text = ("Day 1. Ground Zero\n\n"
                "We had one line to work from and no requirements at all, "
                "so the first job was writing them ourselves.\n")
        lengths = vm.sentence_lengths(text)
        self.assertEqual(len(lengths), 1)
        self.assertGreater(lengths[0], 15)

    def test_short_sentence_ending_in_a_full_stop_survives(self):
        """The label rule keys on missing terminal punctuation, so a genuine
        short sentence must not be swept up with the headings."""
        self.assertIn("It's that simple", " ".join(vm.sentences("It's that simple.")))

    def test_urls_do_not_fragment_into_sentences(self):
        plain = "Read the write-up before deciding anything about it."
        linked = plain + " https://example.com/a.b.c/d.e"
        self.assertEqual(len(vm.sentences(plain)), len(vm.sentences(linked)))


class Markers(unittest.TestCase):

    def test_two_dots_counted_but_ellipsis_ignored(self):
        m = vm.piece_metrics("one .. two ... three .. four")
        self.assertGreater(m["dotdot_per_1k"], 0)
        self.assertEqual(len(vm.DOTDOT.findall("a ... b")), 0)

    def test_contractions_counted_through_curly_apostrophes(self):
        self.assertEqual(vm.contraction_count("don’t it’s"),
                         vm.contraction_count("don't it's"))


class Bands(unittest.TestCase):

    def test_percentile_endpoints(self):
        vals = [1, 2, 3, 4, 5]
        self.assertEqual(vm.percentile(vals, 0), 1)
        self.assertEqual(vm.percentile(vals, 100), 5)
        self.assertEqual(vm.percentile(vals, 50), 3)

    def test_band_reports_the_percentiles_the_gate_reads(self):
        b = vm.band([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 10, 90, 1.0, 1.0)
        for key in ("lo", "hi", "p15", "p25", "p50", "min", "max", "n", "zero_share"):
            self.assertIn(key, b)

    def test_zero_share_is_reported(self):
        b = vm.band([0, 0, 1, 1], 10, 90, 1.0, 1.0)
        self.assertAlmostEqual(b["zero_share"], 0.5)


class SelfSimilarity(unittest.TestCase):

    def test_identical_texts_are_maximally_similar(self):
        same = ["the same words over and over again in every piece"] * 4
        varied = [
            "the same words over and over again in every piece",
            "a completely different sentence about boats and rivers",
            "yet another way of saying something unrelated entirely",
            "numbers, timing and arithmetic dominate this fourth one",
        ]
        self.assertLess(vm.self_similarity(same), vm.self_similarity(varied))

    def test_too_few_texts_returns_none(self):
        self.assertIsNone(vm.self_similarity(["one", "two"]))


class Genres(unittest.TestCase):

    def test_globs_map_to_genres(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "genres.txt"
            f.write_text("# comment\narticle: wp-*.md, 07-*.md\nnotes: session-*.md\n")
            g = vm.load_genres(f)
            self.assertEqual(vm.genre_of("wp-2010-x.md", g), "article")
            self.assertEqual(vm.genre_of("session-004.md", g), "notes")
            self.assertIsNone(vm.genre_of("unlisted.md", g))

    def test_absent_file_means_one_pool(self):
        self.assertEqual(vm.load_genres(Path("/nonexistent/genres.txt")), {})


if __name__ == "__main__":
    unittest.main()
