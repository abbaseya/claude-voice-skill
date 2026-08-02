#!/usr/bin/env python
"""Plugin structure, and the paths inside the protocol, must actually resolve.

The failure this guards against is invisible to the author: a skill that names a
script by a path that only exists on the machine it was written on. It works
locally, ships, and does nothing for anybody else.
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class PluginManifest(unittest.TestCase):

    def setUp(self):
        self.m = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

    def test_manifest_is_at_the_repo_root(self):
        self.assertTrue((ROOT / ".claude-plugin" / "plugin.json").is_file())

    def test_name_is_kebab_case(self):
        self.assertTrue(KEBAB.match(self.m["name"]), self.m["name"])

    def test_required_fields(self):
        for k in ("name", "description", "version"):
            self.assertTrue(self.m.get(k), k)


class Skills(unittest.TestCase):

    def files(self):
        return sorted((ROOT / "skills").glob("*/SKILL.md"))

    def test_expected_skills_exist(self):
        self.assertEqual({p.parent.name for p in self.files()}, {"draft", "setup"})

    def test_skill_name_matches_directory(self):
        for p in self.files():
            head = p.read_text(encoding="utf-8").split("---")[1]
            declared = re.search(r"^name:\s*(\S+)", head, re.M).group(1)
            self.assertEqual(declared, p.parent.name, p)

    def test_every_referenced_script_exists(self):
        rx = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
        checked = 0
        for p in self.files():
            for rel in rx.findall(p.read_text(encoding="utf-8")):
                self.assertTrue((ROOT / rel).exists(),
                                "%s references missing %s" % (p.name, rel))
                checked += 1
        self.assertGreater(checked, 0)

    def test_no_skill_hardcodes_the_old_install_path(self):
        """The whole point of becoming a plugin: scripts move, data does not."""
        for p in self.files():
            text = p.read_text(encoding="utf-8")
            self.assertNotIn(".claude/skills/my-voice/scripts", text, p.name)
            self.assertNotIn("/Users/", text, p.name)

    def test_draft_skill_refuses_without_a_corpus(self):
        """A voice skill with no samples must say so, not invent a voice."""
        text = (ROOT / "skills" / "draft" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("NO_CORPUS", text)
        self.assertIn("do not fabricate a voice", text)

    def test_draft_skill_documents_where_user_data_lives(self):
        text = (ROOT / "skills" / "draft" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("~/.claude/my-voice/", text)


class Templates(unittest.TestCase):

    def test_starter_templates_are_present(self):
        names = {p.name for p in (ROOT / "templates").glob("*.md")}
        self.assertEqual(names, {"annotations.md", "anti-corpus.md",
                                 "hard-rules.md", "corpus-README.md"})

    def test_templates_tell_the_user_to_replace_them(self):
        for n in ("annotations.md", "anti-corpus.md", "hard-rules.md"):
            t = (ROOT / "templates" / n).read_text(encoding="utf-8")
            self.assertRegex(t, r"(?i)(replace|delete them|placeholder|illustrative)", n)

    def test_no_corpus_directory_is_shipped(self):
        """A corpus in the repo would be someone else's voice in everyone's install."""
        self.assertFalse((ROOT / "corpus").exists())


class LeakGate(unittest.TestCase):

    LEAK = "Clau" + "diu"

    def run_checker(self, cwd):
        p = subprocess.run([sys.executable, str(cwd / "bin" / "check-leaks.py")],
                           capture_output=True, text=True, cwd=str(cwd))
        return p.returncode, p.stdout + p.stderr

    def test_repo_is_clean(self):
        rc, out = self.run_checker(ROOT)
        self.assertEqual(rc, 0, out)

    def test_a_planted_leak_is_caught(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "bin").mkdir()
            (td / "bin" / "check-leaks.py").write_text(
                (ROOT / "bin" / "check-leaks.py").read_text(encoding="utf-8"),
                encoding="utf-8")
            (td / "templates").mkdir()
            (td / "templates" / "x.md").write_text("ask %s\n" % self.LEAK, encoding="utf-8")
            rc, out = self.run_checker(td)
            self.assertEqual(rc, 1, out)


if __name__ == "__main__":
    unittest.main()
