---
name: your-voice
description: Use when drafting any first-person content in your voice — LinkedIn posts, articles, blog drafts, announcements, customer-facing writeups. Forces an ordered protocol that builds an internal model of you-as-writer from the corpus and drafts from inside that model. Compose with topic-specific skills for grounding.
---

# Your voice

This skill produces drafts in your voice by forcing the model — at every invocation — to **inhabit you as a writer** before drafting, draft from inside that inhabitation, and critique the draft as you would. The corpus is the source. Annotations and anti-corpus calibrate. The protocol is the forcing function: it makes the inhabitation cheap to do and expensive to skip.

The mechanism has a known structural ceiling around 85% voice match — text-only context conditioning cannot exceed that without weight-level fine-tuning. The last 10–15% is your editing pass.

---

## Mandatory protocol

Do every step in order. Do not skip steps because the topic seems simple, the draft seems short, or you "already know how the writer writes." The corpus and your prior compete; this protocol is what makes the corpus win.

### 0. Setup

Ensure the runtime directory exists:

```
mkdir -p ~/.claude/skills/your-voice/runtime
```

### 1. Baseline check

Run:

```
python3 ~/.claude/skills/your-voice/scripts/check_baseline.py
```

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

The quotes are not optional. They are the proof you actually read the piece rather than skimming. A model that skims cannot produce accurate quotes.

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

### 4. Read the calibrators

Read `annotations.md` and `anti-corpus.md` end to end. They calibrate the writer-model — they do not replace it. Do not draft directly from annotations as a checklist; that produces typographic substitution rather than voice.

### 5. Topic intake

Write `runtime/topic.md` with two short sections:
- **Topic and goal:** one sentence.
- **Closest-shape corpus pieces:** name 2–3 corpus pieces that match the **shape** (length, register, structure) of what's about to be written — not the topic. State why each was picked.

### 6. Engagement note

Write `runtime/engagement.md`. List 5–7 specific moves drawn from `runtime/voice_model.md` that you commit to applying in this draft. Each move ties to a section of the voice model. This is the bridge that puts the writer-model into active reasoning before drafting begins.

### 7. Abstract the input to ideas (only when rewriting a provided input)

If the task is to rewrite an existing draft (input file provided), read the input file **once** and write `runtime/ideas.md` as a **flat unordered list of the core ideas** the input conveys. No structure preserved. No section labels copied. No paragraph order copied. No bullet count preserved. Just the substantive points, each as a single bullet, in whatever order makes sense to you reading them fresh.

After writing `ideas.md`, **do not read the input file again**. This is a hard rule. The input's structural shape is a stronger pull on generation than the writer-model, and the only way to break that pull is to forget the input and rebuild from `ideas.md` + `voice_model.md` from scratch.

If the task is to write a fresh piece (no input), skip this step — your `topic.md` already contains the substance.

### 8. Draft

Write the draft. Primary references, in order:
1. `runtime/voice_model.md` — the inhabited writer-model. **The structural shape of the draft comes from here, not from the input.**
2. `runtime/engagement.md` — the moves committed for this specific draft.
3. `runtime/ideas.md` (if rewriting) or `runtime/topic.md` (if fresh) — the substance.
4. `anti-corpus.md` — patterns to avoid.
5. The corpus itself, only when sampling specific phrasings.

Do **not** open the input file again during drafting (if rewriting). Do **not** consult `annotations.md` directly while drafting. The voice model already incorporated annotations; reopening either of those files reintroduces the structural mimicry or checklist-application failure modes.

### 9. In-voice critique

Write `runtime/critique.md`. Re-read the draft as the writer. Strike the 3 worst sentences and explain why each one fails, citing `voice_model.md` or `anti-corpus.md`. Be brutal. If you cannot honestly find 3 sentences that sound like Claude pretending to be the writer, you didn't critique honestly — try again with sharper eyes.

### 10. Revise

Apply the critique. Rewrite the struck sentences. Keep revising until the draft would survive its own critique pass.

### 11. Safety net

Run:

```
python3 ~/.claude/skills/your-voice/scripts/safety_net.py <path-to-draft.md> [--input <path-to-input.md>]
```

Pass `--input` when rewriting an existing draft. The script then runs both:
- Typography checks (contractions, headings, list density, paragraph variance, anti-tic patterns).
- A **structural drift check**: compares section labels, list shape, and paragraph counts between input and draft. Flags when the draft's structure too closely mirrors the input — the failure mode where voice gets applied as a coat of paint over a preserved input skeleton.

When fresh-drafting (no input), call without `--input`.

- If `NO_VIOLATIONS`: deliver the draft.
- If `VIOLATIONS`: address each one and re-run, or document explicitly why a deviation is intentional (rare — most violations are real).

The safety net is **mechanical**. It catches catastrophic typography drift and structural mimicry. It is **not** a voice judge. Passing it does not mean the draft sounds like the writer; failing it almost certainly means it doesn't.

### 12. Deliver

Show the draft to the user. Mention any safety-net violations that were intentional and unfixed. Do not narrate the protocol — the artifacts in `runtime/` are the work; the draft is the output.

---

## Composition with other skills

This skill provides voice. Topic skills (a `convert-*` skill, a `product-*` skill, etc.) provide grounding. When both apply: read the topic skill for what's true, read this skill for how the writer would say it. Any confidentiality boundary in a topic skill always overrides voice — never copy internal names from a topic skill into voice-matched output.

## What this skill does not do

- It does not guarantee 99% voice match. The structural ceiling for context-conditioned skills is around 85%. Higher fidelity requires fine-tuning, which is not currently exposed for Claude.
- It does not replace the writer's editor pass.
- It does not work for content that isn't the writer's first-person voice (e.g., third-party docs, formal contracts).

## When the corpus changes

Editing or adding a corpus file invalidates `runtime/voice_model.md`. The next invocation's baseline check will detect the hash mismatch and force regeneration via steps 2–3. This adds roughly 30 seconds to one run; subsequent runs reuse the cache.

## When a draft misses voice in a way the protocol didn't catch

Add the failure to `anti-corpus.md` with a 2-sentence diagnosis. The next invocation reads it as part of step 4. If the failure is a recognizable pattern, also add a regex to `ANTI_TIC_PATTERNS` at the top of `scripts/safety_net.py` so the safety net catches it mechanically next time.

## Runtime artifacts

The `runtime/` directory contains the cognitive-forcing artifacts:

- `voice_model.md` — the inhabited writer-model. Cached; regenerated when corpus changes.
- `corpus_notes.md` — per-piece reading notes. Regenerated when corpus changes.
- `topic.md`, `engagement.md`, `ideas.md`, `critique.md` — per-invocation. Overwritten each run. (`ideas.md` only exists when rewriting an input.)

These artifacts are visible by design. Inspect them if a draft misses voice — the failure usually shows up in `voice_model.md` or `engagement.md` first.
