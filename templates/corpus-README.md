# corpus/ — drop my own writing here

This directory holds 8 to 15 pieces of my own real writing, one per file, in Markdown.

## What to drop in

- Past blog posts I wrote myself
- LinkedIn writeups, internal Slack threads where I explained something at length
- Customer-facing emails I composed
- README sections I authored
- Anything I wrote myself **before AI existed** — pure-I, no model contamination

## How many

8 to 15 pieces. Fewer than 8 and the writer-model has too little to triangulate; more than 15 and the protocol gets slower without producing meaningfully better drafts.

## What kind

Mix lengths and shapes aggressively: long-form articles, short Slack messages, persuasive pieces, technical explainers, opinionated takes, customer-facing comms. Variety is the point — voice persists across registers, and the skill learns the boundaries by seeing how I write in each.

## What NOT to do

- Don't curate too hard. First drafts teach the skill better than polished ones.
- Don't include AI-assisted writing — the model will pattern-match itself.
- Don't include third-party content I've quoted (e.g., long paragraphs from someone else's article).

## Naming

Number-prefixed names help the protocol cite them cleanly: `01-launch-announcement.md`, `02-onboarding-email.md`, `03-talk-recap.md`. The numbering isn't load-bearing — pick any scheme that works for me.

## After I drop files here

The next time I invoke the skill, `check_baseline.py` will detect the corpus change and the protocol will regenerate the writer-model automatically. Adds roughly 30 seconds to that one invocation; subsequent invocations reuse the cached writer-model.
