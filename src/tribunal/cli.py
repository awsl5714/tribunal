"""Command-line entry point.

Usage::

    python -m tribunal.cli score --rubric examples/rubric.yaml \\
        --submission examples/submission_pass.json

By default it uses the offline :class:`MockLLM` backend so it runs with no API
keys. Pass ``--backend openai+anthropic`` to use the real GPT scorer + Claude
reviewer (requires ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agents import (
    AnthropicClient,
    ConsensusOrchestrator,
    LLMClient,
    MockLLM,
    OpenAIClient,
    Reviewer,
    Scorer,
)
from .domain import Evidence, Submission
from .hitl import EscalationQueue
from .pipeline import GateEvaluator, ReviewPipeline
from .rubric import load_rubric


def _load_submission(path: str | Path) -> tuple[Submission, GateEvaluator]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    evidence = {
        key: [Evidence(**e) for e in items]
        for key, items in raw.get("evidence", {}).items()
    }
    submission = Submission(
        candidate_id=raw["candidate_id"],
        candidate_name=raw["candidate_name"],
        elective_exam_project=raw.get("elective_exam_project"),
        elective_bonus_projects=tuple(raw.get("elective_bonus_projects", [])),
        evidence=evidence,
        meta=raw.get("meta", {}),
    )
    gates = GateEvaluator(
        gates={k: (bool(v[0]), str(v[1])) for k, v in raw.get("gates", {}).items()}
    )
    return submission, gates


def _build_pipeline(rubric, backend: str) -> ReviewPipeline:
    scorer_client: LLMClient
    reviewer_client: LLMClient
    if backend == "mock":
        scorer_client = MockLLM("gpt-mock", bias=0)
        reviewer_client = MockLLM("claude-mock", bias=1)
    elif backend == "openai+anthropic":
        scorer_client = OpenAIClient()
        reviewer_client = AnthropicClient()
    else:
        raise SystemExit(f"unknown backend: {backend}")
    orchestrator = ConsensusOrchestrator(Scorer(scorer_client), Reviewer(reviewer_client))
    return ReviewPipeline(rubric, orchestrator)


def _print_assessment(assessment) -> None:
    print(f"\n=== {assessment.candidate_name} ({assessment.candidate_id}) ===")
    for proj in assessment.projects:
        flag = " [VETOED]" if proj.vetoed else (" [TRANSMITTED]" if proj.transmitted else "")
        print(f"\n{proj.project}: total={proj.total} weight={proj.weight} weighted={proj.weighted}{flag}")
        for u in proj.units:
            g = u.grade.value if u.grade else "—"
            src = f" <{u.provenance.value}>"
            print(f"    {u.unit_key:<28} {g:<12} {u.score:>5}/{u.max_score:<5}{src}")
    print(f"\nbase_total  = {assessment.base_total}")
    print(f"bonus_total = {assessment.bonus_total}")
    print(f"final_total = {assessment.final_total}")
    if assessment.needs_human_review:
        print("\n** HELD FOR HUMAN REVIEW **")
        for e in assessment.escalations:
            print(f"   - {e}")
    if assessment.anomalies:
        print("\nvalidator findings:")
        for a in assessment.anomalies:
            print(f"   - {a}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tribunal", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_score = sub.add_parser("score", help="score one submission")
    p_score.add_argument("--rubric", required=True)
    p_score.add_argument("--submission", required=True)
    p_score.add_argument("--backend", default="mock",
                         choices=["mock", "openai+anthropic"])

    args = parser.parse_args(argv)

    if args.cmd == "score":
        rubric = load_rubric(args.rubric)
        submission, gates = _load_submission(args.submission)
        pipeline = _build_pipeline(rubric, args.backend)
        queue = EscalationQueue()
        assessment = pipeline.run(submission, gates, queue)
        _print_assessment(assessment)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
