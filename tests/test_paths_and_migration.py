#!/usr/bin/env python
"""Your writing must live outside the plugin, and must survive becoming one.

Two guarantees are tested here and they are the reason this file exists:

  1. Nothing a user owns is stored inside the plugin directory, because a plugin
     update replaces that directory wholesale.
  2. Anyone who installed this before it was a plugin — corpus sitting in
     ~/.claude/skills/my-voice/ — is migrated automatically, by COPY, without
     their originals being touched.

A corpus is often the only surviving copy of someone's writing. Getting this
wrong is not a bug you apologise for.
"""
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))


class VoiceCase(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="my-voice-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "data"
        os.environ["MY_VOICE_HOME"] = str(self.home)
        import paths
        importlib.reload(paths)
        self.paths = paths
        # Point the legacy location at a temp dir too, so a real pre-plugin
        # install on the developer's machine can never be read or copied. Set via
        # the environment rather than by patching the module, so subprocesses see
        # it as well — otherwise the migration path is only ever tested in-process,
        # which is exactly where it is least likely to break.
        self.legacy = self.tmp / "legacy-skill"
        os.environ["MY_VOICE_LEGACY_HOME"] = str(self.legacy)
        importlib.reload(paths)

    def make_legacy(self, pieces=3, with_extras=True):
        (self.legacy / "corpus").mkdir(parents=True)
        for i in range(pieces):
            (self.legacy / "corpus" / ("%02d-piece.md" % i)).write_text(
                "Sample %d. This is my actual writing.\n" % i, encoding="utf-8")
        (self.legacy / "corpus" / "README.md").write_text("instructions\n", encoding="utf-8")
        if with_extras:
            (self.legacy / "annotations.md").write_text("1. I open short.\n", encoding="utf-8")
            (self.legacy / "anti-corpus.md").write_text("bad example\n", encoding="utf-8")
            (self.legacy / "hard-rules.md").write_text("never do X\n", encoding="utf-8")
            (self.legacy / "runtime").mkdir()
            (self.legacy / "runtime" / "voice_model.md").write_text(
                "> Generated from corpus hash: abc\n", encoding="utf-8")

    def run_script(self, name, *args):
        env = dict(os.environ)
        env["MY_VOICE_HOME"] = str(self.home)
        p = subprocess.run([sys.executable, str(SCRIPTS / name), *args],
                           capture_output=True, text=True, env=env)
        return p.returncode, p.stdout + p.stderr


class DataLocation(VoiceCase):

    def test_nothing_the_user_owns_is_inside_the_plugin(self):
        """The guarantee: a plugin update must not be able to delete your work."""
        p = self.paths
        for path in (p.data_home(), p.corpus_dir(), p.annotations(), p.anti_corpus(),
                     p.hard_rules(), p.runtime_dir(), p.voice_model(),
                     p.corpus_notes(), p.sessions_dir(), p.stats_cache()):
            self.assertFalse(str(path).startswith(str(REPO)),
                             "%s is inside the plugin directory" % path)

    def test_stats_cache_is_not_in_the_plugin_scripts_dir(self):
        """It used to live beside the scripts, which an update would wipe."""
        self.assertNotIn("scripts", self.paths.stats_cache().parts)

    def test_env_override_is_respected(self):
        self.assertEqual(self.paths.data_home(), self.home)

    def test_readme_is_not_counted_as_a_corpus_piece(self):
        self.paths.corpus_dir().mkdir(parents=True)
        (self.paths.corpus_dir() / "README.md").write_text("x", encoding="utf-8")
        self.assertEqual(self.paths.corpus_files(), [])
        self.assertFalse(self.paths.is_configured())


class LegacyMigration(VoiceCase):

    def test_pre_plugin_install_is_detected(self):
        self.make_legacy()
        self.assertTrue(self.paths.legacy_corpus_present())

    def test_a_legacy_dir_with_only_a_readme_is_not_a_corpus(self):
        (self.legacy / "corpus").mkdir(parents=True)
        (self.legacy / "corpus" / "README.md").write_text("x", encoding="utf-8")
        self.assertFalse(self.paths.legacy_corpus_present())

    def test_migration_copies_everything_the_user_owns(self):
        self.make_legacy()
        moved = self.paths.migrate_from_legacy()
        self.assertEqual(sorted(moved),
                         ["annotations.md", "anti-corpus.md", "corpus",
                          "hard-rules.md", "runtime"])
        self.assertEqual(len(self.paths.corpus_files()), 3)
        self.assertTrue(self.paths.annotations().is_file())
        self.assertTrue(self.paths.voice_model().is_file())

    def test_originals_are_never_deleted(self):
        """COPY, not move. There may be no other copy of this writing."""
        self.make_legacy()
        self.paths.migrate_from_legacy()
        self.assertTrue((self.legacy / "corpus" / "00-piece.md").is_file())
        self.assertTrue((self.legacy / "annotations.md").is_file())

    def test_migration_never_overwrites_existing_work(self):
        self.make_legacy()
        self.paths.corpus_dir().mkdir(parents=True)
        (self.paths.corpus_dir() / "mine.md").write_text("newer\n", encoding="utf-8")
        self.paths.annotations().write_text("my newer notes\n", encoding="utf-8")
        moved = self.paths.migrate_from_legacy()
        # Already configured, so nothing is touched at all.
        self.assertEqual(moved, [])
        self.assertEqual(self.paths.annotations().read_text(), "my newer notes\n")

    def test_migration_is_idempotent(self):
        self.make_legacy()
        first = self.paths.migrate_from_legacy()
        second = self.paths.migrate_from_legacy()
        self.assertTrue(first)
        self.assertEqual(second, [], "second run copied again")

    def test_nothing_happens_without_a_legacy_install(self):
        self.assertEqual(self.paths.migrate_from_legacy(), [])

    def test_dry_run_writes_nothing(self):
        self.make_legacy()
        pending = self.paths.migrate_from_legacy(dry_run=True)
        self.assertTrue(pending)
        self.assertFalse(self.paths.corpus_dir().exists())


class BaselineGate(VoiceCase):

    def corpus(self, pieces=2):
        self.paths.corpus_dir().mkdir(parents=True)
        for i in range(pieces):
            (self.paths.corpus_dir() / ("%02d.md" % i)).write_text(
                "Piece %d. A sentence I really wrote about a real thing.\n" % i,
                encoding="utf-8")
        self.paths.annotations().write_text("1. I open short.\n", encoding="utf-8")

    def test_no_corpus_is_reported_not_faked(self):
        """The worst failure would be inventing a voice it was never given."""
        rc, out = self.run_script("check_baseline.py")
        self.assertIn("NO_CORPUS", out)

    def test_fresh_corpus_requires_regeneration(self):
        self.corpus()
        rc, out = self.run_script("check_baseline.py")
        self.assertIn("REGENERATE", out)

    def test_matching_hash_with_full_coverage_passes(self):
        self.corpus()
        rc, out = self.run_script("check_baseline.py")
        h = [line.split(":")[-1].strip() for line in out.split("\n") if "corpus hash" in line.lower()]
        self.assertTrue(h, out)
        self.paths.runtime_dir().mkdir(parents=True, exist_ok=True)
        self.paths.voice_model().write_text(
            "> Generated from corpus hash: %s\n" % h[0], encoding="utf-8")
        self.paths.corpus_notes().write_text(
            "## 00.md\n\n\"A sentence I really wrote about a real thing.\"\n\n"
            "## 01.md\n\n\"A sentence I really wrote about a real thing.\"\n",
            encoding="utf-8")
        rc, out = self.run_script("check_baseline.py")
        self.assertIn("BASELINE_OK", out)

    def test_editing_the_corpus_forces_a_rebuild(self):
        self.test_matching_hash_with_full_coverage_passes()
        (self.paths.corpus_dir() / "02.md").write_text("A new piece.\n", encoding="utf-8")
        rc, out = self.run_script("check_baseline.py")
        self.assertIn("REGENERATE", out)

    def test_notes_without_verbatim_quotes_are_rejected(self):
        """The coverage gate is what stops the model summarising instead of reading."""
        self.corpus()
        rc, out = self.run_script("check_baseline.py")
        h = [line.split(":")[-1].strip() for line in out.split("\n") if "corpus hash" in line.lower()][0]
        self.paths.runtime_dir().mkdir(parents=True, exist_ok=True)
        self.paths.voice_model().write_text(
            "> Generated from corpus hash: %s\n" % h, encoding="utf-8")
        self.paths.corpus_notes().write_text(
            "## 00.md\n\nSummarised by inspection, no quotes.\n"
            "## 01.md\n\nAlso summarised.\n", encoding="utf-8")
        rc, out = self.run_script("check_baseline.py")
        self.assertIn("REGENERATE", out)

    def test_migration_is_announced_on_the_first_run(self):
        self.make_legacy()
        rc, out = self.run_script("check_baseline.py")
        self.assertIn("MIGRATED", out)
        self.assertIn("NOT deleted", out)


class SafetyNet(VoiceCase):

    def corpus_of(self, text, pieces=3):
        self.paths.corpus_dir().mkdir(parents=True)
        for i in range(pieces):
            (self.paths.corpus_dir() / ("%02d.md" % i)).write_text(text, encoding="utf-8")

    def test_clean_draft_passes(self):
        prose = ("I don't think that's the whole story. It's simpler than it looks, "
                 "and I'd rather say so plainly.\n\nHere's the part that matters. "
                 "We didn't ship it because the numbers weren't there.\n")
        self.corpus_of(prose)
        d = self.tmp / "draft.md"
        d.write_text(prose, encoding="utf-8")
        rc, out = self.run_script("safety_net.py", str(d))
        self.assertIn("NO_VIOLATIONS", out, out)

    def test_expanded_contractions_are_flagged(self):
        """The canonical tell of a 'voice rewrite' that was really a find-and-replace."""
        self.corpus_of("I don't think so. It's simpler than that, and I'd say so.\n"
                       "I can't see it working. We're not doing that.\n")
        d = self.tmp / "draft.md"
        d.write_text("I do not think so. It is simpler than that, and I would say so.\n"
                     "I cannot see it working. We are not doing that.\n", encoding="utf-8")
        rc, out = self.run_script("safety_net.py", str(d))
        self.assertIn("VIOLATIONS", out, out)

    def test_missing_draft_is_an_error_not_a_pass(self):
        rc, out = self.run_script("safety_net.py", str(self.tmp / "nope.md"))
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
