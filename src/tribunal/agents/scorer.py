"""The scoring agent — proposes an initial grade for a unit (GPT in production)."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.rubric import Grade, ScoringUnit
from ..domain.submission import Submission
from ..rubric.grade_bands import clamp_to_band, is_legal
from .llm_client import LLMClient
from .prompts import SCORER_SYSTEM, scorer_prompt


@dataclass
class ScoreProposal:
    grade: Grade
    score: float
    rationale: str
    evidence_locator: str
    confidence: float
    corrected: bool = False  # True if the model's number was snapped into its band


class Scorer:
    def __init__(self, client: LLMClient):
        self.client = client

    def score(self, unit: ScoringUnit, submission: Submission) -> ScoreProposal:
        reply = self.client.complete(
            SCORER_SYSTEM, scorer_prompt(unit, submission), temperature=0.0
        )
        data = self.client.extract_json(reply.text)
        grade = Grade(data["grade"])
        score = float(data["score"])

        # Deterministic guard: the model's grade is authoritative, its number is
        # not. If they disagree, snap the number into the grade's legal band.
        corrected = False
        if not is_legal(unit.max_score, grade, score):
            score = clamp_to_band(unit.max_score, grade, score)
            corrected = True

        return ScoreProposal(
            grade=grade,
            score=score,
            rationale=str(data.get("rationale", "")),
            evidence_locator=str(data.get("evidence_locator", "")),
            confidence=float(data.get("confidence", 0.5)),
            corrected=corrected,
        )
