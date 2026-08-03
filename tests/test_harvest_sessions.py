#!/usr/bin/env python
"""Harvesting somebody's session transcripts into a corpus.

Everything here guards a way this can go wrong that the person would not
notice until it was already shaping their published writing: machine output
mistaken for their prose, a bad afternoon feeding into how they sound in
public, a key copied into a file, or a "correction" rewriting grammar that
was theirs to begin with.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import harvest_sessions as hs  # noqa: E402


def rec(content, **kw):
    base = {"type": "user", "message": {"role": "user", "content": content}}
    base.update(kw)
    return base


class WhatCountsAsTheirWriting(unittest.TestCase):

    def test_a_typed_message_is_kept(self):
        self.assertTrue(hs.is_user_authored(rec("a real message I typed")))

    def test_tool_results_are_not_their_writing(self):
        self.assertFalse(hs.is_user_authored(rec("x", toolUseResult={"ok": 1})))

    def test_meta_records_are_excluded(self):
        self.assertFalse(hs.is_user_authored(rec("x", isMeta=True)))

    def test_agent_to_agent_prompts_are_excluded(self):
        """Sidechain user turns are written by an agent to a subagent. They
        read exactly like instructions the person would write, which is
        precisely why they have to be excluded by structure and not by eye."""
        self.assertFalse(hs.is_user_authored(rec("investigate this", isSidechain=True)))

    def test_slash_command_stubs_are_excluded(self):
        self.assertFalse(hs.is_user_authored(rec("<command-name>/effort</command-name>")))

    def test_non_text_content_blocks_are_excluded(self):
        self.assertFalse(hs.is_user_authored(
            rec([{"type": "tool_result", "content": "..."}])))


class MachineTextStripping(unittest.TestCase):

    def test_task_notifications_are_removed(self):
        """These arrive inside the user turn and read as prose to any filter
        that only checks the record type. Left in, they were 85k words of the
        first harvest — more than twice the real corpus."""
        text = ("here is what I actually wrote\n"
                "<task-notification>\n<task-id>abc</task-id>\n"
                "<summary>Background command completed</summary>\n</task-notification>")
        out = hs.strip_machine_text(text)
        self.assertIn("here is what I actually wrote", out)
        self.assertNotIn("task-id", out)
        self.assertNotIn("Background command", out)

    def test_fenced_code_is_removed(self):
        out = hs.strip_machine_text("look at this\n```\nprint(1)\n```\nand fix it")
        self.assertNotIn("print(1)", out)
        self.assertIn("and fix it", out)


class HeatedMessages(unittest.TestCase):

    def test_profanity_is_dropped(self):
        self.assertTrue(hs.is_heated("this is fucked up, do your job"))

    def test_sustained_shouting_is_dropped(self):
        self.assertTrue(hs.is_heated("ALL OF THIS IS BROKEN AGAIN AND NOBODY CHECKED IT"))

    def test_ordinary_critical_feedback_is_kept(self):
        """Being blunt is not being angry, and a filter that cannot tell them
        apart strips out the writer's actual register."""
        self.assertFalse(hs.is_heated(
            "I do not think that approach works, the config returns a different "
            "shape and we would have to special-case it everywhere."))


class Redaction(unittest.TestCase):

    def test_secrets_and_identifiers_are_removed(self):
        for probe in ("someone@example.com",
                      "sk-abcdefghijklmnopqrstuvwxyz012345",
                      "AKIAIOSFODNN7EXAMPLE",
                      "550e8400-e29b-41d4-a716-446655440000"):
            with self.subTest(probe=probe):
                self.assertNotIn(probe, hs.redact("value is %s here" % probe))


class TypoCorrection(unittest.TestCase):

    def test_mechanical_slips_are_fixed(self):
        out, n = hs.fix_typos("wiht teh wrong chanegs")
        self.assertIn("with", out)
        self.assertIn("changes", out)
        self.assertGreaterEqual(n, 2)

    def test_case_is_preserved(self):
        out, _ = hs.fix_typos("Chanegs are needed")
        self.assertTrue(out.startswith("Changes"))

    def test_grammar_and_idiom_are_left_alone(self):
        """The whole reason this is a curated map and not a spellchecker.
        These constructions are the writer, not errors, and normalising them
        removes the signal that separates their prose from generated prose."""
        original = "it worth the shot, such concept is not going to cut it"
        out, _ = hs.fix_typos(original)
        self.assertEqual(out, original)

    def test_regional_spelling_survives(self):
        for word in ("behaviour", "organised", "sceptic"):
            with self.subTest(word=word):
                out, _ = hs.fix_typos(word)
                self.assertEqual(out, word)

    def test_real_words_are_never_rewritten(self):
        """Automatic edit-distance suggested it's->its and apps->apis. Both
        would corrupt correct text, so neither may be in the map."""
        for word in ("it's", "apps", "async", "demo", "info", "auth"):
            with self.subTest(word=word):
                out, _ = hs.fix_typos(word)
                self.assertEqual(out, word)

    def test_substring_matches_do_not_fire(self):
        out, n = hs.fix_typos("internally")
        self.assertEqual(out, "internally")
        self.assertEqual(n, 0)


class Grouping(unittest.TestCase):

    def test_long_messages_are_kept_whole(self):
        """A considered explanation is the long-form first-person writing a
        corpus almost never has. Blended into a chunk of one-line
        instructions it stops being that."""
        msgs = [{"text": "w " * 400, "timestamp": "2026-01-01", "words": 400},
                {"text": "short one", "timestamp": "2026-01-02", "words": 30}]
        grouped, standalone = hs.group_into_pieces(msgs, 800)
        self.assertEqual(len(standalone), 1)
        self.assertEqual(standalone[0]["words"], 400)
        self.assertEqual(sum(len(g) for g in grouped), 1)


if __name__ == "__main__":
    unittest.main()
