from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

INTENT_ORDER = (
    "approach",
    "grasp",
    "lift",
    "carry",
    "lower",
    "release",
    "withdraw",
    "finish",
)


def summarize(episode: Path) -> None:
    result = json.loads((episode / "result.json").read_text())
    records = [
        json.loads(line)
        for line in (episode / "steps.jsonl").read_text().splitlines()
    ]
    decisions = [record for record in records if record.get("event") == "decision"]
    metadata = [record["decision_metadata"] for record in decisions]
    first = {}
    for index, item in enumerate(metadata):
        first.setdefault(item["intent"], index)
    first_held = next(
        (
            index
            for index, record in enumerate(decisions)
            if record["state"]["robot"]["held_object"] == "cube"
        ),
        None,
    )
    divergence = next(
        (
            index
            for index, item in enumerate(metadata)
            if item["intent"] != item["shadow_intent"]
        ),
        None,
    )
    uncertain = sum(bool(item["uncertain"]) for item in metadata)
    latencies = sorted(item["latency_ms"] for item in metadata)
    tokens = sum(item["usage"]["input_tokens"] for item in metadata)

    print(f"\n== {episode.parent.name}/{episode.name}  policy {metadata[0]['policy']}")
    print(
        f"success={result['success']} end_reason={result['end_reason']} "
        f"decisions={result['decisions']} rejected={result['rejected']} "
        f"empty_grasps={result['empty_grasps']} "
        f"direction_reversals={result['direction_reversals']}"
    )
    print(
        "first decision per intent:",
        " -> ".join(f"{name}@{first[name]}" for name in INTENT_ORDER if name in first),
    )
    print(
        f"cube first held at decision: {first_held}; uncertainty holds: {uncertain}; "
        f"first divergence from shadow code intent: {divergence}; "
        f"intents {dict(Counter(item['intent'] for item in metadata))}"
    )
    if latencies and latencies[-1] > 0:
        print(
            f"predicate latency p50 {latencies[len(latencies) // 2]:.0f} ms / "
            f"p95 {latencies[int(len(latencies) * 0.95)]:.0f} ms; "
            f"input tokens per decision {tokens / len(metadata):.0f}"
        )


if __name__ == "__main__":
    for path in map(Path, sys.argv[1:]):
        episodes = [path] if (path / "result.json").is_file() else [
            result.parent for result in sorted(path.glob("**/result.json"))
        ]
        for episode in episodes:
            summarize(episode)
