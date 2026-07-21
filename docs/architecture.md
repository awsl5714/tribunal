# Architecture

## The core idea: separate judgement from computation

An LLM is good at reading evidence and forming a qualitative judgement ("this
research report is *good*, not *excellent*, because the methodology section is
thin"). It is unreliable at the mechanical work around that judgement: keeping a
number inside its grade band, summing sub-scores, applying weights, enforcing
caps, and deciding when a result is safe to finalise.

Tribunal draws a hard line between the two:

| Concern | Who does it | Where |
|---|---|---|
| Grade a scoring unit from evidence | LLM assessors | `agents/` |
| Grade → number, sum, weight, caps | deterministic code | `rubric/`, `pipeline/`, `validation/` |
| Qualification gates (veto) | deterministic code | `validation/rules.py` |
| Decide a case is finalisable | deterministic code + HITL | `validation/`, `hitl/` |

Everything below the first row is a pure function of the assessors' grades, so
the same submission + same grades always yields the same numbers.

## The pipeline, step by step

`pipeline/runner.py::ReviewPipeline.run` executes six stages in order.

### 1. Consensus (`agents/orchestrator.py`)

For each scoring unit:

1. the **scorer** proposes `{grade, score, rationale, evidence_locator}`;
2. the deterministic guard in `Scorer.score` snaps the number into the grade's
   legal band if the model emitted an inconsistent pair;
3. the **reviewer** independently re-derives a grade and returns
   `agree` / `challenge`;
4. within `grade_tolerance` ranks → settle on the **conservative** (lower)
   score; otherwise the scorer re-scores with the critique in view;
5. after `max_rounds` without convergence → `ESCALATED` (grade `None`, held).

The two roles map onto two different model families in production (GPT scores,
Claude reviews) precisely so the audit is *independent* — a second pass from the
same model tends to agree with itself.

### 2. Veto (`validation/rules.py::apply_veto`)

Qualification gates are boolean facts about the submission ("is the candidate
the project owner?", "is the candidate the first author?"). When a gate fails,
**every unit in that project is zeroed** and the project is marked `VETOED`.
This is the generalisation of the two one-vote-veto rules in the source rubric.

### 3. Transmission (`validation/rules.py::apply_transmission`)

Some mandatory projects have an *anchor* unit. If the anchor scores zero (its
basic condition is unmet) the sibling units lose their evidentiary basis, so
they are **capped** at fail-tier ceilings. The caps are chosen so the project
total lands below the pass mark as a genuine sum — never by clamping the total
after the fact, which would violate "total = Σ units".

### 4. Rollup

Units → project totals → weighted (`total × weight`) → base total. Bonus items
are scored separately and capped. `final = base + bonus`.

### 5. Validate (`validation/validator.py`)

The machine checklist (`B1…B17`) runs over the finished assessment: band
membership, `Σ units == total`, `total ≤ max`, vetoed ⇒ 0, transmitted ⇒
`< pass_mark`, weighted arithmetic, bonus cap, `final == base + bonus`, and an
escalation flag. Any `ERROR` marks the result "not final".

### 6. Escalate (`hitl/escalation.py`)

Non-convergence, fired vetoes, and surviving errors produce an
`EscalationTicket` with the full context a human needs to adjudicate.

## Extending

- **New backend** — implement `LLMClient.complete`; pass it to `Scorer` /
  `Reviewer`.
- **New rubric** — edit YAML; the loader validates structure (weights sum to 1,
  transmission triggers exist, unique keys).
- **New check** — add a `Finding` in `Validator.check`; it is picked up
  everywhere the validator runs.
- **New gate** — add a `VetoRule` in YAML and supply its boolean via
  `GateEvaluator`.
