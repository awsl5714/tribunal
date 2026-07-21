"""Deterministic application of veto and transmission rules.

These are *not* LLM decisions. Once the assessors have graded the qualification
units, whether a veto fires is a pure function of those grades, and what it does
to the numbers is arithmetic. Keeping this out of the model is what makes the
scores reproducible and auditable.
"""

from __future__ import annotations

from ..domain.assessment import Provenance, UnitScore
from ..domain.rubric import Rubric, TransmissionRule, VetoRule
from ..rubric.grade_bands import grade_of


def apply_veto(
    rubric: Rubric,
    veto: VetoRule,
    unit_scores: dict[str, UnitScore],
    *,
    qualification_failed: bool,
    role: str = "",
) -> bool:
    """If ``qualification_failed``, zero every unit in the veto's project.

    Returns True if the veto fired. The reference application's two vetoes —
    research-qualification and authorship-role — are both expressed this way.
    """
    if not qualification_failed:
        return False

    for unit in rubric.units_for(veto.project):
        us = unit_scores.get(unit.key)
        note = f"vetoed by {veto.key}"
        if role:
            note += f" (actual role: {role})"
        if us is None:
            unit_scores[unit.key] = UnitScore(
                unit_key=unit.key,
                grade=None,
                score=0.0,
                max_score=unit.max_score,
                rationale=note,
                provenance=Provenance.VETOED,
            )
        else:
            us.score = 0.0
            us.grade = None
            us.provenance = Provenance.VETOED
            us.rationale = f"{note}: {us.rationale}"
    return True


def apply_transmission(
    rubric: Rubric,
    rule: TransmissionRule,
    unit_scores: dict[str, UnitScore],
) -> bool:
    """If the trigger unit failed, cap the affected sibling units.

    "Failed" means the trigger unit scored 0 (its anchor condition is unmet).
    Each affected unit is capped at the rule's ceiling so the project total
    falls below the pass mark *as a natural sum*, not by post-hoc clamping.
    """
    trigger = unit_scores.get(rule.trigger_unit)
    # Only a genuinely-scored zero triggers transmission. An escalated trigger
    # (grade is None -> outcome unknown) must not silently fire it.
    if trigger is None or trigger.grade is None or trigger.score > 0:
        return False

    fired = False
    for unit_key, cap in rule.caps.items():
        us = unit_scores.get(unit_key)
        if us is None or us.grade is None:
            continue
        if us.score > cap:
            us.score = round(cap, 1)
            # keep grade consistent with the capped number
            us.grade = grade_of(rubric.unit(unit_key).max_score, us.score)
            us.provenance = Provenance.TRANSMITTED
            us.rationale = f"capped at {cap} by transmission from {rule.trigger_unit}: {us.rationale}"
            fired = True
    return fired
