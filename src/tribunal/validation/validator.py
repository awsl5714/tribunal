"""The deterministic post-check suite.

Everything an LLM should *not* be trusted to do: range membership, summation,
weighting, cap enforcement, veto/transmission consistency. Each check returns a
structured :class:`Finding`; the pipeline treats any ``ERROR`` finding as a
reason to hold the result for human review.

This is the codified version of the reference project's "Appendix B" machine
checklist.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..domain.assessment import Assessment, Provenance
from ..domain.rubric import Rubric
from ..rubric.grade_bands import is_legal


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Finding:
    code: str
    severity: Severity
    message: str


class Validator:
    """Runs all deterministic checks over a finished :class:`Assessment`."""

    def __init__(self, rubric: Rubric):
        self.rubric = rubric

    def check(self, assessment: Assessment) -> list[Finding]:
        findings: list[Finding] = []
        f = findings.append

        for proj in assessment.projects:
            # B1: every graded unit's score sits in its grade band.
            for u in proj.units:
                if u.grade is not None and not is_legal(u.max_score, u.grade, u.score):
                    f(Finding("B1", Severity.ERROR,
                              f"{u.unit_key}: score {u.score} outside band for grade {u.grade.value}"))
                # B3: no unit exceeds its max.
                if u.score > u.max_score + 1e-9:
                    f(Finding("B3", Severity.ERROR,
                              f"{u.unit_key}: score {u.score} > max {u.max_score}"))
                if u.score < 0:
                    f(Finding("B3", Severity.ERROR, f"{u.unit_key}: negative score {u.score}"))

            # B2: project total == sum of its units.
            unit_sum = round(sum(u.score for u in proj.units), 1)
            if abs(unit_sum - proj.total) > 0.05:
                f(Finding("B2", Severity.ERROR,
                          f"{proj.project}: units sum to {unit_sum} but total is {proj.total}"))

            # B4: a vetoed project must total exactly 0.
            if proj.vetoed and proj.total != 0:
                f(Finding("B4", Severity.ERROR,
                          f"{proj.project}: vetoed but total is {proj.total}, expected 0"))

            # B5: a transmitted (failed-gate) project must fall below the pass mark.
            if proj.transmitted and proj.total >= self.rubric.pass_mark:
                f(Finding("B5", Severity.ERROR,
                          f"{proj.project}: transmission fired but total {proj.total} >= pass mark"))

            # B9: weighted score is computed correctly.
            expect_weighted = round(proj.total * proj.weight, 2)
            if abs(expect_weighted - proj.weighted) > 0.01:
                f(Finding("B9", Severity.ERROR,
                          f"{proj.project}: weighted {proj.weighted} != {proj.total}*{proj.weight}"))

        # B7: bonus cap.
        if assessment.bonus_total > self.rubric.bonus_cap + 1e-9:
            f(Finding("B7", Severity.ERROR,
                      f"bonus total {assessment.bonus_total} exceeds cap {self.rubric.bonus_cap}"))

        # B10: final == base + bonus.
        if abs(assessment.final_total - (assessment.base_total + assessment.bonus_total)) > 0.01:
            f(Finding("B10", Severity.ERROR,
                      f"final {assessment.final_total} != base {assessment.base_total} + bonus {assessment.bonus_total}"))

        # B17: any escalated unit means the result is not final.
        for proj in assessment.projects:
            for u in proj.units:
                if u.provenance is Provenance.ESCALATED:
                    f(Finding("B17", Severity.WARNING,
                              f"{u.unit_key}: escalated to human review, result not final"))

        return findings

    @staticmethod
    def has_errors(findings: list[Finding]) -> bool:
        return any(x.severity is Severity.ERROR for x in findings)
