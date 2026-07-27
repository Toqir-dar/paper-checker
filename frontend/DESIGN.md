# Markup — frontend design notes

The direction is **editorial paper**: it should feel like marking on paper, not like a SaaS
dashboard. Everything below lives in `src/styles.css` as CSS custom properties — change a token
there and the whole app follows.

## The rules

- **One accent.** `--mark` (#b23a2e) is a red pencil. It marks things that need a human: flags,
  overridden scores, the active nav item, hover chevrons. Nothing decorative is ever red.
- **No rounded corners, no drop shadows.** Structure comes from hairline rules (`--rule`) and
  2px ink rules under section headings. `.card`/`.panel` are flat bordered blocks.
- **Serif for numbers and headings** (`--font-display`, Instrument Serif), sans for UI
  (IBM Plex Sans), **mono for data and labels** (IBM Plex Mono). Uppercase mono `.label` /
  `.eyebrow` is the only small-caps device.
- **Ruled lists, not tables.** `.ruled` + `.ruled__row` is the primary layout for any collection.
  `.table` is still defined for anything that genuinely needs a grid.
- Body copy is warm off-white on near-black; whites stay under 0.02 chroma.

## Screens

| Route | Component | Purpose |
| --- | --- | --- |
| `/today` | `features/dashboard` | The review queue — what's waiting on you, oldest first. Built from `GET /answer-keys` + `GET /submissions?answer_key_id=` only. |
| `/answer-keys` | `answer-key-list` | Library of keys. |
| `/answer-keys/upload` | `answer-key-upload` | Photograph a marking scheme; vision model extracts it. |
| `/answer-keys/new` | `answer-key-form` | Manual entry. |
| `/answer-keys/:id/submissions` | `submission-list` | The stack for one key. |
| `/submissions/:id/report` | `grade-report` | **The review screen** — the core of the product. |

## The review screen

This is where the design earns its keep. Three commitments, all from the questionnaire:

1. **The model's reasoning is always inline.** `feedback` renders as a margin-ruled quote under
   each question, beside a two-up split showing *They wrote* vs *The key says* (fetched from
   `GET /submissions/:id` and `GET /answer-keys/:id` — no new endpoints).
2. **Low confidence is flagged.** Confidence is *derived*, not invented:
   - `graded_by === 'mcq'` → matched exactly, no flag possible.
   - `detected_label` disagrees with `question_id` → `page says Q5`.
   - a model-judged answer with partial credit → `partial credit`.
   `only flagged (n)` filters to just those.
3. **Scores are overridable in place.** The `.stepper` writes to a local `overrides` signal keyed
   by `question_id`; the running total, percentage and meter recompute from it, and any changed
   question shows `you set this · model said 2 / 4` with an undo. Overrides reset on re-grade.

`Confirm this paper` is currently a no-op button — wire it to whatever persistence you add for
teacher-approved scores (the overrides map is the payload you want).

## Not yet wired

- Confirmed/awaiting status per paper needs backend support; the queue currently lists every
  submission rather than only unreviewed ones.
- Class average and score spread need a per-key aggregate endpoint, so the class overview shows
  paper counts instead.
