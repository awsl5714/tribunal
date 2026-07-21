"""End-to-end pipeline behaviour on the example submissions."""

import json
from pathlib import Path

from tribunal import (
    ConsensusOrchestrator,
    EscalationQueue,
    Evidence,
    MockLLM,
    Reviewer,
    ReviewPipeline,
    Scorer,
    Submission,
)
from tribunal.pipeline import GateEvaluator
from tribunal.validation.validator import Validator

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load(name):
    raw = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    evidence = {k: [Evidence(**e) for e in v] for k, v in raw["evidence"].items()}
    sub = Submission(
        candidate_id=raw["candidate_id"],
        candidate_name=raw["candidate_name"],
        elective_exam_project=raw.get("elective_exam_project"),
        elective_bonus_projects=tuple(raw.get("elective_bonus_projects", [])),
        evidence=evidence,
    )
    gates = GateEvaluator({k: (bool(v[0]), str(v[1])) for k, v in raw.get("gates", {}).items()})
    return sub, gates


def _pipeline(rubric):
    orch = ConsensusOrchestrator(Scorer(MockLLM("gpt", 0)), Reviewer(MockLLM("claude", 1)))
    return ReviewPipeline(rubric, orch, bonus_scorer=lambda p, s: 4.0)


def test_pass_submission_produces_consistent_numbers(rubric):
    sub, gates = _load("submission_pass.json")
    a = _pipeline(rubric).run(sub, gates)
    # base == sum of weighted; final == base + bonus
    assert abs(a.base_total - sum(p.weighted for p in a.projects)) < 0.01
    assert abs(a.final_total - (a.base_total + a.bonus_total)) < 0.01
    # deterministic validator agrees the numbers are internally consistent
    findings = Validator(rubric).check(a)
    assert not Validator.has_errors(findings)


def test_veto_submission_zeros_two_projects(rubric):
    sub, gates = _load("submission_veto.json")
    a = _pipeline(rubric).run(sub, gates)
    research = a.project("research")
    elective = a.project("elective_exam")
    assert research.vetoed and research.total == 0.0
    assert elective.vetoed and elective.total == 0.0
    assert a.needs_human_review  # vetoes are logged as escalations


def test_bonus_is_capped(rubric):
    sub, gates = _load("submission_pass.json")
    # 5 bonus projects * 4 each = 20 -> capped to 15
    sub = Submission(
        candidate_id=sub.candidate_id,
        candidate_name=sub.candidate_name,
        elective_bonus_projects=("a", "b", "c", "d", "e"),
        evidence=sub.evidence,
    )
    a = _pipeline(rubric).run(sub, gates)
    assert a.bonus_total <= rubric.bonus_cap


def test_escalation_queue_collects_veto_case(rubric):
    queue = EscalationQueue()
    pipe = _pipeline(rubric)
    for name in ("submission_pass.json", "submission_veto.json"):
        sub, gates = _load(name)
        pipe.run(sub, gates, queue)
    # the veto submission must have produced at least one ticket
    assert any(t.candidate_id == "SYN-002" for t in queue.tickets)
