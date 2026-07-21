"""Prompt templates for the scorer and reviewer roles.

These are deliberately terse; the real rubric text is injected at run time. The
shape mirrors the production prompts: a rule-bound system message that forbids
inventing facts, and a structured JSON output contract that the deterministic
layer can validate.
"""

from __future__ import annotations

from ..domain.rubric import ScoringUnit
from ..domain.submission import Evidence, Submission

SCORER_SYSTEM = """\
You are a rigorous document assessor. You score ONE scoring unit at a time \
against a fixed rubric. Rules you must obey:
- Judge ONLY from the evidence provided. Never invent facts or assume unstated ones.
- Output a six-grade label (outstanding/excellent/good/fair/pass/fail) and a score.
- If there is no evidence for the unit, the grade is "fail" and the score is 0.
- Cite the evidence locator you relied on.
Respond with a single JSON object: \
{"grade","score","rationale","evidence_locator","confidence"}.
"""

REVIEWER_SYSTEM = """\
You are an independent second assessor auditing another model's score for ONE \
scoring unit. You did not see the first score until now. Rules:
- Re-derive your own grade from the evidence, then compare.
- If you agree within one grade, set "verdict":"agree".
- If you disagree, set "verdict":"challenge" and give your grade, score and the \
specific reason (missing evidence, wrong grade band, over-credit, etc.).
- Never rubber-stamp: agreement must be justified from the evidence.
Respond with a single JSON object: \
{"verdict","grade","score","reason","confidence"}.
"""


def _render_evidence(evidence: list[Evidence]) -> str:
    if not evidence:
        return "(no evidence attached to this unit)"
    return "\n".join(
        f"- [{e.source} {e.locator}] ({e.kind}) {e.excerpt}" for e in evidence
    )


def scorer_prompt(unit: ScoringUnit, submission: Submission) -> str:
    ev = submission.evidence_for(unit.key)
    return (
        f"Candidate: {submission.candidate_name} ({submission.candidate_id})\n"
        f"Scoring unit: {unit.label}\n"
        f"unit_key = {unit.key}\n"
        f"max_score = {unit.max_score}\n"
        f"unit_type = {unit.unit_type.value}\n\n"
        f"Evidence:\n{_render_evidence(ev)}\n\n"
        f"Score this unit."
    )


def reviewer_prompt(
    unit: ScoringUnit,
    submission: Submission,
    scorer_grade: str,
    scorer_score: float,
    scorer_rationale: str,
) -> str:
    ev = submission.evidence_for(unit.key)
    return (
        f"Candidate: {submission.candidate_name} ({submission.candidate_id})\n"
        f"Scoring unit: {unit.label}\n"
        f"unit_key = {unit.key}\n"
        f"max_score = {unit.max_score}\n\n"
        f"Evidence:\n{_render_evidence(ev)}\n\n"
        f"First assessor said: grade={scorer_grade}, score={scorer_score}\n"
        f'First assessor rationale: "{scorer_rationale}"\n\n'
        f"Audit this score."
    )
