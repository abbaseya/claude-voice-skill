# How to create a Claude Skill that writes in my own voice

A Claude Code plugin that drafts in **your** voice — built from your own writing, not from
adjectives describing it.

```
/plugin marketplace add abbaseya/claude-plugins
/plugin install my-voice@abbaseya
```

Then `/my-voice:setup` to create your writing folder, and `/my-voice:draft` to use it.

> **Upgrading from the plain-skill version?** If you cloned this into
> `~/.claude/skills/my-voice/` with your corpus inside it, the plugin finds that on its
> first run and copies your writing to `~/.claude/my-voice/`. It copies rather than
> moves and never overwrites — your originals stay exactly where they are. See
> [Install](#install) for what to do afterwards.

The rest of this README is the essay: why a voice skill built from a description of your
voice does not work, and what does. If you just want it running, the two commands above
are the whole install.

---

## The wrong way (and why it's tempting)

The intuitive approach: write a skill called `my-voice` that says things like _"My style is direct, technical, has a POV, uses backticks, dislikes corporate language."_ A list of adjectives and tendencies.

This is what most "writing style" prompts look like. It's also why most AI-written content sounds like AI written by a slightly different AI. Adjectives don't transfer voice. _"Be direct"_ produces 100 different outputs from 100 different LLMs, and none of them sound like me.

Voice isn't a set of properties — it's a set of _patterns_. The shape of my sentences. Where I put the verb. How long I let a thought run before a break. What I do with the second-most-important point. Whether I ever use a one-word paragraph. Whether I use em-dashes or parentheticals or both. These are checkable against actual writing, but they're nearly impossible to articulate from scratch. They operate below the level of conscious style.

A voice skill built from my description of my voice will be mediocre. A voice skill built from my _writing_ — actual samples — will be better. But samples alone are not enough either. They are necessary, not sufficient.

## Why "just put samples in a folder" doesn't work

The natural assumption: drop 8–15 samples in a `corpus/` folder, write a few rules in `SKILL.md`, point Claude at it, done. This is the structure most "voice" tools ship with. It produces drafts that sound _like a slightly different AI pretending to be me_, not like me.

The reason is mechanical. A skill is plain markdown injected into the model's context window. The corpus sits there as reference text. The model is _free_ to read it, but it's also free to skim — and pretraining bias toward "polished professional writing" is a much stronger force than 8–15 short samples in context. The model reads `SKILL.md`, intends to absorb the corpus, then defaults to its prior when drafting.

I can't fix this by writing more rules. Rules become a checklist the model applies typographically _(swap em-dash for en-dash, expand contractions, promote bold to ## headings)_ and reports back as "voice rewrite." It isn't.

The fix is structural: the skill must force the model to _inhabit I as a writer_ before drafting, by computing a structured model of my writing into context as an active step, then drafting from inside that model. The corpus is the source. The annotations and anti-corpus calibrate. The protocol is what makes the corpus actually win against the priors.

## Building an internal model of me-as-writer from the corpus

This is the load-bearing concept of the whole skill, so worth being precise about what it means.

### What "internal model" means here

There are two kinds of internal model. The first is _weight-level_ — the kind I'd get from fine-tuning. The corpus becomes part of the model's parameters and the probability distribution of next-token prediction shifts toward my voice. In principle this gives consistent voice across topics. In practice, at the data scale most individuals can produce (8–15 corpus pieces, maybe a hundred or two paired examples), fine-tuning a local 7B model produces drafts that are *worse* than what a well-built markdown skill produces — not better. The fine-tuning ceiling at small-data scale sits BELOW the markdown-skill ceiling, not above it. (Weight-level fine-tuning of Claude itself is also not exposed.)

The second is _context-level_ — the kind a markdown skill can produce. My corpus sits in the input context, and the model is free to read it and condition its output on it, but its weights are unchanged. Generation is still pulled hard toward pretraining priors *(i.e. polished professional writing)*. A good protocol can fight the pull, a bad one can't, but no protocol can eliminate it.

A markdown skill cannot build a true internal model. What it _can_ do is force the model to _simulate_ having one, every time, from scratch, by computing a structured analysis of my writing into context before drafting. That simulation is the writer-model. It's real and useful, and empirically — at the data scale most individuals can produce — it outperforms locally fine-tuned models of comparable accessibility. Both approaches have a ceiling and the fine-tune's sits lower; where the context-conditioned one sits is not something anybody here has measured, so this README does not put a number on it. See [The honest ceiling](#the-honest-ceiling).

### Why writing it down works (and reading silently doesn't)

Reading the corpus is passive. The text enters context and sits there. The model's prior toward "polished writing" still wins because the corpus has not been engaged with — it has only been _seen_.

Writing a structured analysis of the corpus is active. The act of producing the analysis forces the model to actually examine paragraph rhythm, opening shape, transition vocabulary, what the writer reaches for and avoids, and to commit observations to a file. That commitment is what biases generation: the model can't draft without referencing the analysis it just produced, because the analysis exists as the most recent and most concrete reference for "what the writer does."

This is why the protocol's step 2 *(per-piece reading with quoted excerpts)* and step 3 *(synthesis of `voice_model.md`)* are non-negotiable. A model that skips them and drafts directly from the corpus produces typographic substitution every time. A model that does them produces something closer to inhabitation.

### The structure of `voice_model.md`

The writer-model needs nine sections, each with corpus citations. Each section answers a specific question that the corpus alone leaves implicit, and that pretraining priors will get wrong if not made explicit:

- **Opening moves** — what my first 1–2 sentences mechanically do, and what I avoid opening with. _(Closes the "balanced tripartite hook" failure mode.)_
- **Transition vocabulary** — specific connectors I reach for, specific ones I don't. _(Closes the "Furthermore / Moreover / Notably" Claude default.)_
- **Paragraph and sentence rhythm** — variance pattern, where one-line paragraphs land, how long paragraphs get. _(Closes the "uniform-block" drift.)_
- **What the writer reaches for** — concrete moves: parenthetical italics, light bold, em-dashes, story-shaped framing, etc. _(Gives the drafting step a positive target.)_
- **What the writer avoids** — patterns from annotations + anti-corpus + corpus observation. _(Gives the drafting step a negative target.)_
- **Handling uncertainty** — how I flag estimates, hedges, "I don't know." _(Closes the "stack-the-qualifiers" Claude default.)_
- **Handling praise** — how I give credit. _(Voice changes register here; needs an explicit pattern.)_
- **Handling criticism** — how I name a failure mode without piling on. _(Same.)_
- **Closings** — declarative observations, terminal claims, memorable phrases, or inline reference links — never meta-closers or generic invitations. _(Closes the "happy to discuss" failure mode.)_

Every claim in the model cites at least one corpus piece by filename. The citations are what make the model _falsifiable_ rather than asserted — if a claim has no citation, it's a guess, and guesses don't bias generation reliably.

The first line of `voice_model.md` stamps the corpus hash:

```
> Generated from corpus hash: c3eec658f11a4844e1f2965ef3e8d0571e163c83330abdc4ebee813406af11df
```

The hash is the cache key. `check_baseline.py` reads it on every invocation and decides whether to reuse the cached writer-model or rebuild from scratch.

### How the writer-model gets used during drafting

Step 7 of the protocol *(engagement note)* is the bridge that puts the writer-model into _active_ reasoning before the first sentence is written. The engagement note picks 5–7 specific moves from `voice_model.md` and commits to applying them in this draft, each tied to a section of the model.

Step 8 *(draft)* names `voice_model.md` and `engagement.md` as the primary references — _not_ the corpus, _not_ the annotations. The model drafts against the analysis it just produced, with the corpus available only for sampling specific phrasings. This ordering matters: drafting against the corpus directly biases toward imitation of specific pieces; drafting against the writer-model biases toward the underlying patterns.

Step 9 *(in-voice critique)* re-engages the writer-model from the other direction. The model writes a critique of its own draft _as the writer would_, citing `voice_model.md` and `anti-corpus.md` for each failure. Step 10 *(revise)* applies the critique. This loop is where the last 5–10% of voice match comes from — most first drafts have at least three sentences that sound like Claude pretending, and the critique-revise loop is what surfaces and fixes them.

### Why this gets us closer to inhabitation than to imitation

Imitation produces sentences that resemble the corpus. Inhabitation produces sentences that resemble what the writer would have written on a topic the corpus has never touched. The difference is whether the model is operating from the writer's _patterns_ or from the writer's _previous outputs_.

The writer-model encodes patterns. The protocol's drafting and critique steps reference patterns, not outputs. The corpus stays as ground truth, but it's behind the analysis — the analysis is what's load-bearing during generation.

This is what a context-conditioned skill produces — a forced simulation of the writer's internal model, every invocation, from scratch. The protocol is the cost; the inhabitation is the payoff.

The intuitive alternative is fine-tuning a local open-source model on the same corpus. I tried this end-to-end. At ~100 paired examples, on a 7B base, across six runs spanning four training paradigms — basic SFT, structurally-distinct generics, two-stage continued-pretrain, two flavors of DPO — every variant produced drafts that were measurably worse than what this skill produces. The protocol approach wins at small-data scale, not the other way around.

## The five-part skill

**The plugin and your writing live in different places, deliberately.** The plugin
directory is replaced wholesale on every update. Anything of mine stored inside it
would be deleted the first time I update — corpus, annotations, years of accumulated
anti-corpus, gone silently. So:

```
<plugin>/                       # ours. replaced on every update.
├── skills/
│   ├── draft/SKILL.md          # the strict protocol      → /my-voice:draft
│   └── setup/SKILL.md          # first-run walkthrough    → /my-voice:setup
├── scripts/
│   ├── paths.py                # resolves plugin-vs-data, migrates old installs
│   ├── check_baseline.py       # gates the protocol; hashes corpus + annotations
│   ├── safety_net.py           # post-draft typography check + machine-checked hard rules
│   └── session_runtime.py      # resolves this session's per-session runtime dir
└── templates/                  # starter files, copied into your data dir by setup

~/.claude/my-voice/             # YOURS. never touched by an update.
├── annotations.md              # my own observations about how I write
├── anti-corpus.md              # examples of off-voice writing with diagnoses
├── hard-rules.md               # absolute do/don't constraints (override everything)
├── corpus/                     # 8–15 unedited writing samples
└── runtime/                    # generated artifacts (regenerated as needed)
    ├── voice_model.md          # SHARED across sessions — the inhabited writer-model
    ├── corpus_notes.md         # SHARED across sessions — per-piece reading notes
    ├── corpus_stats.json       # SHARED — cached corpus statistics
    └── sessions/
        └── <session-id>/       # per-session, isolated (keyed off $CLAUDE_CODE_SESSION_ID)
            ├── topic.md        # per-invocation topic intake
            ├── engagement.md   # per-invocation moves committed for this draft
            ├── ideas.md        # per-invocation flat list of ideas (rewrite case only)
            ├── critique.md     # per-invocation in-voice critique of own draft
            └── draft.md        # per-invocation scratch draft
```

Set `MY_VOICE_HOME` to put your writing somewhere else — a synced folder, say.
`python3 scripts/paths.py` prints wherever it resolved to.

Each piece does different work.

### `corpus/` — the source

Eight to fifteen pieces of my actual writing. Past Slack writeups, blog drafts, internal progress summaries, customer-facing comms, README sections I wrote myself, public LinkedIn About text, technical explainers, anything in my unedited voice from before I started using AI.

**Real text, unedited.** First drafts are valuable because they show my unmediated voice. Aim for variety: long-form, short-form, technical, persuasive, explanatory, opinionated. Don't curate too hard.

What counts: anything I wrote myself, even if the topic is a business profile or product description from years ago. Voice persists across topics — formal-mode-I and casual-mode-I both belong in the corpus. The protocol distinguishes prose-style pieces from formal-list pieces automatically when computing baseline statistics.

### `annotations.md` — my own observations

Specific, falsifiable observations about my writing, written like marginalia rather than rules. Not _"I am direct"_ but _"I open with the shortest version of my claim, often a memorable plain-English statement"_. Not _"I avoid corporate language"_ but _"I never use ALL CAPS, I prefer a single bold word for emphasis"_. Not _"I am informal"_ but _"I tend to format anything between parentheses as italic"_.

These are shortcuts to patterns the corpus would teach the model eventually. They're also dangerous if used as a checklist — the protocol below treats them as calibration, not as the source.

### `anti-corpus.md` — the boundary

Examples of writing that sounds like me on the surface but isn't, each with a 2-sentence diagnosis of what's off. Three or four to start, plus every off-voice draft the skill ever produces — every miss goes in here with a diagnosis, and the skill gets sharper.

Anti-corpus teaches the _boundary_ of my voice, not just the center. The corpus shows the destination; the anti-corpus shows where the cliff is.

### `hard-rules.md` — the absolutes

Everything above is _soft_. The corpus is a source the writer-model is triangulated from; annotations and anti-corpus calibrate that model. `hard-rules.md` is different: it is a list of absolute do/don't constraints that **override the writer-model and the corpus whenever they conflict** — even if the corpus shows me breaking one occasionally. "Never use em dashes" belongs here, not in annotations, because it must hold every time rather than nudge a probability.

Two kinds of rules live in the file. **Judgment rules** are prose do/don't lines the model reads at draft time and re-checks at critique time. **Machine-checked rules** sit inside `<!-- machine-checked-rules:start/end -->` markers as `` - `<regex>` <message> `` rows; `safety_net.py` parses that section, compiles each regex, and flags any match. Unlike the corpus, `hard-rules.md` is read fresh on every run and is _not_ hashed into the cached writer-model, so editing it takes effect immediately with no regeneration.

### `SKILL.md` — the protocol

This is the load-bearing piece, and it must be a strict ordered protocol — not a description, not a request. Each step must produce a written artifact in `runtime/` so the cognitive engagement is visible and verifiable, not assumed.

The 12-step protocol:

1. **Setup.** Run `scripts/session_runtime.py` to resolve and create this session's `runtime/sessions/<session-id>/` dir (call it `$SESSION_DIR`). Per-invocation artifacts go there; the shared corpus cache stays at the `runtime/` root.
2. **Baseline check.** Run `scripts/check_baseline.py`. If `BASELINE_OK`, skip to step 4. If `REGENERATE`, continue.
3. **Per-piece corpus reading.** Read every file in `corpus/` _one at a time_, no batching. For each file write a section in `runtime/corpus_notes.md` with a one-sentence summary plus 3–5 specific moves I make in that piece, with **quoted excerpts from the piece**. Quotes are non-optional — they are the proof the model actually read the piece rather than skimmed it.
4. **Synthesize the writer-model.** Build `runtime/voice_model.md`. First line stamps the corpus hash. Required sections, each with corpus citations: _opening moves, transition vocabulary, paragraph and sentence rhythm, what the writer reaches for, what the writer avoids, handling uncertainty, handling praise, handling criticism, closings_. This is the inhabited writer-model — the structured analysis of me-as-writer, computed from the corpus, written down so it lives in active reasoning when drafting begins.
5. **Read the calibrators and hard rules.** `annotations.md` end to end, then `anti-corpus.md` end to end — they calibrate the writer-model, they do not replace it. Then `hard-rules.md`: absolute do/don't constraints that override the writer-model and the corpus on any conflict, applied at draft time and re-checked at critique.
6. **Topic intake.** Write `$SESSION_DIR/topic.md`: one-sentence topic + goal, plus the 2–3 corpus pieces closest in _shape_ (not topic) to what's being written.
7. **Engagement note.** Write `$SESSION_DIR/engagement.md` — 5–7 specific moves drawn from `voice_model.md` that I commit to applying in this draft. This is the bridge that puts the writer-model into active reasoning before the first sentence is written.
8. **Abstract input to ideas** _(only when rewriting a provided input)_. Read the input file **once** and write `$SESSION_DIR/ideas.md` as a flat unordered list of the core ideas — no structure preserved, no section labels copied, no paragraph order copied, no bullet count preserved. After this step, **do not read the input file again**. The input's structural shape is a stronger pull on generation than the writer-model; the only way to break that pull is to forget the input and rebuild from `ideas.md` + `voice_model.md` from scratch.
9. **Draft.** Primary references in order: `voice_model.md`, `engagement.md`, `ideas.md` (if rewriting) or `topic.md` (if fresh), `anti-corpus.md`, then the corpus only when sampling specific phrasings. **The structural shape of the draft comes from `voice_model.md`, not from the input.** Do not open the input again during drafting. Do not consult `annotations.md` directly — that biases toward checklist application.
10. **In-voice critique.** Write `$SESSION_DIR/critique.md`. Re-read the draft as the writer. Strike the 3 worst sentences and explain why each fails, citing `voice_model.md` or `anti-corpus.md`. Be brutal. If I cannot find 3 sentences that sound like Claude pretending to be the writer, I didn't critique honestly.
11. **Revise.** Apply the critique. Rewrite the struck sentences. Iterate until the draft would survive its own critique pass.
12. **Safety net.** Run `scripts/safety_net.py "$SESSION_DIR/draft.md" [--input <input.md>]` on the draft. Pass `--input` when rewriting. If `NO_VIOLATIONS`, deliver. If violations, address each and re-run.

Steps 3, 4, 6, 7, 8, and 10 are the cognitive forcing function. Each one writes a file, and the act of writing is what puts the corpus and the substance into active reasoning instead of letting either sit in context as passive reference.

### `scripts/check_baseline.py` — the regeneration gate

Hashes `corpus/*.md` + `annotations.md`. Compares the hash against the one stamped at the top of `runtime/voice_model.md`. Prints `BASELINE_OK` or `REGENERATE: <reason>`.

When I edit the corpus or annotations, the next invocation's baseline check detects the mismatch and forces full regeneration of `voice_model.md` via steps 3–4. I don't have to ask for it; the protocol picks it up automatically.

### `scripts/safety_net.py` — the deterministic backstop

A mechanical typography + structural-drift check. Computes statistics from the corpus once _(cached)_ and checks each draft against them. Usage:

```
python3 scripts/safety_net.py <draft.md> [--input <input.md>]
```

Pass `--input` when rewriting a provided draft. The script then runs both classes of check.

**Rhythm (the layer that separates hardest):**
- **Clipped rhythm.** A composite: sentences short *and* uniform *and* never stretching past 35 words, all three at once. Measured against a real corpus, no single one of those separates — a floor tight enough to catch generated prose also rejects a quarter of the writer's own pieces, because a real range is wide and genuinely overlaps the model's. Requiring convergent evidence takes the catch rate from 32% to 74% at a higher corpus pass rate. Any one of short, uniform or flat is a style. All three together is a generator.

**Typography:**
- **Contraction floor and ceiling.** The floor catches prose with every contraction expanded, the canonical corporate-memo signal. The ceiling exists because a gate with only a floor is a one-way ratchet — every correction pushes the same direction, nothing pushes back, and the metric sails past the corpus unflagged. That is not hypothetical: it is what happened, at roughly twice the writer's own rate.
- **Heading density**, **list density**, **paragraph variance**, and **anti-tic regex matches** from `anti-corpus.md`.

**Structural drift (only with `--input`):**
- **Sequence retention.** How much of the input's word sequence survives, in order. The decisive one for rewrites: every section label can be replaced and the lists reshaped while two thirds of the original wording sits untouched underneath — a voice pass applied as paint over a skeleton that was never rebuilt.
- **Section-label mimicry** and **list-shape mimicry**.

**Window and formula (across recent drafts):**
- **Fading markers.** Signature punctuation is absent from a large minority of anyone's real pieces, so a per-draft floor fails genuine writing about as often as it catches drift. Across a window the signal is clean.
- **Formula.** Whether recent drafts have converged on one shape, by mean pairwise Burrows's Delta against the corpus's own spread. This is the failure invisible inside any single piece and obvious across ten — the one a reader means when they say the posts have started to feel samey.

The safety net is **not** a voice judge. Passing it does not mean the draft sounds like me. Failing it almost certainly means it doesn't. It catches catastrophes — typographic substitution masquerading as voice rewrite, and structural mimicry of the input — and lets the protocol handle the rest.

When I spot a new failure pattern in a draft, two things go in: a diagnosed entry in `anti-corpus.md` _(read at step 5)_, and an entry in `safety_net.py`'s `ANTI_TIC_PATTERNS` list _(catches it mechanically next time)_.

### `scripts/pick_exemplars.py` — which passages the model reads before drafting

Ranks the corpus by **shape** _(length, density, register)_ and never by subject, because matching on topic pulls the draft toward reusing the exemplar's content instead of its rhythm. Its `EVIDENCE DEPTH` block reports how much writing exists in the register being drafted, and warns when the target is longer than anything available — a corpus of short pieces cannot teach the back half of a long one, and what the model reaches for once the examples run out is its own default.

### `scripts/calibrate.py` — does the gate accept the writing it came from

Runs every band against the corpus that defined it. A gate that rejects its own corpus is not strict, it is broken, and the first few false alarms teach everybody to stop reading it. Every threshold in this repo was set by running this, not by picking a number that sounded about right.

### `scripts/harvest_sessions.py` — a corpus from what you have already typed

Most people cannot find 8–15 pieces of their own writing, and most people have far more than they think sitting in their Claude Code transcripts: months of unedited first-person prose written with no thought of how it would read. That is a better sample than anything anyone submits deliberately.

Only their own typed messages — tool results, pasted files, command output and agent-written prompts are excluded by structure rather than by eye, because agent-to-agent prompts read exactly like something the person would write. Heated messages are dropped, secrets are redacted, and mechanical typos are corrected while grammar and regional spelling are left alone. That last distinction matters: idiom and article use are not errors, they are the writer, and normalising them removes the very signal that separates their prose from generated prose.

Give harvested material its own genre. Instructing an agent is not the register an article gets written in.

### `corpus/genres.txt` — registers, and why pooling them breaks the thresholds

An optional map of globs to registers _(`article: wp-*.md`)_. Thresholds are then computed per register.

This matters more than it sounds. Measured on one real corpus, the `..` trailer runs 15.3 per 1k words in public prose and 1.3 in the same person's working notes. Same writer, different situation. Pooled, the floor for one collapses toward the other and stops catching the drift it exists to catch.

## How an invocation flows

The skill has three categories of files: inputs I set up once, cached artifacts that regenerate when the corpus changes, and per-invocation artifacts that overwrite on every draft. The protocol's hash gate decides whether the cached layer needs to rebuild before drafting.

```mermaid
flowchart TD
    User([User: rewrite X in my voice])
    User --> S1

    S1[Step 1: check_baseline.py — hash corpus and annotations]
    S1 --> Gate{voice_model.md hash matches?}

    Gate -->|REGENERATE| S2
    Gate -->|BASELINE_OK| S4

    S2[Step 2: read each corpus piece, quote excerpts into corpus_notes.md]:::regen
    S2 --> S3[Step 3: synthesize voice_model.md stamped with the corpus hash]:::regen
    S3 --> S4

    S4[Step 4: read annotations.md and anti-corpus.md]
    S4 --> S5[Step 5: topic intake into topic.md]:::perrun
    S5 --> S6[Step 6: engagement note into engagement.md]:::perrun
    S6 --> RewriteGate{rewriting an input?}
    RewriteGate -->|yes| S7[Step 7: extract ideas into ideas.md, then forget the input]:::perrun
    RewriteGate -->|no fresh draft| S8
    S7 --> S8[Step 8: draft from voice_model and ideas, structure comes from voice_model]:::perrun
    S8 --> S9[Step 9: in-voice critique into critique.md]:::perrun
    S9 --> S10[Step 10: revise per critique]:::perrun
    S10 --> S11[Step 11: run safety_net.py with --input when rewriting]
    S11 --> Safe{NO_VIOLATIONS?}
    Safe -->|no| S10
    Safe -->|yes| S12([Step 12: deliver final draft])

    classDef regen fill:#d1fae5,stroke:#059669,color:#000
    classDef perrun fill:#dbeafe,stroke:#2563eb,color:#000
```

**Green** = cached layer (regenerates only when corpus or annotations change).
**Blue** = per-invocation layer (overwrites every run).
Uncolored steps are reads or script calls.

### Inputs I set up once

Under `~/.claude/my-voice/` — mine, and never touched by a plugin update:

| File                        | Purpose                                          |
| --------------------------- | ------------------------------------------------ |
| `corpus/*.md`               | 8–15 unedited writing samples                    |
| `annotations.md`            | My own observations about how I write        |
| `anti-corpus.md`            | Off-voice examples + diagnoses (grows over time) |
| `hard-rules.md`             | Absolute do/don't constraints (override everything) |

`/my-voice:setup` creates that folder and copies starter versions of the three
markdown files into it. The corpus is mine to fill.

### Cached artifacts

Under `~/.claude/my-voice/runtime/`. Regenerated automatically when the protocol detects a hash or mtime mismatch:

| File                        | Lifetime                    | Regen trigger                            |
| --------------------------- | --------------------------- | ---------------------------------------- |
| `runtime/voice_model.md`    | Shared across sessions | Edit any corpus file or `annotations.md` |
| `runtime/corpus_notes.md`   | Shared across sessions | Same as above                            |
| `runtime/corpus_stats.json` | Shared across sessions | Edit any corpus file (mtime check)       |

The first line of `voice_model.md` stamps the corpus hash. `check_baseline.py` reads that line on every invocation and compares it against the current hash of `corpus/*.md` + `annotations.md`. If the hashes diverge, the protocol rebuilds the cached layer in steps 2–3 before continuing.

I don't trigger this manually. Edit a corpus file or annotations, run any voice draft, and the regeneration happens as part of the protocol. The first invocation after an edit takes ~30 seconds longer; subsequent ones reuse the cache.

### Per-invocation artifacts

Under `runtime/sessions/<session-id>/` (`$SESSION_DIR`). Overwritten on every draft within the same session:

| File                         | What it is                                                                                              |
| ---------------------------- | ------------------------------------------------------------------------------------------------------- |
| `$SESSION_DIR/topic.md`      | Topic + goal + closest-shape corpus pieces for this draft                                               |
| `$SESSION_DIR/engagement.md` | 5–7 specific moves committed for this draft                                                             |
| `$SESSION_DIR/ideas.md`      | Flat list of core ideas extracted from the input. Only created when rewriting; the input is never reopened after this file is written. |
| `$SESSION_DIR/critique.md`   | In-voice critique of the first draft, citing what fails and why                                         |
| `$SESSION_DIR/draft.md`      | Scratch draft for the critique + safety-net loop                                                        |

These exist for one reason: cognitive forcing. Reading the corpus is passive. Writing these files is active. The active engagement is what biases generation toward the writer-model instead of toward pretraining priors. They are visible by design — inspect them when a draft misses voice; the failure usually shows up in `engagement.md` or `critique.md` first.

## The honest ceiling

There is a real ceiling here, and it is further away than it looks. Be careful about which one you are actually hitting.

A context-conditioned skill cannot change the model's weights, so some gap will always remain, and the last stretch is an editing pass on phrasings that are not reproducible from any sample size. That much is true. What is not true is that every shortfall you notice is that ceiling. Measured against a real corpus, output from an earlier version of this skill was missing its writer's signature punctuation at roughly one-seventh of their own rate, running sentences a third shorter with half the variance, and using contractions at nearly twice their rate. None of that is a ceiling. All of it is measurable, none of it was being measured, and every one of those numbers moved once it was.

So before concluding you have hit the limit of the mechanism, run `calibrate.py`, look at what the gate is actually checking, and check whether the corpus contains anything in the register you are asking for. A ceiling is a claim about the mechanism. Most disappointment is a claim about the corpus.

The intuitive next move is to fine-tune a local open-source model on the same corpus. Do not skip the empirical check before going down that road: at ~100 paired examples, across four training paradigms on a 7B local base, every variant tried produced drafts that were worse than this skill produces, not better. Fine-tuning needs orders of magnitude more data than most individuals can produce before it pays back. For personal voice at individual data scale, better conditioning and better gates are where the remaining gains are.

## Composition with other commands

If I have slash commands or other skills that compose with this one _(e.g., a `linkedin-draft` command that produces fresh posts)_, those commands must compose `my-voice` and run its protocol. The forcing function only fires when the skill is invoked. Bypassing it — drafting directly without the protocol — produces typographic-substitution drafts that look like voice but aren't.

The simplest enforcement: in the composing command's prompt, require explicitly that the protocol's runtime artifacts (`engagement.md`, `critique.md`) exist after drafting. If they don't, the protocol was skipped.

**Do not let the composing command write the piece first.** The tempting shape is: draft it normally, then hand it to `my-voice` to rewrite. It reads as separation of concerns and it does not work. Measured across nineteen articles produced that way, 67% of the original word sequence survived verbatim and in order into the "voice-tuned" version, mean sentence length moved by one word, and the writer's signature trailer appeared exactly zero times in every single pre-voice draft. The abstraction step at step 7 exists to break that pull and cannot fully break it, because a finished draft is a far stronger anchor than any writer-model.

If a command needs grounding before drafting, have it produce a **fact sheet** — claims, numbers, links, sources — and let the voice protocol write the prose once, from that. A rewrite pass over finished text can only ever paint.

## Bootstrapping my corpus quickly

I probably have more material than I think:

- Internal progress summaries I've written. Strip confidential names if needed; voice persists.
- Public README sections I authored.
- Any blog posts, LinkedIn articles, or substack drafts I wrote myself.
- Slack threads where I explained something at length to a teammate.
- Customer-facing emails I composed.
- Anything I wrote _before AI existed_ — that's pure-I, no model contamination.

Aim for variety: long-form, short-form, technical, persuasive, explanatory, opinionated. Don't polish. The unedited version teaches better than the polished one.

```bash
mkdir -p ~/.claude/my-voice/corpus
# Copy in 8–15 .md files of my real writing.
# Don't curate hard — first drafts are valuable.
```

## Two things to be honest about

**Voice transfer has a ceiling, and it is further out than the first bad draft suggests.** Anyone promising an exact match — from a markdown skill or from a hobbyist-scale local fine-tune — is either wrong or selling something, so plan to do the editing pass myself. But do not accept a disappointing draft as the ceiling either: measure it first. Run `calibrate.py`, check what the gate is actually checking, and look at whether the corpus holds anything in the register being asked for.

**The skill keeps growing.** My voice now isn't my voice in two years. Add new pieces every few months — especially anything that landed well, or anything where I noticed myself writing differently than usual. Treat the skill as a living artifact, not a one-time setup. Every off-voice draft the skill produces is a sharpening opportunity for `anti-corpus.md` and `ANTI_TIC_PATTERNS`.

## Install

```
/plugin marketplace add abbaseya/claude-plugins
/plugin install my-voice@abbaseya
```

Then `/my-voice:setup`, which creates `~/.claude/my-voice/`, copies in the starter
files, and walks through what to put where.

### Already using this as a plain skill?

If it was installed the old way — the repo copied into `~/.claude/skills/my-voice/`
with the corpus inside it — **the plugin finds that and brings the writing across on
its first run.** Corpus, annotations, anti-corpus, hard rules and the runtime cache all
move to `~/.claude/my-voice/`.

It **copies rather than moves**, and never overwrites. The originals stay exactly where
they are; a corpus is often the only surviving copy of a piece of writing, and a tool
that relocates it unwatched has no way to be sorry. Once the drafts still sound right,
delete `~/.claude/skills/my-voice/` by hand — and do delete it, or two copies of the
skill will be registered at once.

## TL;DR for setup

1. Install the plugin and run `/my-voice:setup`.
2. Spend 30 minutes copying 8–15 real writing samples into `corpus/`. Don't curate.
3. Spend 60 minutes writing `annotations.md`. Read three of my own pieces and notice patterns. Falsifiable observations only.
4. Spend 20 minutes writing `anti-corpus.md` — three off-voice examples with two-sentence diagnoses each.
5. Run a real draft. Compare to what I'd write myself. Note specific things that miss. Add those to `anti-corpus.md` and extend `ANTI_TIC_PATTERNS` in the safety net.

The whole thing is maybe two hours of work for an artifact I'll use for years across every command and every piece of first-person writing. The skill gets sharper every time I correct it.

## How to use

```
rewrite <PATH_TO_INPUT_FILE> in my voice into <PATH_TO_OUTPUT_FILE>
```

That's it. The protocol does the rest. Edit the last 10–15% myself.

## Development

```bash
bash bin/run-tests.sh     # leak gate, corpus-not-shipped check, 35 tests
ruff check .
```

CI runs the same script on every pull request, on Ubuntu and macOS. Nothing is pushed
to `main` directly.

The suite is built around the two guarantees that matter: **nothing a user owns is
stored inside the plugin** (an update would delete it), and **a pre-plugin install is
migrated by copy with the originals untouched**. Plus the baseline gate forcing a
rebuild when the corpus changes, the coverage gate rejecting notes without verbatim
quotes, and the safety net catching an expanded-contractions draft.

## License

MIT — see [LICENSE](LICENSE).
