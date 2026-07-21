"""Runnable demo: score two synthetic submissions with the offline mock backend.

    python examples/demo.py

Shows the happy path (consensus + rollup) and the veto path (two qualification
gates zeroing whole projects), plus the deterministic validator and the
human-in-the-loop queue.
"""

from __future__ import annotations

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
    load_rubric,
)
from tribunal.pipeline import GateEvaluator

HERE = Path(__file__).parent


def load_submission(name: str):
    raw = json.loads((HERE / name).read_text(encoding="utf-8"))
    evidence = {k: [Evidence(**e) for e in v] for k, v in raw.get("evidence", {}).items()}
    submission = Submission(
        candidate_id=raw["candidate_id"],
        candidate_name=raw["candidate_name"],
        elective_exam_project=raw.get("elective_exam_project"),
        elective_bonus_projects=tuple(raw.get("elective_bonus_projects", [])),
        evidence=evidence,
        meta=raw.get("meta", {}),
    )
    gates = GateEvaluator({k: (bool(v[0]), str(v[1])) for k, v in raw.get("gates", {}).items()})
    return submission, gates


def main() -> None:
    rubric = load_rubric(HERE / "rubric.yaml")

    # GPT plays scorer; Claude plays independent reviewer. Offline they're two
    # mock backends with a slight bias difference so consensus/escalation runs.
    orchestrator = ConsensusOrchestrator(
        Scorer(MockLLM("gpt-4o", bias=0)),
        Reviewer(MockLLM("claude-sonnet-4-5", bias=1)),
    )

    # a tiny bonus scorer for the demo (real one would grade the bonus evidence)
    pipeline = ReviewPipeline(rubric, orchestrator, bonus_scorer=lambda p, s: 4.0)

    queue = EscalationQueue()

    for name in ("submission_pass.json", "submission_veto.json"):
        submission, gates = load_submission(name)
        assessment = pipeline.run(submission, gates, queue)
        print(f"\n{'='*64}\n{assessment.candidate_name} ({assessment.candidate_id})")
        for proj in assessment.projects:
            tag = "VETOED" if proj.vetoed else ("TRANSMITTED" if proj.transmitted else "")
            print(f"  {proj.project:<20} total={proj.total:>5}  weighted={proj.weighted:>6}  {tag}")
        print(f"  base={assessment.base_total}  bonus={assessment.bonus_total}  FINAL={assessment.final_total}")
        print(f"  human review needed: {assessment.needs_human_review}")

    print(f"\n{'='*64}\nEscalation queue: {len(queue.tickets)} ticket(s)")
    for t in queue.tickets:
        print(t.summary())


if __name__ == "__main__":
    main()
