"""Qualification vetoes zero out whole projects, deterministically."""

from tribunal.domain.assessment import Provenance, UnitScore
from tribunal.domain.rubric import Grade
from tribunal.validation.rules import apply_veto


def _seed_scores(rubric, project, value=10.0):
    return {
        u.key: UnitScore(
            unit_key=u.key,
            grade=Grade.EXCELLENT,
            score=min(value, u.max_score),
            max_score=u.max_score,
            rationale="seed",
        )
        for u in rubric.units_for(project)
    }


def test_veto_fires_and_zeros_all_units(rubric):
    veto = rubric.veto_for("elective_exam")
    scores = _seed_scores(rubric, "elective_exam")
    fired = apply_veto(rubric, veto, scores, qualification_failed=True, role="corresponding author")
    assert fired
    for u in rubric.units_for("elective_exam"):
        assert scores[u.key].score == 0.0
        assert scores[u.key].provenance is Provenance.VETOED
        assert "corresponding author" in scores[u.key].rationale


def test_veto_does_not_fire_when_qualification_holds(rubric):
    veto = rubric.veto_for("elective_exam")
    scores = _seed_scores(rubric, "elective_exam")
    fired = apply_veto(rubric, veto, scores, qualification_failed=False)
    assert not fired
    assert all(scores[u.key].score > 0 for u in rubric.units_for("elective_exam"))


def test_research_qualification_veto(rubric):
    veto = rubric.veto_for("research")
    scores = _seed_scores(rubric, "research")
    fired = apply_veto(rubric, veto, scores, qualification_failed=True, role="co-investigator")
    assert fired
    assert sum(scores[u.key].score for u in rubric.units_for("research")) == 0.0
