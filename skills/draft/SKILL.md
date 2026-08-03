---
name: draft
description: Use when drafting any first-person content in my voice — LinkedIn posts, articles, blog drafts, announcements, customer-facing writeups. Forces an ordered protocol that builds an internal model of me-as-writer from the corpus and drafts from inside that model. Compose with topic-specific skills for grounding.
---

# My voice

This skill produces drafts in my voice by forcing the model — at every invocation — to **inhabit me as a writer** before drafting, draft from inside that inhabitation, and critique the draft as I would. The corpus is the source. Annotations and anti-corpus calibrate. Hard rules (`hard-rules.md`) are absolute — they override the writer-model and the corpus whenever they conflict. The protocol is the forcing function: it makes the inhabitation cheap to do and expensive to skip.

There is a real limit here: context conditioning leaves the model's weights unchanged, so some gap always remains and the last stretch is the writer's own editing pass. What that gap actually measures has not been established, and no figure should be quoted as if it had — treat a disappointing draft as a thing to measure, not as the ceiling arriving.

**Where the inputs live.** Throughout this protocol, **`VOICE`** = `~/.claude/my-voice/` (or `$MY_VOICE_HOME` if set). The corpus (`corpus/`), `annotations.md`, `anti-corpus.md`, `hard-rules.md` and the generated `runtime/` cache all live under `VOICE` — every bare `corpus/`, `runtime/…`, `annotations.md`, `anti-corpus.md` and `hard-rules.md` reference below means `VOICE/…`. They live **outside the plugin on purpose**: the plugin directory is replaced on every update, and anything of mine stored inside it would be deleted. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/paths.py"` to print the resolved locations.

**Precondition — no corpus, no voice draft.** If step 1 prints `NO_CORPUS`, **do not run this protocol and do not fabricate a voice.** Say: *"No writing samples are configured, so I can't voice-match. Run `/my-voice:setup` and add 8–15 pieces of your own writing, then ask again — for now I'll draft normally."* Then write an ordinary draft without the protocol. A skill that invents a voice it was never given is worse than one that admits it cannot.

---

## Mandatory protocol

Do every step in order. Do not skip steps because the topic seems simple, the draft seems short, or I "already know how the writer writes." The corpus and my prior compete; this protocol is what makes the corpus win.

### 0. Setup

This run's per-invocation artifacts live in a **session-scoped** subdirectory so that concurrent sessions don't clobber each other's draft prep. Resolve (and create) it:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/session_runtime.py"
```

It prints the absolute path of THIS session's runtime dir — e.g. `~/.claude/my-voice/runtime/sessions/<session-id>/`. Call that path **`$SESSION_DIR`** and use it for every per-invocation artifact below (`topic.md`, `engagement.md`, `ideas.md`, `critique.md`, `draft.md`).

The shared corpus cache — `runtime/voice_model.md` and `runtime/corpus_notes.md` — stays at the `runtime/` root (keyed by corpus hash, identical across sessions). Do not move it under `$SESSION_DIR`.

### 1. Baseline check

Run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_baseline.py"
```

- If output starts with `NO_CORPUS`: **stop the protocol** — see the precondition above. Draft normally and tell the user how to add a corpus.
- If output starts with `MIGRATED`: a pre-plugin install was found and the writing was copied across. Relay those lines to the user verbatim, then carry on with whatever the output says next.
- If output starts with `BASELINE_OK`: skip to step 4 (the writer-model is current).
- If output starts with `REGENERATE`: continue with steps 2–3 to rebuild the writer-model.

### 2. Per-piece corpus reading (only when regenerating)

Read every file in `corpus/` **one at a time**, with the Read tool, no batching. After each file, append a section to `runtime/corpus_notes.md` in this exact shape:

```
## <filename>
**Summary (one sentence):** <...>
**Three to five specific moves the writer makes in this piece, with quoted excerpts:**
- <move 1> — "<short quote from the piece>"
- <move 2> — "<short quote>"
- ...
```

The quotes are not optional. They are the proof I actually read the piece rather than skimming. A model that skims cannot produce accurate quotes.

`check_baseline.py` mechanically verifies, after the writer-model is generated, that every `corpus/*.md` has its own `## <filename>` section in `corpus_notes.md` and that at least one quoted excerpt per section appears verbatim in the source. Batching multiple files into a single "by inspection" section, or summarising without verbatim quotes, fails this gate and forces a redo. Do not try to economise here — the gate will catch it.

### 3. Synthesize the writer-model (only when regenerating)

Build `runtime/voice_model.md`. The first non-empty line MUST be:

```
> Generated from corpus hash: <copy the hash printed by check_baseline.py>
```

Required sections, each with corpus citations by filename:

- **Opening moves.** What the writer's first 1–2 sentences typically do, mechanically. What the writer avoids opening with (cite anti-corpus where applicable).
- **Transition vocabulary.** Specific connectors the writer reaches for. Specific ones the writer doesn't.
- **Paragraph and sentence rhythm.** Variance pattern. Where one-line paragraphs land. How long paragraphs get.
- **What the writer reaches for.** Concrete moves: parenthetical italics, light single-word bold, inline links to references, em-dashes with spaces for asides, story-shaped framing (intro/problem → context/findings → outro/recommendation), or whatever the corpus shows.
- **What the writer avoids.** Drawn from `annotations.md` + `anti-corpus.md` + corpus observation: typographic preferences, formal connectors, balanced tripartite openers, trailing rhetorical questions, formulaic constructs.
- **Handling uncertainty.** How the writer flags estimates, hedges, and admissions of "I don't know."
- **Handling praise.** How the writer gives credit. Cite the corpus piece that shows this.
- **Handling criticism.** How the writer names a failure mode without stacking complaints.
- **Closings.** How the writer ends — declarative observations or terminal claims, never meta-closers like "happy to discuss" or generic meeting invites (unless the corpus actually shows the writer using them).

Each claim cites at least one corpus piece by filename.

### 4. Read the calibrators and hard rules

Read `annotations.md` and `anti-corpus.md` end to end. They calibrate the writer-model — they do not replace it. Do not draft directly from annotations as a checklist; that produces typographic substitution rather than voice.

Then read `hard-rules.md` if it exists. **Hard rules are not calibrators.** Annotations and anti-corpus are soft signals that shaped the writer-model; hard rules are absolute do/don't constraints the writer has set, and they override the writer-model and the corpus whenever they conflict — even if the corpus shows the writer occasionally breaking one. Apply every hard rule as a gate at draft time (step 8) and re-check the draft against each one at critique time (step 9). The machine-checked subset (the rows inside the `machine-checked-rules` markers) is additionally enforced by the safety net in step 11. `hard-rules.md` is read fresh on every run and is not part of the cached writer-model, so editing it takes effect immediately with no regeneration.

### 5. Topic intake and exemplar selection

Write `$SESSION_DIR/topic.md` with:
- **Topic and goal:** one sentence.
- **Target length and genre:** roughly how many words, and which genre from `corpus/genres.txt` (if that file exists).

Then pick the exemplars mechanically rather than by judgement:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pick_exemplars.py" --words <target> [--genre <genre>]
```

It ranks the corpus by **shape** — length, density, register — never by subject, because matching on topic pulls the draft toward reusing the exemplar's content instead of its rhythm. Paste its output into `topic.md`.

Read its warnings. If it reports that the target is longer than anything in the corpus, say so in the final delivery: past that length the draft has no example to imitate and will drift toward the model's defaults, and that is worth the writer knowing before they publish rather than after.

### 6. Engagement note

Write `$SESSION_DIR/engagement.md`. List 5–7 specific moves drawn from `runtime/voice_model.md` that I commit to applying in this draft. Each move ties to a section of the voice model. This is the bridge that puts the writer-model into active reasoning before drafting begins.

### 7. Abstract the input to ideas (only when rewriting a provided input)

If the task is to rewrite an existing draft (input file provided), read the input file **once** and write `$SESSION_DIR/ideas.md` as a **flat unordered list of the core ideas** the input conveys. No structure preserved. No section labels copied. No paragraph order copied. No bullet count preserved. Just the substantive points, each as a single bullet, in whatever order makes sense to me reading them fresh.

After writing `ideas.md`, **do not read the input file again**. This is a hard rule. The input's structural shape is a stronger pull on generation than the writer-model, and the only way to break that pull is to forget the input and rebuild from `ideas.md` + `voice_model.md` from scratch.

If the task is to write a fresh piece (no input), skip this step — my `topic.md` already contains the substance.

### 8. Draft

**First, read every exemplar from step 5 in full, with the Read tool, immediately before writing.** Not skimmed, not recalled from the writer-model — the actual text, in context, at drafting time.

This is the step the whole protocol turns on. A writer-model is a *description* of how somebody writes, and a description is something the model obeys rather than imitates. Obeying "varies sentence length deliberately" reliably produces sentences of uniform length, because the instruction carries no rhythm to copy, only an intention to satisfy. The passages carry the rhythm. Drafting from the description alone is what produces prose that passes every stated rule and still reads as generated.

Then write the draft to `$SESSION_DIR/draft.md`. References, in order:
1. **The exemplar pieces themselves** — the rhythm, sentence shapes and paragraph movement to imitate.
2. `$SESSION_DIR/engagement.md` — the moves committed for this specific draft.
3. `$SESSION_DIR/ideas.md` (if rewriting) or `$SESSION_DIR/topic.md` (if fresh) — the substance.
4. `hard-rules.md` — absolute do/don't constraints. These override 1–3 on any conflict.
5. `anti-corpus.md` — patterns to avoid.
6. `runtime/voice_model.md` — consult only to settle a question the exemplars do not answer.

Do **not** open the input file again during drafting (if rewriting). Do **not** consult `annotations.md` directly while drafting. The voice model already incorporated annotations; reopening either of those files reintroduces the structural mimicry or checklist-application failure modes. Hard rules are the exception: apply every rule in `hard-rules.md`, and when a hard rule conflicts with an observed corpus habit, the hard rule wins.

### 9. In-voice critique

Write `$SESSION_DIR/critique.md`. Re-read the draft as the writer. Strike the 3 worst sentences and explain why each one fails, citing `voice_model.md` or `anti-corpus.md`. Be brutal. If I cannot honestly find 3 sentences that sound like Claude pretending to be the writer, I didn't critique honestly — try again with sharper eyes. Also check the draft against every rule in `hard-rules.md`: a hard-rule violation is an automatic strike regardless of how the sentence otherwise reads.

### 10. Revise

Apply the critique. Rewrite the struck sentences. Keep revising until the draft would survive its own critique pass.

### 11. Safety net

Run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safety_net.py" "$SESSION_DIR/draft.md" [--genre <genre>] [--input <path-to-input.md>]
```

Pass `--genre` so the draft is measured against the right register. Pass `--input` when rewriting an existing draft. The script runs three layers:

- **Per-draft.** Sentence rhythm (a composite check for prose that is short *and* uniform *and* never stretches out), typography, contraction floor and ceiling, the machine-checked patterns from `hard-rules.md`, and — with `--input` — structural mimicry, including how much of the input's word sequence survives in order.
- **Window.** Signature punctuation across the last several drafts. A marker absent from one piece proves nothing; absent across a run it is drift.
- **Formula.** Whether recent drafts have converged on one shape. This is the failure nobody sees inside a single piece and every regular reader sees across ten.

Output:
- `NO_VIOLATIONS` and no `DRIFT` block: deliver the draft.
- `VIOLATIONS`: address each one and re-run, or document explicitly why a deviation is intentional (rare — most violations are real).
- `DRIFT`: these are about the recent run, not this draft alone, and they are still this draft's job. If the trailer has been fading for eight drafts, this is the one that stops the trend. Do not treat a clean `NO_VIOLATIONS` as permission to ignore them.

The safety net is **mechanical**. It is **not** a voice judge. Passing it does not mean the draft sounds like the writer; failing it almost certainly means it doesn't.

### 12. Deliver

Show the draft to the user. Mention any safety-net violations that were intentional and unfixed. Do not narrate the protocol — the artifacts in `runtime/` are the work; the draft is the output.

---

## Composition with other skills

This skill provides voice. Topic skills (a `convert-*` skill, a `product-*` skill, etc.) provide grounding. When both apply: read the topic skill for what's true, read this skill for how the writer would say it. Any confidentiality boundary in a topic skill always overrides voice — never copy internal names from a topic skill into voice-matched output.

## What this skill does not do

- It does not reproduce a voice exactly. Weights are unchanged, so a gap remains; its size is not something this skill has measured, and any specific percentage would be invented.
- It does not replace the writer's editor pass.
- It does not work for content that isn't the writer's first-person voice (e.g., third-party docs, formal contracts).

## Corpus health

Two tools exist because the commonest reason a draft misses voice is not the protocol — it is that the corpus cannot answer the question being asked of it.

**Is there enough of the right kind of writing?**

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pick_exemplars.py" --words 1000 --genre article
```

Its `EVIDENCE DEPTH` block reports how much writing exists in the register being drafted, and warns when the target is longer than anything available. A corpus of short pieces cannot teach the back half of a long one, and what the model reaches for once the examples run out is its own default.

**Do the thresholds accept the writing they came from?**

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/calibrate.py" --verbose
```

Run after changing a threshold, adding pieces, or editing `genres.txt`. A gate that rejects the corpus it was built from is not strict, it is broken — and the first few false alarms teach everybody to stop reading it.

**Genres.** An optional `corpus/genres.txt` maps globs to registers (`article: wp-*.md`). Thresholds are then computed per register. This matters more than it sounds: the same writer's public prose and working notes can differ by an order of magnitude on signature punctuation, and pooled, the floor for one collapses toward the other and stops catching the drift it exists to catch.

**Short of material?**

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/harvest_sessions.py" --dry-run --sample 5
```

Builds corpus pieces from what the writer has typed into Claude Code — unedited first-person prose written with no thought of how it would read, which is a better sample than anything anyone submits deliberately. Only their own typed messages; tool output, pasted files and agent-written prompts are excluded. Heated messages are dropped, secrets are redacted, mechanical typos are corrected and grammar is left alone. Give it its own genre: instructing an agent is not the register an article gets written in.

## When the corpus changes

Editing or adding a corpus file invalidates `runtime/voice_model.md`. The next invocation's baseline check will detect the hash mismatch and force regeneration via steps 2–3. This adds roughly 30 seconds to one run; subsequent runs reuse the cache.

## When a draft misses voice in a way the protocol didn't catch

Add the failure to `anti-corpus.md` with a 2-sentence diagnosis. The next invocation reads it as part of step 4. If the failure is a recognizable pattern, also add a regex to `ANTI_TIC_PATTERNS` at the top of `scripts/safety_net.py` so the safety net catches it mechanically next time.

## Runtime artifacts

The `runtime/` directory contains the cognitive-forcing artifacts, split into a shared layer and a per-session layer:

**Shared across sessions** — corpus-derived, keyed by corpus hash, identical for every session on the same corpus. Live at the `runtime/` root:

- `voice_model.md` — the inhabited writer-model. Cached; regenerated when corpus changes.
- `corpus_notes.md` — per-piece reading notes. Regenerated when corpus changes.

**Per session** — under `runtime/sessions/<session-id>/` (`$SESSION_DIR`, resolved by `scripts/session_runtime.py` in step 0), so concurrent sessions don't clobber each other:

- `topic.md`, `engagement.md`, `ideas.md`, `critique.md`, `draft.md` — per-invocation. Overwritten on each run within the same session. (`ideas.md` only exists when rewriting an input.)

These artifacts are visible by design. Inspect them if a draft misses voice — the failure usually shows up in `voice_model.md` or `engagement.md` first.
