# corpus/ — drop your own writing here

This directory holds 8 to 15 pieces of your own real writing, one per file, in Markdown.

## What to drop in

- Past blog posts you wrote yourself
- LinkedIn writeups, internal Slack threads where you explained something at length
- Customer-facing emails you composed
- README sections you authored
- Anything you wrote yourself **before AI existed** — pure-you, no model contamination

## How many

8 to 15 pieces. Fewer than 8 and the writer-model has too little to triangulate; more than 15 and the protocol gets slower without producing meaningfully better drafts.

## What kind

Mix lengths and shapes aggressively: long-form articles, short Slack messages, persuasive pieces, technical explainers, opinionated takes, customer-facing comms. Variety is the point — voice persists across registers, and the skill learns the boundaries by seeing how you write in each.

## What NOT to do

- Don't curate too hard. First drafts teach the skill better than polished ones.
- Don't include AI-assisted writing — the model will pattern-match itself.
- Don't include third-party content you've quoted (e.g., long paragraphs from someone else's article).

## Naming

Number-prefixed names help the protocol cite them cleanly: `01-launch-announcement.md`, `02-onboarding-email.md`, `03-talk-recap.md`. The numbering isn't load-bearing — pick any scheme that works for you.

## After you drop files here

The next time you invoke the skill, `check_baseline.py` will detect the corpus change and the protocol will regenerate the writer-model automatically. Adds roughly 30 seconds to that one invocation; subsequent invocations reuse the cached writer-model.
