"""Deterministic grade <-> score-band conversion.

This is the heart of "the model judges, the code computes". An LLM assessor only
ever emits a :class:`~tribunal.domain.rubric.Grade`; this module is the *sole*
authority that turns a grade into a number, and validates that a proposed number
is legal for its grade. It scales to any ``max_score`` from a single ratio table,
which is why the reference rubric's ten different band tables (max 5, 10, 15, 20,
25, 30, 35, 40, 50, 60) all collapse into ~15 lines here.
"""

from __future__ import annotations

from ..domain.rubric import Grade

# (low_ratio, high_ratio_exclusive) of max_score for each grade.
_RATIOS: dict[Grade, tuple[float, float]] = {
    Grade.OUTSTANDING: (1.0, 1.0),
    Grade.EXCELLENT: (0.9, 1.0),
    Grade.GOOD: (0.8, 0.9),
    Grade.FAIR: (0.7, 0.8),
    Grade.PASS: (0.6, 0.7),
    Grade.FAIL: (0.0, 0.6),
}

#: one decimal place of resolution
_STEP = 0.1


def band(max_score: float, grade: Grade) -> tuple[float, float]:
    """Return the inclusive ``(low, high)`` score band for ``grade``.

    >>> band(10, Grade.EXCELLENT)
    (9.0, 9.9)
    >>> band(5, Grade.FAIL)
    (0.0, 2.9)
    >>> band(60, Grade.GOOD)
    (48.0, 53.9)
    """
    if grade is Grade.OUTSTANDING:
        return (round(max_score, 1), round(max_score, 1))
    lo_r, hi_r = _RATIOS[grade]
    low = round(lo_r * max_score, 1)
    high = round(hi_r * max_score - _STEP, 1)
    return (low, high)


def grade_of(max_score: float, score: float) -> Grade:
    """Inverse of :func:`band`: which grade does ``score`` fall in?"""
    if score >= max_score:
        return Grade.OUTSTANDING
    for grade in _RATIOS:
        low, high = band(max_score, grade)
        if low <= score <= high:
            return grade
    return Grade.FAIL


def is_legal(max_score: float, grade: Grade, score: float) -> bool:
    """True iff ``score`` is inside ``grade``'s band for ``max_score``."""
    low, high = band(max_score, grade)
    return low <= round(score, 1) <= high


def clamp_to_band(max_score: float, grade: Grade, score: float) -> float:
    """Snap an out-of-band score to the nearest legal value for its grade.

    Reviewers sometimes emit a grade and a number that don't match (a classic
    LLM failure). Rather than silently trusting either, the validator uses this
    to coerce the number into the grade's band and flags the correction.
    """
    low, high = band(max_score, grade)
    return round(min(max(score, low), high), 1)


def band_table(max_score: float) -> dict[Grade, tuple[float, float]]:
    """The full six-row band table for one ``max_score`` (handy for docs/tests)."""
    return {g: band(max_score, g) for g in Grade}
