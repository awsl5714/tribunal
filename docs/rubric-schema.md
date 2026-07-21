# Rubric YAML schema

A rubric is loaded by `tribunal.rubric.load_rubric` and validated on load.

```yaml
name: "capstone-review"        # rubric identifier
pass_mark: 60.0                # project total below this = not passing
bonus_cap: 15.0               # max total bonus points

weights:                       # project -> weight; must sum to 1.0
  research: 0.30
  team: 0.30
  digital_resources: 0.10
  development_report: 0.10
  elective_exam: 0.20

units:                         # every atomic scoring line item
  - key: research.topic_value  # unique id
    project: research          # which project it rolls up into
    label: "Topic value"       # human-readable name
    max_score: 15              # points available
    type: grade_band           # grade_band | base_plus_tier | qualification
    transmission_cap: 0.0      # optional: ceiling when project transmission fires

veto_rules:                    # qualification gates
  - key: veto.authorship_role
    project: elective_exam     # project zeroed when the gate fails
    description: "..."
    conditions:                # human-facing statements the assessors confirm
      - "candidate is first author"
    zeroes_bonus_only: false   # true = failing zeros only the bonus, not a project

transmission_rules:            # cap siblings when an anchor fails
  - project: team
    trigger_unit: team.basic   # if this scores 0 ...
    caps:                      # ... cap these units at these ceilings
      team.activity: 5.9
      team.members: 2.9
```

## Validation on load

`Rubric.validate_self()` (called by the loader) rejects a rubric that has:

- duplicate unit keys,
- weights that don't sum to `1.0` (when weights are given),
- a transmission `trigger_unit` that isn't a real unit key.

## Unit types

| `type` | Meaning |
|---|---|
| `grade_band` | Standard six-grade scoring against the band table. |
| `base_plus_tier` | A qualifying base plus a tiered top-up (e.g. base 40 + up to 20). |
| `qualification` | A pass/fail gate that can only be full marks or 0. |

The type is advisory metadata for reviewers and downstream tooling; the numeric
consequences (bands, vetoes, transmission) are enforced by the deterministic
layer regardless.
