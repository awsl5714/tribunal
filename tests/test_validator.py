"""The deterministic post-check suite catches illegal / inconsistent scores."""

from tribunal.domain.assessment import Assessment, ProjectScore, UnitScore
from tribunal.domain.rubric import Grade
from tribunal.validation.validator import Severity, Validator


def _assessment_ok():
    units = [
        UnitScore("elective.basic", Grade.GOOD, 42.0, 50, "ok"),
        UnitScore("elective.topic", Grade.GOOD, 12.0, 15, "ok"),
        UnitScore("elective.content", Grade.GOOD, 12.0, 15, "ok"),
        UnitScore("elective.publish", Grade.GOOD, 17.0, 20, "ok"),
    ]
    total = sum(u.score for u in units)  # 83
    proj = ProjectScore("elective_exam", total, 0.2, round(total * 0.2, 2), units)
    a = Assessment("c1", "C", [proj])
    a.base_total = proj.weighted
    a.bonus_total = 0.0
    a.final_total = a.base_total
    return a


def test_clean_assessment_has_no_errors(rubric):
    findings = Validator(rubric).check(_assessment_ok())
    assert not Validator.has_errors(findings)


def test_detects_score_outside_band(rubric):
    a = _assessment_ok()
    a.projects[0].units[0].score = 49.0  # GOOD band for 50 is 40-44.9
    findings = Validator(rubric).check(a)
    assert any(f.code == "B1" and f.severity is Severity.ERROR for f in findings)


def test_detects_sum_mismatch(rubric):
    a = _assessment_ok()
    a.projects[0].total = 999.0
    findings = Validator(rubric).check(a)
    assert any(f.code == "B2" for f in findings)


def test_detects_weighted_mismatch(rubric):
    a = _assessment_ok()
    a.projects[0].weighted = 0.0
    findings = Validator(rubric).check(a)
    assert any(f.code == "B9" for f in findings)


def test_detects_bonus_over_cap(rubric):
    a = _assessment_ok()
    a.bonus_total = 20.0
    a.final_total = a.base_total + a.bonus_total
    findings = Validator(rubric).check(a)
    assert any(f.code == "B7" for f in findings)


def test_detects_final_total_mismatch(rubric):
    a = _assessment_ok()
    a.final_total = 123.0
    findings = Validator(rubric).check(a)
    assert any(f.code == "B10" for f in findings)


def test_vetoed_project_must_be_zero(rubric):
    a = _assessment_ok()
    a.projects[0].vetoed = True  # but total is 83
    findings = Validator(rubric).check(a)
    assert any(f.code == "B4" for f in findings)
