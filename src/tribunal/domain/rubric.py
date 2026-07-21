"""Rubric domain model.

A :class:`Rubric` is a machine-readable specification of *how* a document is
scored: the atomic scoring units, their weights, the six-grade band table, and
the qualification (veto) gates that can zero out an entire project.

The design principle that runs through this package: **the rubric is data, not
code**. Reviewers (human or LLM) only ever pick a *grade* or *tier* for a unit;
turning that into a number, summing units, applying weights, and enforcing caps
is deterministic and lives in :mod:`tribunal.validation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Grade(str, Enum):
    """Six-grade ordinal scale, best to worst."""

    OUTSTANDING = "outstanding"
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    PASS = "pass"
    FAIL = "fail"

    @property
    def rank(self) -> int:
        """0 = best (OUTSTANDING) ... 5 = worst (FAIL)."""
        return _GRADE_ORDER.index(self)


_GRADE_ORDER = [
    Grade.OUTSTANDING,
    Grade.EXCELLENT,
    Grade.GOOD,
    Grade.FAIR,
    Grade.PASS,
    Grade.FAIL,
]


class UnitType(str, Enum):
    """How a scoring unit is graded."""

    #: Standard six-grade band scoring.
    GRADE_BAND = "grade_band"
    #: A qualifying base score plus a tiered top-up (e.g. base 40 + up to 20).
    BASE_PLUS_TIER = "base_plus_tier"
    #: A pass/fail qualification gate that can only take two values (max or 0).
    QUALIFICATION = "qualification"


@dataclass(frozen=True)
class ScoringUnit:
    """An atomic, independently-scored line item.

    Attributes
    ----------
    key:
        Stable identifier, unique within the rubric.
    project:
        The project this unit rolls up into. All units sharing a project are
        summed to form the project score.
    label:
        Human-readable name.
    max_score:
        Maximum attainable points for this unit.
    unit_type:
        See :class:`UnitType`.
    transmission_cap:
        When the unit's project trips a transmission trigger (see
        :class:`TransmissionRule`), this unit's score is capped at this value.
        ``None`` means the unit is unaffected by transmission.
    """

    key: str
    project: str
    label: str
    max_score: float
    unit_type: UnitType = UnitType.GRADE_BAND
    transmission_cap: Optional[float] = None


@dataclass(frozen=True)
class VetoRule:
    """A qualification gate: fail it and the whole project scores zero.

    This models the two "one-vote-veto" mechanisms from the reference
    application:

    * a *research-qualification* veto (project owner / seniority / in-window),
    * an *authorship-role* veto (the candidate must be first author / presenter).

    ``project`` names the project zeroed out. ``conditions`` are the human-facing
    qualification statements the LLM assessors must confirm from evidence.
    """

    key: str
    project: str
    description: str
    conditions: tuple[str, ...]
    #: If the project is a scored "exam item", failing zeros the whole project.
    #: If it is only a "bonus item", failing zeros the bonus. Purely
    #: informational here; the validator applies the numeric consequence.
    zeroes_bonus_only: bool = False


@dataclass(frozen=True)
class TransmissionRule:
    """When a project's *anchor* unit fails, cap sibling units.

    In the reference rubric, if a mandatory project's anchor line item is judged
    unusable (e.g. a workshop that never really operated), the remaining units
    lose their evidentiary basis and are capped so the project total naturally
    falls below the pass mark — rather than hard-capping the project total after
    the fact, which would contradict "project total = sum of units".
    """

    project: str
    trigger_unit: str
    #: unit_key -> cap value
    caps: dict[str, float]


@dataclass(frozen=True)
class Rubric:
    """A complete scoring specification."""

    name: str
    units: tuple[ScoringUnit, ...]
    #: project -> weight (should sum to 1.0 across scored projects)
    weights: dict[str, float] = field(default_factory=dict)
    veto_rules: tuple[VetoRule, ...] = ()
    transmission_rules: tuple[TransmissionRule, ...] = ()
    bonus_cap: float = 15.0
    pass_mark: float = 60.0

    # -- lookups ---------------------------------------------------------

    def unit(self, key: str) -> ScoringUnit:
        for u in self.units:
            if u.key == key:
                return u
        raise KeyError(f"no scoring unit {key!r} in rubric {self.name!r}")

    def units_for(self, project: str) -> list[ScoringUnit]:
        return [u for u in self.units if u.project == project]

    @property
    def projects(self) -> list[str]:
        seen: list[str] = []
        for u in self.units:
            if u.project not in seen:
                seen.append(u.project)
        return seen

    def veto_for(self, project: str) -> Optional[VetoRule]:
        for v in self.veto_rules:
            if v.project == project:
                return v
        return None

    def transmission_for(self, project: str) -> Optional[TransmissionRule]:
        for t in self.transmission_rules:
            if t.project == project:
                return t
        return None

    def validate_self(self) -> list[str]:
        """Return a list of structural problems (empty == healthy)."""
        problems: list[str] = []
        keys = [u.key for u in self.units]
        if len(keys) != len(set(keys)):
            problems.append("duplicate unit keys")
        weight_sum = sum(self.weights.values())
        if self.weights and abs(weight_sum - 1.0) > 1e-6:
            problems.append(f"weights sum to {weight_sum}, expected 1.0")
        for t in self.transmission_rules:
            if t.trigger_unit not in keys:
                problems.append(f"transmission trigger {t.trigger_unit!r} missing")
        return problems
