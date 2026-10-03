"""Deterministic mock backend — tests, demos, and `--backend mock`."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from ..decisions.envelope import (
    Answer,
    SystemOneRequest,
    SystemOneResponse,
)
from .base import Health


class MockBackend:
    id = "mock"

    def load(self) -> None:
        pass

    def _dist(self, seed_text: str, options: list[str]) -> dict[str, float]:
        """Stable pseudo-distribution: same input → same numbers."""
        rng = random.Random(int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:8], 16))
        raw = [rng.random() + 0.35 for _ in options] or [1.0]
        total = sum(raw)
        probs = [r / total for r in raw]
        # sharpen the top so `auto` is reachable with default thresholds
        top = probs.index(max(probs))
        probs[top] += 0.30
        total = sum(probs)
        return {o: p / total for o, p in zip(options, probs, strict=False)}

    def system_one(self, req: SystemOneRequest) -> SystemOneResponse:
        state = req.state if isinstance(req.state, str) else str(req.state)
        answers: dict[str, Answer] = {}
        for name, q in req.questions.items():
            if q.type == "noul":
                probs = self._dist(f"{state}|{name}", ["yes", "no"])
                answers[name] = Answer(
                    type="noul", noul=probs["yes"] > probs["no"], probabilities=probs,
                    confidence=max(probs.values()),
                )
            elif q.type == "score":
                levels = list(q.criteria) if isinstance(q.criteria, (list, dict)) else \
                    [f"L{i}" for i in range(1, 6)]
                probs = self._dist(f"{state}|{name}", levels)
                best = max(probs, key=probs.get)
                idx = levels.index(best)
                answers[name] = Answer(
                    type="score", score=idx + 1, nearest_level=best,
                    probabilities=probs, confidence=probs[best],
                )
            else:  # choice
                options = list(q.criteria) if q.criteria else ["a", "b"]
                probs = self._dist(f"{state}|{name}", options)
                best = max(probs, key=probs.get)
                answers[name] = Answer(
                    type="choice", choice=best, probabilities=probs,
                    confidence=probs[best],
                )
        return SystemOneResponse(answers=answers, model="mock-1")

    def health(self) -> Health:
        return Health(status="ready", device="cpu", detail="deterministic mock")

    def close(self) -> None:
        pass

    def describe(self) -> dict[str, Any]:
        return {"name": self.id, "model": "mock-1", "remote": False, "ready": True}
