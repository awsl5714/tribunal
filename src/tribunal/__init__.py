"""Tribunal — multi-agent LLM document assessment with deterministic arbitration.

Public surface::

    from tribunal import (
        load_rubric, Submission, Evidence,
        MockLLM, OpenAIClient, AnthropicClient,
        Scorer, Reviewer, ConsensusOrchestrator, ConsensusConfig,
        ReviewPipeline, GateEvaluator, Validator, EscalationQueue,
    )
"""

from .agents import (
    AnthropicClient,
    ConsensusConfig,
    ConsensusOrchestrator,
    LLMClient,
    MockLLM,
    OpenAIClient,
    Reviewer,
    Scorer,
)
from .domain import (
    Assessment,
    Evidence,
    Grade,
    ProjectScore,
    Provenance,
    Rubric,
    ScoringUnit,
    Submission,
    TransmissionRule,
    UnitScore,
    UnitType,
    VetoRule,
)
from .hitl import EscalationQueue, EscalationTicket
from .pipeline import GateEvaluator, ReviewPipeline
from .rubric import band, grade_of, is_legal, load_rubric
from .validation import Validator

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # rubric
    "load_rubric",
    "band",
    "grade_of",
    "is_legal",
    "Rubric",
    "ScoringUnit",
    "UnitType",
    "VetoRule",
    "TransmissionRule",
    "Grade",
    # submission / assessment
    "Submission",
    "Evidence",
    "Assessment",
    "ProjectScore",
    "UnitScore",
    "Provenance",
    # agents
    "LLMClient",
    "MockLLM",
    "OpenAIClient",
    "AnthropicClient",
    "Scorer",
    "Reviewer",
    "ConsensusOrchestrator",
    "ConsensusConfig",
    # pipeline / validation / hitl
    "ReviewPipeline",
    "GateEvaluator",
    "Validator",
    "EscalationQueue",
    "EscalationTicket",
]
