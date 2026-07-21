# Tribunal

**Multi-agent LLM document assessment with deterministic arbitration and human-in-the-loop escalation.**

Two large language models — a **scorer** (GPT) and an independent **reviewer** (Claude) — grade a document against a machine-readable rubric over multiple rounds. A deterministic layer they cannot influence does all the arithmetic, enforces qualification gates, and routes anything the models can't agree on to a human.

[![CI](https://github.com/awsl5714/tribunal/actions/workflows/ci.yml/badge.svg)](https://github.com/awsl5714/tribunal/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## Why this exists

The system was distilled from a real project: reviewing the graduation portfolios of ~100 candidates in a provincial "master teacher / principal" training programme. Each portfolio is hundreds of pages of PDF/Word plus an Excel scoresheet, graded against a rubric with ~30 line items, weighted projects, qualification gates, and bonus caps.

Letting a single LLM "just score it" fails in three predictable ways:

1. **It does arithmetic wrong.** Sums that don't add up, scores outside their grade band, weighted totals that don't reconcile.
2. **It rationalises.** One model, one pass — nothing challenges an over-generous or under-evidenced score.
3. **It fabricates confidence.** It returns a number for cases a human should actually decide.

Tribunal is the architecture that addresses all three:

| Failure | Mechanism |
|---|---|
| Bad arithmetic | **The model judges, the code computes.** LLMs only emit a *grade*; a deterministic engine turns grades into numbers, sums, weights, and validates every result. |
| Rationalisation | **Dual-LLM consensus.** GPT proposes, Claude independently audits, they iterate; the conservative score wins ties. |
| False confidence | **Human-in-the-loop.** Non-convergence, ambiguous gates, and surviving validator errors are escalated, never guessed. |

On the source project this pushed grade-band errors caught by the deterministic layer to **~85%** and concentrated genuinely hard cases into the **~15%** that reached a human.

> This repository ships **only synthetic examples** — no real candidate data. The rubric is a generalised, anonymised version of the original.

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
   Submission  ───► │  1. CONSENSUS   scorer (GPT) ⇄ reviewer (Claude)   │
   + Evidence       │                 multi-round, per scoring unit │
                    └─────────────────────────────────────────────┘
                                      │ proposed unit scores (grades)
                                      ▼
                    ┌─────────────────────────────────────────────┐
                    │  2. VETO        qualification gates → project = 0 │  deterministic
                    │  3. TRANSMISSION failed anchor → cap siblings │  deterministic
                    │  4. ROLLUP      Σ units → weighted → final    │  deterministic
                    │  5. VALIDATE    band / sum / cap / consistency │  deterministic
                    └─────────────────────────────────────────────┘
                                      │
                       converged & clean │ unconverged / error
                                      ▼        ▼
                                  Assessment   Human review queue
```

The LLMs touch only step 1. Steps 2–5 are pure functions of their grades — reproducible, testable, and auditable. See [`docs/architecture.md`](docs/architecture.md) and [`docs/design-decisions.md`](docs/design-decisions.md).

---

## Quickstart

```bash
git clone https://github.com/awsl5714/tribunal
cd tribunal
pip install -e ".[dev]"          # core + test tooling, no API keys needed

python examples/demo.py          # runs fully offline on the mock backend
pytest -q                        # 44 tests
```

Offline demo output (deterministic mock backend):

```
Synthetic Candidate A (SYN-001)
  research            total= 76.7  weighted= 23.01
  team                total= 63.1  weighted= 18.93
  ...
  base=72.81  bonus=8.0  FINAL=80.81   human review needed: False

Synthetic Candidate B (SYN-002)
  research            total=  0.0  weighted=  0.0   VETOED   (not project owner)
  elective_exam       total=  0.0  weighted=  0.0   VETOED   (corresponding author, not first author)
  base=33.92  bonus=0  FINAL=33.92   human review needed: True
```

### Using the real GPT + Claude backends

```bash
pip install -e ".[llm]"
export OPENAI_API_KEY=...  ANTHROPIC_API_KEY=...
python -m tribunal.cli score \
    --rubric examples/rubric.yaml \
    --submission examples/submission_pass.json \
    --backend openai+anthropic
```

`OpenAIClient` is the scorer, `AnthropicClient` the reviewer — swap either for any class implementing the three-method [`LLMClient`](src/tribunal/agents/llm_client.py) interface.

---

## Library usage

```python
from tribunal import (
    load_rubric, Submission, Evidence,
    Scorer, Reviewer, ConsensusOrchestrator,
    OpenAIClient, AnthropicClient,
    ReviewPipeline, GateEvaluator, EscalationQueue,
)

rubric = load_rubric("examples/rubric.yaml")

orchestrator = ConsensusOrchestrator(
    Scorer(OpenAIClient("gpt-4o")),        # proposes
    Reviewer(AnthropicClient("claude-sonnet-4-5")),  # independently audits
)
pipeline = ReviewPipeline(rubric, orchestrator)

submission = Submission(
    candidate_id="C-001", candidate_name="…",
    evidence={"research.topic_value": [Evidence("portfolio.pdf", "p.6-17", "…")]},
)
gates = GateEvaluator({"veto.research_qualification": (False, "project owner")})

queue = EscalationQueue()
assessment = pipeline.run(submission, gates, queue)

print(assessment.final_total, assessment.needs_human_review)
for ticket in queue.tickets:
    print(ticket.summary())
```

---

## Key design decisions

- **Rubric as data.** Scoring units, weights, grade bands, veto gates, and transmission caps live in [`examples/rubric.yaml`](examples/rubric.yaml). A domain expert maintains scoring policy without touching Python.
- **One grade-band engine.** [`grade_bands.py`](src/tribunal/rubric/grade_bands.py) generates every band table (max 5…60) from a single ratio table and is the *only* authority mapping grade ↔ number.
- **Two one-vote vetoes, generalised.** A research-qualification gate and an authorship-role gate each zero an entire project when the candidate fails to qualify — modelled as declarative [`VetoRule`s](src/tribunal/domain/rubric.py).
- **Transmission over hard-capping.** When a mandatory project's anchor fails, sibling units are capped so the total *naturally* falls below the pass mark, preserving "project total = Σ units" instead of post-hoc clamping.
- **Escalation, not averaging.** Two assessors who genuinely disagree are never silently averaged — the unit is flagged `ESCALATED` and the result held.

---

## Project layout

```
src/tribunal/
├── domain/         rubric, submission, assessment data model
├── rubric/         YAML loader + deterministic grade-band engine
├── agents/         LLM clients (mock/OpenAI/Anthropic), scorer, reviewer, orchestrator
├── validation/     veto & transmission rules + the post-check suite
├── hitl/           human-in-the-loop escalation queue
├── pipeline/       document extractors + end-to-end runner
└── cli.py
tests/              44 tests — grade bands, vetoes, transmission, consensus, validator, pipeline
examples/           runnable demo, YAML rubric, synthetic submissions
docs/               architecture, rubric schema, design decisions
```

## License

MIT — see [LICENSE](LICENSE).
