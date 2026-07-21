"""Transmission caps push a failed-gate project below the pass mark via the sum."""

from tribunal.domain.assessment import Provenance, UnitScore
from tribunal.domain.rubric import Grade
from tribunal.validation.rules import apply_transmission


def _scores(rubric, project, trigger_value, other_value=9.0):
    out = {}
    rule = rubric.transmission_for(project)
    for u in rubric.units_for(project):
        val = trigger_value if u.key == rule.trigger_unit else min(other_value, u.max_score)
        out[u.key] = UnitScore(u.key, Grade.EXCELLENT, val, u.max_score, "seed")
    return out, rule


def test_transmission_fires_when_trigger_is_zero(rubric):
    scores, rule = _scores(rubric, "team", trigger_value=0.0)
    fired = apply_transmission(rubric, rule, scores)
    assert fired
    for key, cap in rule.caps.items():
        assert scores[key].score <= cap
        assert scores[key].provenance is Provenance.TRANSMITTED


def test_transmission_pushes_team_below_pass_mark(rubric):
    scores, rule = _scores(rubric, "team", trigger_value=0.0, other_value=100.0)
    apply_transmission(rubric, rule, scores)
    total = sum(scores[u.key].score for u in rubric.units_for("team"))
    assert total < rubric.pass_mark  # 46.5 ceiling in the reference design


def test_transmission_noop_when_trigger_positive(rubric):
    scores, rule = _scores(rubric, "team", trigger_value=30.0)
    fired = apply_transmission(rubric, rule, scores)
    assert not fired
