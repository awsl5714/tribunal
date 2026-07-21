# Design decisions

Short rationale for the choices that aren't obvious from the code.

## Why two different model families, not two temperatures of one

An independent audit needs an assessor that doesn't share the first one's
blind spots. Two samples from the same model at different temperatures are
correlated — they tend to make the same mistakes and rationalise the same way.
Using GPT as the scorer and Claude as the reviewer gives genuinely independent
judgement, which is the whole point of the review step. The `LLMClient`
abstraction keeps this a configuration choice, not a hard dependency.

## Why the model never sees a number it must respect

`Scorer.score` and `Reviewer.review` both re-derive the *number* from the
*grade* using the deterministic band engine, discarding any out-of-band number
the model emitted (and flagging the correction). This means a model can never
"win" an argument by asserting a number that isn't legal for the grade it chose.
It also collapses the reference rubric's ten separate band tables into one
15-line function — the single source of truth for grade ↔ score.

## Why transmission caps instead of clamping the project total

The naive way to make a failed project score below 60 is to compute the total
normally and then `min(total, 59.9)`. That contradicts the invariant "project
total = sum of its units" — the printed sub-scores no longer add up to the
printed total, which an auditor will (rightly) reject. Transmission instead
lowers the *ceilings of the affected units*, so the sum falls below the pass
mark on its own and every number on the page reconciles.

## Why escalate instead of average

Averaging two assessors who are one grade apart is fine — that's the
`grade_tolerance` path, and we take the conservative side. Averaging two
assessors who are three grades apart hides a real disagreement behind a
plausible-looking number. Those cases are exactly the ones a human should see,
so the pipeline refuses to invent a score for them.

## Why the rubric is YAML, not Python

Scoring policy changes far more often than pipeline code, and the people who
own the policy are domain experts, not engineers. A declarative rubric with a
validating loader lets them change weights, bands, gates, and caps without a
code review, while `Rubric.validate_self()` still catches structural mistakes
(weights that don't sum to 1, a transmission trigger that doesn't exist).

## Why ship only synthetic data

The source project handled real individuals' assessment portfolios. None of
that is in this repository. The example rubric is generalised and anonymised;
the two example submissions are hand-written synthetic cases chosen to exercise
the happy path and the veto path. `.gitignore` blocks stray `.xlsx` files so
real data can't be committed by accident.
