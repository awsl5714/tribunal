"""The reviewing agent — independently audits a proposed score (Claude in production)."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.rubric import Grade, ScoringUnit
from ..domain.submission import Submission
from ..rubric.grade_bands import clamp_to_band, is_legal
from .llm_client import LLMClient
from .prompts import REVIEWER_SYSTEM, reviewer_prompt
from .scorer import ScoreProposal


@dataclass
class ReviewVerdict:
    agrees: bool
    grade: Grade
    score: float
    reason: str
    confidence: float


class Reviewer:
    def __init__(self, client: LLMClient):
        self.client = client

    def review(
        self, unit: ScoringUnit, submission: Submission, proposal: ScoreProposal
    ) -> ReviewVerdict:
        reply = self.client.complete(
            REVIEWER_SYSTEM,
            reviewer_prompt(
                unit,
                submission,
                proposal.grade.value,
                proposal.score,
                proposal.rationale,
            ),
            temperature=0.0,
        )
        data = self.client.extract_json(reply.text)
        agrees = str(data.get("verdict", "agree")).lower() == "agree"

        # When the reviewer agrees it may not restate a grade; fall back to the
        # scorer's. When it challenges, take its own grade/score.
        grade = Grade(data["grade"]) if data.get("grade") else proposal.grade
        score = float(data["score"]) if data.get("score") is not None else proposal.score
        if not is_legal(unit.max_score, grade, score):
            score = clamp_to_band(unit.max_score, grade, score)

        return ReviewVerdict(
            agrees=agrees,
            grade=grade,
            score=score,
            reason=str(data.get("reason", "")),
            confidence=float(data.get("confidence", 0.5)),
        )
