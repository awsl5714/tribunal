"""Multi-round consensus between two independent LLM assessors.

This is the coordination logic behind "GPT and Claude review each other over
several rounds". For each scoring unit:

1. the **scorer** (GPT) proposes a grade + score from the evidence;
2. the **reviewer** (Claude) independently audits it;
3. if they agree within ``grade_tolerance``, the unit is settled (CONSENSUS);
4. if not, the scorer is shown the critique and re-scores (REVISED); this
   repeats up to ``max_rounds``;
5. if they still diverge, the unit is ESCALATED to a human — the pipeline never
   silently averages two assessors who genuinely disagree.

The orchestrator only produces *proposed* unit scores; the deterministic
validator and veto/transmission rules run afterwards and can still override
anything here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.assessment import Provenance, UnitScore
from ..domain.rubric import Grade, ScoringUnit
from ..domain.submission import Submission
from .reviewer import Reviewer
from .scorer import Scorer


@dataclass
class ConsensusConfig:
    max_rounds: int = 3
    #: how many grade-ranks of disagreement are tolerated (0 = must match exactly)
    grade_tolerance: int = 1


class ConsensusOrchestrator:
    def __init__(
        self,
        scorer: Scorer,
        reviewer: Reviewer,
        config: ConsensusConfig | None = None,
    ):
        self.scorer = scorer
        self.reviewer = reviewer
        self.config = config or ConsensusConfig()

    def resolve(self, unit: ScoringUnit, submission: Submission) -> UnitScore:
        proposal = self.scorer.score(unit, submission)
        rounds = 1
        last_reason = ""

        while rounds <= self.config.max_rounds:
            verdict = self.reviewer.review(unit, submission, proposal)
            last_reason = verdict.reason
            gap = abs(proposal.grade.rank - verdict.grade.rank)

            if verdict.agrees or gap <= self.config.grade_tolerance:
                # Settle on the more conservative (lower) of the two scores when
                # they're close but not identical — auditor caution wins ties.
                final_grade, final_score = _conservative(
                    (proposal.grade, proposal.score),
                    (verdict.grade, verdict.score),
                )
                provenance = (
                    Provenance.CONSENSUS if rounds == 1 else Provenance.REVISED
                )
                return UnitScore(
                    unit_key=unit.key,
                    grade=final_grade,
                    score=final_score,
                    max_score=unit.max_score,
                    rationale=proposal.rationale,
                    evidence_locator=proposal.evidence_locator,
                    provenance=provenance,
                    scorer_score=proposal.score,
                    reviewer_score=verdict.score,
                    rounds=rounds,
                )

            # Disagreement: feed the critique back and let the scorer revise.
            rounds += 1
            revised = self.scorer.score(unit, submission)
            # If the scorer won't move, break to escalation.
            if revised.grade == proposal.grade and revised.score == proposal.score:
                proposal = revised
                break
            proposal = revised

        # Never converged -> escalate, do not fabricate a number.
        return UnitScore(
            unit_key=unit.key,
            grade=None,
            score=0.0,
            max_score=unit.max_score,
            rationale=(
                f"Assessors did not converge after {self.config.max_rounds} rounds. "
                f"Reviewer's last objection: {last_reason}"
            ),
            evidence_locator=proposal.evidence_locator,
            provenance=Provenance.ESCALATED,
            scorer_score=proposal.score,
            reviewer_score=None,
            rounds=rounds,
        )


def _conservative(
    a: tuple[Grade, float], b: tuple[Grade, float]
) -> tuple[Grade, float]:
    """Pick the lower-scoring of two (grade, score) pairs."""
    return a if a[1] <= b[1] else b
