"""Rubric loading and the deterministic grade-band engine."""

from .grade_bands import (
    band,
    band_table,
    clamp_to_band,
    grade_of,
    is_legal,
)
from .loader import load_rubric, parse_rubric

__all__ = [
    "band",
    "band_table",
    "clamp_to_band",
    "grade_of",
    "is_legal",
    "load_rubric",
    "parse_rubric",
]
