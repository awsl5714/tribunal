"""Pluggable LLM backends.

Two real backends (OpenAI / Anthropic) and a deterministic mock so the whole
pipeline — and the test suite — runs with no API keys and no network. The mock
is seeded from the prompt hash, so the same submission always yields the same
"scores", which keeps demos and CI reproducible.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str


class LLMClient(ABC):
    """Minimal chat interface every backend implements."""

    name: str = "llm"

    @abstractmethod
    def complete(self, system: str, user: str, *, temperature: float = 0.0) -> LLMResponse:
        ...

    @staticmethod
    def extract_json(text: str) -> dict:
        """Best-effort JSON extraction from a model reply."""
        # fenced block first
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        blob = m.group(1) if m else None
        if blob is None:
            m = re.search(r"(\{.*\})", text, re.DOTALL)
            blob = m.group(1) if m else None
        if blob is None:
            raise ValueError(f"no JSON object found in reply: {text[:200]!r}")
        return json.loads(blob)


class MockLLM(LLMClient):
    """Deterministic offline stand-in.

    It never *decides* scores in a meaningful sense — it produces stable
    pseudo-grades from a hash so pipeline plumbing can be exercised end to end.
    A ``bias`` lets the two mock agents disagree a little, which exercises the
    consensus/escalation paths.
    """

    def __init__(self, name: str = "mock", bias: int = 0):
        self.name = name
        self.bias = bias

    _GRADES = ["outstanding", "excellent", "good", "fair", "pass", "fail"]

    def complete(self, system: str, user: str, *, temperature: float = 0.0) -> LLMResponse:
        max_score = _parse_max(user)
        grade, score = self._judge(user, max_score)

        # Reviewer prompts embed the first assessor's grade; when present the
        # mock produces a verdict by comparing its own judgement to that grade,
        # so the challenge/escalation paths are genuinely exercised offline.
        m = re.search(r"First assessor said: grade=([a-z]+)", user)
        if m:
            scorer_grade = m.group(1)
            gap = abs(self._GRADES.index(grade) - self._GRADES.index(scorer_grade))
            payload = {
                "verdict": "agree" if gap <= 1 else "challenge",
                "grade": grade,
                "score": score,
                "reason": f"[{self.name}] mock audit (rank gap {gap})",
                "confidence": 0.7,
            }
        else:
            payload = {
                "grade": grade,
                "score": score,
                "rationale": f"[{self.name}] deterministic mock judgement for review plumbing",
                "evidence_locator": "p.1",
                "confidence": 0.7,
            }
        return LLMResponse(text=json.dumps(payload, ensure_ascii=False), model=self.name)

    def _judge(self, user: str, max_score: float) -> tuple[str, float]:
        from ..domain.rubric import Grade
        from ..rubric.grade_bands import band

        # Seed on the *unit* only (a shared pseudo-ground-truth), not on the
        # agent name or role framing. Two agents then differ solely by their
        # ``bias`` — a small bias gap yields agreement (consensus), a large gap
        # yields a challenge (and eventual escalation). This keeps the offline
        # demo realistic and fully controllable.
        unit_key = _parse_unit_key(user)
        seed = int(hashlib.sha256((unit_key + str(max_score)).encode()).hexdigest(), 16)
        idx = max(0, min(5, 1 + (seed % 4) + self.bias))
        grade = self._GRADES[idx]
        low, high = band(max_score, Grade(grade))
        score = round(low + (high - low) * ((seed >> 8) % 100) / 100.0, 1)
        return grade, score


class OpenAIClient(LLMClient):
    """GPT backend (used as the primary *scorer* in the reference setup)."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        self.name = model
        self.model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def complete(self, system: str, user: str, *, temperature: float = 0.0) -> LLMResponse:
        from openai import OpenAI  # imported lazily; optional dependency

        client = OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return LLMResponse(text=resp.choices[0].message.content or "", model=self.model)


class AnthropicClient(LLMClient):
    """Claude backend (used as the independent *reviewer* in the reference setup)."""

    def __init__(self, model: str = "claude-sonnet-4-5", api_key: str | None = None):
        self.name = model
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def complete(self, system: str, user: str, *, temperature: float = 0.0) -> LLMResponse:
        import anthropic  # imported lazily; optional dependency

        client = anthropic.Anthropic(api_key=self._api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        return LLMResponse(text=text, model=self.model)


def _parse_max(user_prompt: str) -> float:
    m = re.search(r"max_score\s*[:=]\s*([0-9.]+)", user_prompt)
    return float(m.group(1)) if m else 10.0


def _parse_unit_key(user_prompt: str) -> str:
    m = re.search(r"unit_key\s*[:=]\s*(\S+)", user_prompt)
    return m.group(1) if m else user_prompt[:32]
