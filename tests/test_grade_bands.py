"""The grade-band engine is the deterministic core — test it hard."""

import pytest

from tribunal.domain.rubric import Grade
from tribunal.rubric.grade_bands import (
    band,
    band_table,
    clamp_to_band,
    grade_of,
    is_legal,
)

# The ten canonical band tables from the reference rubric.
EXPECTED = {
    5:  {Grade.OUTSTANDING: (5.0, 5.0), Grade.EXCELLENT: (4.5, 4.9), Grade.GOOD: (4.0, 4.4),
         Grade.FAIR: (3.5, 3.9), Grade.PASS: (3.0, 3.4), Grade.FAIL: (0.0, 2.9)},
    10: {Grade.OUTSTANDING: (10.0, 10.0), Grade.EXCELLENT: (9.0, 9.9), Grade.GOOD: (8.0, 8.9),
         Grade.FAIR: (7.0, 7.9), Grade.PASS: (6.0, 6.9), Grade.FAIL: (0.0, 5.9)},
    15: {Grade.OUTSTANDING: (15.0, 15.0), Grade.EXCELLENT: (13.5, 14.9), Grade.GOOD: (12.0, 13.4),
         Grade.FAIR: (10.5, 11.9), Grade.PASS: (9.0, 10.4), Grade.FAIL: (0.0, 8.9)},
    20: {Grade.OUTSTANDING: (20.0, 20.0), Grade.EXCELLENT: (18.0, 19.9), Grade.GOOD: (16.0, 17.9),
         Grade.FAIR: (14.0, 15.9), Grade.PASS: (12.0, 13.9), Grade.FAIL: (0.0, 11.9)},
    25: {Grade.OUTSTANDING: (25.0, 25.0), Grade.EXCELLENT: (22.5, 24.9), Grade.GOOD: (20.0, 22.4),
         Grade.FAIR: (17.5, 19.9), Grade.PASS: (15.0, 17.4), Grade.FAIL: (0.0, 14.9)},
    30: {Grade.OUTSTANDING: (30.0, 30.0), Grade.EXCELLENT: (27.0, 29.9), Grade.GOOD: (24.0, 26.9),
         Grade.FAIR: (21.0, 23.9), Grade.PASS: (18.0, 20.9), Grade.FAIL: (0.0, 17.9)},
    35: {Grade.OUTSTANDING: (35.0, 35.0), Grade.EXCELLENT: (31.5, 34.9), Grade.GOOD: (28.0, 31.4),
         Grade.FAIR: (24.5, 27.9), Grade.PASS: (21.0, 24.4), Grade.FAIL: (0.0, 20.9)},
    40: {Grade.OUTSTANDING: (40.0, 40.0), Grade.EXCELLENT: (36.0, 39.9), Grade.GOOD: (32.0, 35.9),
         Grade.FAIR: (28.0, 31.9), Grade.PASS: (24.0, 27.9), Grade.FAIL: (0.0, 23.9)},
    50: {Grade.OUTSTANDING: (50.0, 50.0), Grade.EXCELLENT: (45.0, 49.9), Grade.GOOD: (40.0, 44.9),
         Grade.FAIR: (35.0, 39.9), Grade.PASS: (30.0, 34.9), Grade.FAIL: (0.0, 29.9)},
    60: {Grade.OUTSTANDING: (60.0, 60.0), Grade.EXCELLENT: (54.0, 59.9), Grade.GOOD: (48.0, 53.9),
         Grade.FAIR: (42.0, 47.9), Grade.PASS: (36.0, 41.9), Grade.FAIL: (0.0, 35.9)},
}


@pytest.mark.parametrize("max_score", sorted(EXPECTED))
def test_band_tables_match_reference(max_score):
    assert band_table(max_score) == EXPECTED[max_score]


@pytest.mark.parametrize("max_score", sorted(EXPECTED))
def test_bands_are_contiguous_and_cover_zero_to_max(max_score):
    # Walk from FAIL up: each grade's high + 0.1 should equal the next grade's low.
    order = [Grade.FAIL, Grade.PASS, Grade.FAIR, Grade.GOOD, Grade.EXCELLENT]
    for lower, upper in zip(order, order[1:]):
        _, lo_high = band(max_score, lower)
        up_low, _ = band(max_score, upper)
        assert round(lo_high + 0.1, 1) == up_low
    assert band(max_score, Grade.FAIL)[0] == 0.0
    assert band(max_score, Grade.OUTSTANDING) == (max_score, max_score)


def test_grade_of_is_inverse_of_band():
    for max_score in EXPECTED:
        for grade, (low, high) in EXPECTED[max_score].items():
            assert grade_of(max_score, low) == grade
            assert grade_of(max_score, high) == grade


def test_is_legal():
    assert is_legal(10, Grade.EXCELLENT, 9.5)
    assert not is_legal(10, Grade.EXCELLENT, 8.5)
    assert is_legal(10, Grade.OUTSTANDING, 10.0)
    assert not is_legal(10, Grade.OUTSTANDING, 9.9)


def test_clamp_snaps_into_band():
    # grade says EXCELLENT (9.0-9.9) but number 7.0 is FAIR -> snap up to 9.0
    assert clamp_to_band(10, Grade.EXCELLENT, 7.0) == 9.0
    # number above the band -> snap down
    assert clamp_to_band(10, Grade.GOOD, 9.9) == 8.9
    # already legal -> unchanged
    assert clamp_to_band(10, Grade.GOOD, 8.5) == 8.5
