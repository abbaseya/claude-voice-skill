#!/usr/bin/env python
"""Nobody else's voice may reach a user's drafts.

This plugin was generalised out of one person's working setup, and the failure
mode that follows from that is not a leaked name — `check-leaks.py` already
catches those. It is a leaked *preference*: a typography rule, a punctuation
habit, or a starter annotation that quietly shapes somebody else's writer-model.

A `^#{2,6}\\s` heading rule once lived in the anti-tic list. It flagged every
draft written by anyone who structures prose with section headings, their own
corpus included, and it did so silently — the message read "light bold is
preferred", which is one person's preference stated as a universal.

The load-bearing test here builds a corpus in a voice deliberately unlike the
original author's — three-word sentences, headings everywhere, no signature
punctuation at all — and asserts the gate leaves it alone. Every threshold is
supposed to come from the user's own corpus. This proves it does.
"""
import importlib
import os
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

# Short, declarative, semicolon-using, heading-structured. No "..", no "!",
# no long sentences. Roughly the opposite of the corpus this was built against.
SHORT_LINES = [
    "The build is green.", "We shipped it.", "Latency dropped.",
    "Tests pass now.", "The cache was cold.", "It works.",
    "No regressions.", "The fix was small.", "Config was wrong.",
    "Coverage improved; barely.", "Rollout is done.", "Metrics look flat.",
    "The queue drained.", "Nothing broke.", "The patch is merged.",
]
HEADINGS = ["Overview", "Method", "Results", "Notes", "Summary", "Context"]


def write_other_voice_corpus(corpus_dir: Path, pieces: int = 8) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    for i in range(pieces):
        rng = random.Random(i)
        out = []
        for h in range(4):
            out += ["## " + HEADINGS[(i + h) % len(HEADINGS)], ""]
            for _ in range(9):
                n = rng.choice([1, 1, 2])
                out.append(" ".join(rng.choice(SHORT_LINES) for _ in range(n)))
            out.append("")
        (corpus_dir / ("other-%d.md" % i)).write_text("\n".join(out), encoding="utf-8")


class ForeignVoiceIsLeftAlone(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="voice-leak-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.environ["MY_VOICE_HOME"] = str(self.tmp)
        write_other_voice_corpus(self.tmp / "corpus")
        import paths
        importlib.reload(paths)
        import voice_metrics
        importlib.reload(voice_metrics)
        import safety_net
        importlib.reload(safety_net)
        self.sn = safety_net

    def statistical_violations(self, path: Path):
        """Violations excluding the user's own hard rules (there are none here)."""
        violations, _ = self.sn.check(path, None, None, record=False)
        return [v for v in violations if not v.startswith("hard-rule:")]

    def test_a_draft_in_their_own_voice_passes(self):
        """The headline guarantee. Their writing must not be flagged for not
        being somebody else's."""
        draft = self.tmp / "draft.md"
        draft.write_text((self.tmp / "corpus" / "other-1.md").read_text(encoding="utf-8"),
                         encoding="utf-8")
        self.assertEqual(self.statistical_violations(draft), [])

    def test_headings_are_not_flagged_when_the_corpus_uses_headings(self):
        """The specific regression. A hardcoded heading rule fired here."""
        draft = self.tmp / "draft.md"
        draft.write_text("## Overview\n\nThe build is green. It works.\n\n"
                         "## Results\n\nLatency dropped. Nothing broke.\n" * 6,
                         encoding="utf-8")
        found = [v for v in self.statistical_violations(draft) if "heading" in v.lower()]
        self.assertEqual(found, [], "heading rule fired on a heading-using corpus")

    def test_no_pressure_to_adopt_signature_punctuation(self):
        """A marker absent from their corpus must never be demanded of them.
        The window layer keys on the corpus band, so a band of zero has to mean
        'not applicable' rather than 'floor of zero'."""
        draft = self.tmp / "draft.md"
        body = "\n\n".join(["The build is green. It works. Tests pass now."] * 30)
        draft.write_text(body, encoding="utf-8")
        for marker in ("'..'", "'!'"):
            found = [v for v in self.statistical_violations(draft) if marker in v]
            self.assertEqual(found, [], "demanded %s from a corpus without it" % marker)

    def test_their_corpus_passes_bands_built_from_it(self):
        """Calibration must hold for any corpus, not just the one the
        thresholds were originally tuned against."""
        import calibrate  # noqa: F401  (imported for side-effect-free reuse)
        for piece in sorted((self.tmp / "corpus").glob("*.md")):
            tmp = self.tmp / ("check-" + piece.name)
            tmp.write_text(piece.read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(self.statistical_violations(tmp), [],
                             "%s fails bands derived from its own corpus" % piece.name)


TEMPLATES = REPO / "templates"
# Not every packaging of this skill ships starter templates — the Convert plugin
# build has none, because its users are handed a corpus location rather than a
# setup wizard. Where there is nothing shipped there is nothing to leak, so the
# template assertions skip rather than fail.
HAS_TEMPLATES = TEMPLATES.is_dir()


class ShippedFilesCarryNobodysVoice(unittest.TestCase):

    def test_anti_tic_patterns_hold_no_typography_preference(self):
        """Typography is a voice preference and belongs in a user's own
        hard-rules.md, which only applies to them."""
        import safety_net
        for pattern, _ in safety_net.ANTI_TIC_PATTERNS:
            self.assertNotIn("#", pattern, "heading/typography rule in anti-tics")
            for banned in ("—", "–", ";", r"\.\.", "!"):
                self.assertNotIn(banned, pattern,
                                 "punctuation preference %r in anti-tics" % banned)

    def test_generic_typos_are_domain_free(self):
        """A correction that only makes sense inside one person's vocabulary is
        noise in everyone else's. Personal entries load via --typos."""
        import harvest_sessions as hs
        for right in hs.GENERIC_TYPOS.values():
            self.assertNotIn(right.lower(),
                             {"bucketing", "mermaid", "shopify", "convert", "asana",
                              "kubernetes", "postgres"},
                             "domain-specific correction %r ships by default" % right)

    def test_generic_typos_never_rewrite_a_real_word(self):
        """"it's"->"its" and "apps"->"apis" were both automatic suggestions."""
        import harvest_sessions as hs
        for word in ("it's", "its", "apps", "async", "demo", "info", "auth",
                     "wont", "lets", "ill", "id", "behaviour", "organised"):
            self.assertNotIn(word, hs.GENERIC_TYPOS,
                             "%r is a real word and must not be corrected" % word)

    @unittest.skipUnless(HAS_TEMPLATES, "this packaging ships no templates")
    def test_templates_do_not_ship_a_usable_voice(self):
        """The annotations template is hashed into the corpus baseline and feeds
        the writer-model, so a filled-in example there is not illustrative — it
        is a stranger's voice applied to whoever skipped editing it."""
        import re as _re
        text = (TEMPLATES / "annotations.md").read_text(encoding="utf-8")
        body = text.split("-->", 1)[-1]
        self.assertIn("<", body,
                      "annotations template must use <placeholders>, not real observations")
        # Inside <angle brackets> a term is one of several options on offer.
        # Outside them it is an assertion about how the user writes, which the
        # template cannot know and must not supply.
        asserted = _re.sub(r"<[^>]*>", " ", body).lower()
        for concrete in ("em-dash", "em dash", "semi-colon", "semicolon",
                         "bullet list", "inline link", "story-shaped",
                         "shortest version", "single bold"):
            self.assertNotIn(concrete, asserted,
                             "template asserts a concrete preference: %r" % concrete)

    @unittest.skipUnless(HAS_TEMPLATES, "this packaging ships no templates")
    def test_templates_address_the_reader_not_the_author(self):
        """"write my own annotations" is a leftover from a personal file."""
        for name in ("annotations.md", "anti-corpus.md", "hard-rules.md"):
            text = (TEMPLATES / name).read_text(encoding="utf-8")
            head = text.split("-->", 1)[0]
            for slip in ("my own", "write my own", "add my own", "replace with my"):
                self.assertNotIn(slip, head.lower(),
                                 "%s instructs in the author's first person: %r"
                                 % (name, slip))


if __name__ == "__main__":
    unittest.main()
