from __future__ import annotations

import os

from jev_vla_sim.types import EefDecision

from robofastpath.robojev import (
    PREDICATE_SOURCES,
    code_predicates,
    decide,
    model_predicates,
)
from robofastpath.systemone import SystemOneClient


class FastPathPolicy:
    def __init__(self, config, mode: str) -> None:
        if mode not in {"code", "mixed"}:
            raise ValueError(f"unsupported mode: {mode}")
        self.mode = mode
        self.client = (
            SystemOneClient(
                os.environ["ROBOFASTPATH_URL"],
                os.environ["ROBOFASTPATH_MODEL"],
                timeout=config.api_timeout_s,
            )
            if mode == "mixed"
            else None
        )
        self.last_exchange: dict = {}

    def close(self) -> None:
        if self.client is not None:
            self.client.close()

    def decide(self, state) -> EefDecision:
        snapshot = state.to_dict()
        exact = code_predicates(snapshot)
        shadow = decide(exact, snapshot)
        if self.mode == "code":
            predicates = exact
            step = shadow
            metadata = {"latency_ms": 0.0, "input_tokens": 0}
        else:
            predicates, metadata = model_predicates(self.client, snapshot)
            step = decide(predicates, snapshot)
        sources = (
            PREDICATE_SOURCES
            if self.mode == "mixed"
            else {name: "code" for name in PREDICATE_SOURCES}
        )
        self.last_exchange = {
            "attempts": 0 if self.mode == "code" else 1,
            "fastpath": {
                "mode": self.mode,
                "sources": sources,
                "predicates": predicates,
                "step": step,
                "shadow_code_step": shadow,
                "latency_ms": metadata["latency_ms"],
            },
        }
        return EefDecision(
            state.state_id,
            **step["action"],
            metadata={
                "policy": f"fastpath_{self.mode}",
                "intent": step["intent"],
                "shadow_intent": shadow["intent"],
                "uncertain": step["uncertain"],
                "latency_ms": metadata["latency_ms"],
                "usage": {
                    "input_tokens": metadata["input_tokens"],
                    "output_tokens": 0,
                },
            },
        )
