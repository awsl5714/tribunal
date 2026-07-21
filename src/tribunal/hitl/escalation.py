"""Human-in-the-loop escalation queue.

The system is explicitly *not* fully autonomous. Cases where the two assessors
never converge, a veto is ambiguous, or a validator error survives are routed
to a human with the full context needed to adjudicate — the reference project
kept ~15% of cases here rather than let the models guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.assessment import Assessment
from ..validation.validator import Finding


@dataclass
class EscalationTicket:
    candidate_id: str
    candidate_name: str
    reasons: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"[{self.candidate_id}] {self.candidate_name}"]
        for r in self.reasons:
            lines.append(f"  - {r}")
        for fnd in self.findings:
            lines.append(f"  ! {fnd.code} {fnd.severity.value}: {fnd.message}")
        return "\n".join(lines)


@dataclass
class EscalationQueue:
    tickets: list[EscalationTicket] = field(default_factory=list)

    def maybe_enqueue(
        self, assessment: Assessment, findings: list[Finding]
    ) -> EscalationTicket | None:
        reasons = list(assessment.escalations)
        error_findings = [f for f in findings if f.severity.value == "error"]

        if not reasons and not error_findings and not assessment.needs_human_review:
            return None

        ticket = EscalationTicket(
            candidate_id=assessment.candidate_id,
            candidate_name=assessment.candidate_name,
            reasons=reasons or ["validator errors present"],
            findings=error_findings,
        )
        self.tickets.append(ticket)
        return ticket

    @property
    def rate(self) -> float:
        """Fraction escalated — set by the caller against the batch size."""
        return len(self.tickets)
