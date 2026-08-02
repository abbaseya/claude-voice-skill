<!--
This file holds your ABSOLUTE do/don't rules for your own voice.

How this differs from the other inputs:
- corpus/        — shows where your voice LIVES (the source the writer-model is built from).
- annotations.md — soft observations that calibrate the writer-model. NOT a checklist.
- anti-corpus.md — off-voice examples that mark where your voice STOPS.
- hard-rules.md  — ABSOLUTE constraints. These override the writer-model AND the corpus
                   whenever they conflict. If a rule here says "never X", then never X —
                   even if the corpus shows you doing X sometimes.

Two kinds of rules live here:

1. Judgment rules — prose do/don't lines the model reads at draft time and re-checks at
   critique time. Use these for anything that needs judgment to apply.

2. Machine-checked rules — inside the <!-- machine-checked-rules --> markers below. Each
   line is `- `<regex>` <message>`. The safety net (scripts/safety_net.py) parses this
   section, compiles each regex, and flags any match in a draft. The regexes run with
   re.IGNORECASE | re.MULTILINE — use an inline (?-i:...) group to force case-sensitivity
   (e.g. for capitalization rules). A row with a regex the script can't compile is skipped.

The rules below are ILLUSTRATIVE — they show the SHAPE of an entry. Delete them and add
your own.
-->

---

## Judgment rules

- Never open with a throat-clearing announcement of the writing ("In this post I will…", "A few thoughts on…").
- Never end with engagement bait ("Let me know your thoughts in the comments!").
- Always cite a source for any factual or numeric claim.

## Machine-checked rules

These are caught mechanically by the safety net. Keep each one to a single regex per line.

<!-- machine-checked-rules:start -->
- `\bvery very\b` doubled intensifier — pick one stronger word instead.
- `!{2,}` multiple exclamation marks in a row — one is enough.
- `\b(synergy|leverage|game-?changer)\b` marketing buzzword — say what actually happens.
<!-- machine-checked-rules:end -->
