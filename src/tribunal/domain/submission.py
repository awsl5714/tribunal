"""The thing under review: a submission and its extracted evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Evidence:
    """A located piece of supporting material.

    Precise localisation is a hard requirement in the reference application: a
    score is only defensible if it points at *where* in the source it came from.
    """

    source: str          # file name
    locator: str         # page / cell / figure reference, e.g. "p.24-45"
    excerpt: str         # the quoted / summarised content
    kind: str = "general"  # "qualification" (gates a project) | "general"


@dataclass(frozen=True)
class Submission:
    """A candidate's full submission for one review."""

    candidate_id: str
    candidate_name: str
    #: The project chosen as the scored elective (weighted), if any.
    elective_exam_project: Optional[str] = None
    #: Projects declared only as bonus items.
    elective_bonus_projects: tuple[str, ...] = ()
    #: unit_key -> list of evidence supporting that unit
    evidence: dict[str, list[Evidence]] = field(default_factory=dict)
    #: free-form metadata (training window, source files, ...)
    meta: dict[str, str] = field(default_factory=dict)

    def evidence_for(self, unit_key: str) -> list[Evidence]:
        return self.evidence.get(unit_key, [])
