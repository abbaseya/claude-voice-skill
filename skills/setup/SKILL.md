---
name: setup
description: Set up my-voice — create the writing folder, copy in the starter files, and explain what to put where. Run once before the first draft.
disable-model-invocation: true
---

# my-voice setup

Get the user to a working corpus. **Assume they have never opened a terminal.** Ask one
thing at a time, and never show them a file path they have to type.

## 1. Check what already exists

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/paths.py"
```

Three possible states:

- **`configured: yes`** — they already have a corpus. Tell them how many pieces, and ask
  whether they want to add more or leave it. Do not re-run setup over a working install.
- **A `legacy:` line appears** — they installed this before it was a plugin, and their
  writing is in the old location. Say so plainly, then run
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_baseline.py"`, which copies it across
  automatically and reports what it moved. **The originals are not deleted** — tell them
  that, and that they can remove the old folder once they are happy.
- **`NO_CORPUS` and no legacy** — a fresh install. Continue below.

## 2. Create the folder and copy the starters

Create the data home printed by `paths.py` and copy these from
`${CLAUDE_PLUGIN_ROOT}/templates/` into it:

| Template | Goes to | What it is |
|---|---|---|
| `annotations.md` | `annotations.md` | Their own observations about how they write |
| `anti-corpus.md` | `anti-corpus.md` | Off-voice examples with diagnoses |
| `hard-rules.md` | `hard-rules.md` | Absolute do/don't rules |
| `corpus-README.md` | `corpus/README.md` | Instructions for the corpus folder |

Never overwrite a file that already exists.

## 3. Explain the corpus, then help them fill it

This is the part that decides whether the skill works at all, so do not rush it.

Tell them: **8 to 15 pieces of their own writing, one file each, unedited.** Then help
them find some — most people have far more than they think:

- Blog posts or newsletters they wrote themselves
- Long Slack or email replies where they explained something properly
- README sections, project write-ups, proposals
- Anything written **before they started using AI** — that is the purest sample

Two things to say explicitly, because both are counter-intuitive:

- **Do not polish.** First drafts teach the model more than tidied ones.
- **Do not include AI-assisted writing.** The model will pattern-match itself, and the
  voice collapses toward the default it was already going to produce.

Offer to copy files in for them if they point at a folder.

## 4. Confirm it is ready

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_baseline.py"
```

Expect `REGENERATE` on a fresh corpus — that is correct, it means the writer-model has
not been built yet and the first draft will build it. `NO_CORPUS` means the corpus folder
is still empty; say so rather than declaring success.

## 5. Set expectations honestly

Before they try it, tell them two things:

- **The ceiling is around 85%.** Drafts will sound like them, and the last stretch is
  their own editing pass. Anyone promising more is wrong.
- **The first draft after any corpus change is slower**, because the writer-model
  rebuilds. After that it is cached.

Then offer to write something: *"Want to try it on a real post?"*
