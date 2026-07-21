"""End-to-end review pipeline: submission -> assessment.

Wiring order (matters):

1. **Consensus** — the two LLM assessors resolve every scoring unit.
2. **Veto** — qualification gates zero out whole projects (deterministic).
3. **Transmission** — failed anchors cap sibling units (deterministic).
4. **Rollup** — sum units -> project totals -> weighted -> base + bonus -> final.
5. **Validate** — the machine checklist runs over the finished numbers.
6. **Escalate** — anything unconverged / erroring is queued for a human.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..domain.assessment import Assessment, ProjectScore, Provenance, UnitScore
from ..domain.rubric import Rubric
from ..domain.submission import Submission
from ..agents.orchestrator import ConsensusOrchestrator
from ..hitl.escalation import EscalationQueue
from ..validation.rules import apply_transmission, apply_veto
from ..validation.validator import Validator


@dataclass
class GateEvaluator:
    """Supplies the boolean outcome of each qualification veto.

    In production these come from the assessors reading qualification evidence
    (is-owner? first-author? in-window?). Here they are injected so the caller —
    or a test — controls them explicitly. Maps ``veto.key`` ->
    ``(failed: bool, role: str)``.
    """

    gates: dict[str, tuple[bool, str]] = field(default_factory=dict)

    def failed(self, veto_key: str) -> tuple[bool, str]:
        return self.gates.get(veto_key, (False, ""))


class ReviewPipeline:
    def __init__(
        self,
        rubric: Rubric,
        orchestrator: ConsensusOrchestrator,
        *,
        bonus_scorer: Callable[[str, Submission], float] | None = None,
    ):
        self.rubric = rubric
        self.orchestrator = orchestrator
        self.validator = Validator(rubric)
        self.bonus_scorer = bonus_scorer or (lambda project, sub: 0.0)

    def run(
        self,
        submission: Submission,
        gates: GateEvaluator | None = None,
        queue: EscalationQueue | None = None,
    ) -> Assessment:
        gates = gates or GateEvaluator()

        # 1. consensus over every unit
        unit_scores: dict[str, UnitScore] = {}
        escalations: list[str] = []
        for unit in self.rubric.units:
            us = self.orchestrator.resolve(unit, submission)
            unit_scores[unit.key] = us
            if us.provenance is Provenance.ESCALATED:
                escalations.append(f"{unit.key}: assessors did not converge")
            if us.disagreement > 0:
                # informative, not fatal
                pass

        # 2. vetoes (deterministic)
        vetoed_projects: set[str] = set()
        for veto in self.rubric.veto_rules:
            failed, role = gates.failed(veto.key)
            if apply_veto(self.rubric, veto, unit_scores, qualification_failed=failed, role=role):
                vetoed_projects.add(veto.project)
                escalations.append(f"{veto.project}: {veto.key} veto fired (role={role or 'n/a'})")

        # 3. transmission (deterministic) — skip projects already vetoed to zero
        transmitted_projects: set[str] = set()
        for rule in self.rubric.transmission_rules:
            if rule.project in vetoed_projects:
                continue
            if apply_transmission(self.rubric, rule, unit_scores):
                transmitted_projects.add(rule.project)

        # 4. rollup
        assessment = Assessment(
            candidate_id=submission.candidate_id,
            candidate_name=submission.candidate_name,
            escalations=escalations,
        )
        base_total = 0.0
        for project in self.rubric.projects:
            units = [unit_scores[u.key] for u in self.rubric.units_for(project)]
            total = round(sum(u.score for u in units), 1)
            weight = self.rubric.weights.get(project, 0.0)
            weighted = round(total * weight, 2)
            base_total += weighted
            assessment.projects.append(
                ProjectScore(
                    project=project,
                    total=total,
                    weight=weight,
                    weighted=weighted,
                    units=units,
                    vetoed=project in vetoed_projects,
                    transmitted=project in transmitted_projects,
                )
            )

        # bonus items (capped)
        bonus = sum(
            self.bonus_scorer(p, submission) for p in submission.elective_bonus_projects
        )
        assessment.bonus_total = round(min(bonus, self.rubric.bonus_cap), 1)
        assessment.base_total = round(base_total, 2)
        assessment.final_total = round(assessment.base_total + assessment.bonus_total, 2)

        # 5. validate
        findings = self.validator.check(assessment)
        assessment.anomalies = [f"{f.code} {f.severity.value}: {f.message}" for f in findings]
        if Validator.has_errors(findings) or escalations:
            assessment.needs_human_review = True

        # 6. escalate
        if queue is not None:
            queue.maybe_enqueue(assessment, findings)

        return assessment
