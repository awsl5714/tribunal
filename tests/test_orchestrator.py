"""Consensus orchestration between two assessors."""

from tribunal.agents import ConsensusConfig, ConsensusOrchestrator, MockLLM, Reviewer, Scorer
from tribunal.domain.assessment import Provenance
from tribunal.domain.rubric import ScoringUnit, UnitType
from tribunal.domain.submission import Evidence, Submission


def _unit():
    return ScoringUnit("u1", "proj", "Unit One", 10, UnitType.GRADE_BAND)


def _submission():
    return Submission(
        candidate_id="c1",
        candidate_name="C",
        evidence={"u1": [Evidence("f.pdf", "p.1", "some evidence")]},
    )


def test_agreeing_assessors_reach_consensus():
    orch = ConsensusOrchestrator(Scorer(MockLLM("a", 0)), Reviewer(MockLLM("a", 0)))
    us = orch.resolve(_unit(), _submission())
    assert us.provenance in (Provenance.CONSENSUS, Provenance.REVISED)
    assert us.grade is not None
    assert 0 <= us.score <= 10


def test_consensus_takes_conservative_score():
    # identical clients -> identical proposal & verdict -> min() is that score
    orch = ConsensusOrchestrator(Scorer(MockLLM("x", 0)), Reviewer(MockLLM("x", 0)))
    us = orch.resolve(_unit(), _submission())
    assert us.score == min(us.scorer_score, us.reviewer_score)


def test_persistent_disagreement_escalates():
    # Force wide, stubborn disagreement and zero tolerance so it never converges.
    orch = ConsensusOrchestrator(
        Scorer(MockLLM("gpt", bias=-1)),
        Reviewer(MockLLM("claude", bias=+3)),
        ConsensusConfig(max_rounds=2, grade_tolerance=0),
    )
    us = orch.resolve(_unit(), _submission())
    assert us.provenance is Provenance.ESCALATED
    assert us.grade is None
    assert us.score == 0.0


def test_score_always_legal_for_its_grade():
    from tribunal.rubric.grade_bands import is_legal

    orch = ConsensusOrchestrator(Scorer(MockLLM("a", 0)), Reviewer(MockLLM("b", 1)))
    for max_score in (5, 15, 40, 60):
        unit = ScoringUnit("u", "p", "U", max_score)
        us = orch.resolve(unit, _submission())
        if us.grade is not None:
            assert is_legal(max_score, us.grade, us.score)
