from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class DecisionResponse:
    answers: dict[str, Any]
    latency_ms: float
    input_tokens: int
    payload: dict[str, Any]


class SystemOneClient:
    def __init__(self, url: str, model: str, timeout: float = 120.0) -> None:
        self.url = url
        self.model = model
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def evaluate(self, state: dict, questions: dict) -> DecisionResponse:
        started = time.perf_counter()
        response = self._client.post(
            self.url,
            json={"model": self.model, "state": state, "questions": questions},
        )
        response.raise_for_status()
        payload = response.json()
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise ValueError("System One response does not contain an answers object")
        return DecisionResponse(
            answers=answers,
            latency_ms=1000 * (time.perf_counter() - started),
            input_tokens=int(payload.get("usage", {}).get("input_tokens", 0)),
            payload=payload,
        )
