"""Load a :class:`Rubric` from a YAML file.

The YAML schema is intentionally close to the machine-readable "scoring-unit
table" the reference project used, so a domain expert can maintain the rubric
without touching Python.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..domain.rubric import (
    Rubric,
    ScoringUnit,
    TransmissionRule,
    UnitType,
    VetoRule,
)


def load_rubric(path: str | Path) -> Rubric:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return parse_rubric(raw)


def parse_rubric(raw: dict[str, Any]) -> Rubric:
    units = tuple(
        ScoringUnit(
            key=u["key"],
            project=u["project"],
            label=u.get("label", u["key"]),
            max_score=float(u["max_score"]),
            unit_type=UnitType(u.get("type", "grade_band")),
            transmission_cap=_opt_float(u.get("transmission_cap")),
        )
        for u in raw["units"]
    )

    veto_rules = tuple(
        VetoRule(
            key=v["key"],
            project=v["project"],
            description=v.get("description", ""),
            conditions=tuple(v.get("conditions", [])),
            zeroes_bonus_only=bool(v.get("zeroes_bonus_only", False)),
        )
        for v in raw.get("veto_rules", [])
    )

    transmission_rules = tuple(
        TransmissionRule(
            project=t["project"],
            trigger_unit=t["trigger_unit"],
            caps={k: float(val) for k, val in t["caps"].items()},
        )
        for t in raw.get("transmission_rules", [])
    )

    rubric = Rubric(
        name=raw.get("name", "unnamed"),
        units=units,
        weights={k: float(v) for k, v in raw.get("weights", {}).items()},
        veto_rules=veto_rules,
        transmission_rules=transmission_rules,
        bonus_cap=float(raw.get("bonus_cap", 15.0)),
        pass_mark=float(raw.get("pass_mark", 60.0)),
    )

    problems = rubric.validate_self()
    if problems:
        raise ValueError(f"invalid rubric {rubric.name!r}: {'; '.join(problems)}")
    return rubric


def _opt_float(v: Any) -> float | None:
    return None if v is None else float(v)
