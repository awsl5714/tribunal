"""Assessment outputs: per-unit scores, project rollups, and the final result."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .rubric import Grade


class Provenance(str, Enum):
    """How a unit's final score was arrived at."""

    CONSENSUS = "consensus"          # both models agreed within tolerance
    REVISED = "revised"              # scorer revised after reviewer challenge
    ARBITRATED = "arbitrated"        # deterministic rule overrode the models
    VETOED = "vetoed"                # zeroed by a qualification veto
    TRANSMITTED = "transmitted"      # capped by a transmission rule
    ESCALATED = "escalated"          # models never converged -> human needed


@dataclass
class UnitScore:
    """A single unit's outcome after the whole pipeline has run."""

    unit_key: str
    grade: Optional[Grade]
    score: float
    max_score: float
    rationale: str
    evidence_locator: str = ""
    provenance: Provenance = Provenance.CONSENSUS
    #: populated when the two assessors disagreed
    scorer_score: Optional[float] = None
    reviewer_score: Optional[float] = None
    rounds: int = 1

    @property
    def disagreement(self) -> float:
        if self.scorer_score is None or self.reviewer_score is None:
            return 0.0
        return abs(self.scorer_score - self.reviewer_score)


@dataclass
class ProjectScore:
    project: str
    total: float
    weight: float
    weighted: float
    units: list[UnitScore] = field(default_factory=list)
    vetoed: bool = False
    transmitted: bool = False
    note: str = ""


@dataclass
class Assessment:
    """The complete result for one submission."""

    candidate_id: str
    candidate_name: str
    projects: list[ProjectScore] = field(default_factory=list)
    bonus_total: float = 0.0
    base_total: float = 0.0
    final_total: float = 0.0
    escalations: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    #: set True when the numbers must not be treated as final
    needs_human_review: bool = False

    def project(self, name: str) -> Optional[ProjectScore]:
        for p in self.projects:
            if p.project == name:
                return p
        return None
