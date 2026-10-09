from __future__ import annotations

from collections.abc import Callable, Mapping

from robofastpath.systemone import SystemOneClient

THRESHOLD = 0.5
UNCERTAIN = (0.35, 0.65)
WITHDRAW_HEIGHT_M = 0.10

PredicateFn = Callable[[dict], bool]


def _cube(state: dict) -> dict:
    matches = [obj for obj in state["objects"] if obj["id"] == "cube"]
    if len(matches) != 1:
        raise ValueError(f"expected one cube, found {len(matches)}")
    return matches[0]


def _withdraw_clear(state: dict) -> bool:
    return state["robot"]["tcp_position"][2] - _cube(state)["position"][2] >= WITHDRAW_HEIGHT_M


PREDICATES: dict[str, tuple[str | None, PredicateFn]] = {
    "holding_cube": (
        'Is state.robot.held_object equal to "cube"?',
        lambda state: state["robot"]["held_object"] == "cube",
    ),
    "cube_in_target": (
        "Is state.relations.cube_inside_target_xy true?",
        lambda state: bool(state["relations"]["cube_inside_target_xy"]),
    ),
    "cube_resting": (
        "Is state.relations.cube_resting_height true?",
        lambda state: bool(state["relations"]["cube_resting_height"]),
    ),
    "grasp_ready": (
        "Are state.relations.grasp_tcp_from_tcp.directions x, y and z all equal to zero?",
        lambda state: all(
            value == "zero"
            for value in state["relations"]["grasp_tcp_from_tcp"]["directions"].values()
        ),
    ),
    "target_xy_aligned": (
        "Is state.relations.target_from_cube.xy_aligned true?",
        lambda state: bool(state["relations"]["target_from_cube"]["xy_aligned"]),
    ),
    "transport_clear": (
        "Is state.relations.cube_clear_of_table_for_transport true?",
        lambda state: bool(state["relations"]["cube_clear_of_table_for_transport"]),
    ),
    "placement_z_aligned": (
        "Is state.relations.placement_tcp_from_tcp.directions.z equal to zero?",
        lambda state: state["relations"]["placement_tcp_from_tcp"]["directions"]["z"] == "zero",
    ),
    "withdraw_clear": (None, _withdraw_clear),
}

PREDICATE_SOURCES = {name: "noul" for name in PREDICATES} | {"withdraw_clear": "code"}
HOLD = {"x": "zero", "y": "zero", "z": "zero", "gripper": "hold"}


def compose_intent(predicates: Mapping[str, bool]) -> tuple[str, list[str]]:
    if not predicates["holding_cube"]:
        if predicates["cube_in_target"] and predicates["cube_resting"]:
            return (
                "finish" if predicates["withdraw_clear"] else "withdraw",
                ["holding_cube", "cube_in_target", "cube_resting", "withdraw_clear"],
            )
        consulted = ["holding_cube", "cube_in_target"]
        if predicates["cube_in_target"]:
            consulted.append("cube_resting")
        return (
            "grasp" if predicates["grasp_ready"] else "approach",
            consulted + ["grasp_ready"],
        )
    if predicates["target_xy_aligned"]:
        return (
            "release" if predicates["placement_z_aligned"] else "lower",
            ["holding_cube", "target_xy_aligned", "placement_z_aligned"],
        )
    return (
        "carry" if predicates["transport_clear"] else "lift",
        ["holding_cube", "target_xy_aligned", "transport_clear"],
    )


def motion(intent: str, state: dict) -> dict[str, str]:
    relations = state["relations"]
    grasp = relations["grasp_tcp_from_tcp"]
    target = relations["target_from_cube"]
    action = {"x": "zero", "y": "zero", "z": "zero"}
    if intent == "approach":
        action.update(x=grasp["directions"]["x"], y=grasp["directions"]["y"])
        if grasp["xy_aligned"]:
            action["z"] = grasp["directions"]["z"]
    elif intent == "carry":
        action.update(x=target["directions"]["x"], y=target["directions"]["y"])
    elif intent in {"lift", "withdraw"}:
        action["z"] = "positive"
    elif intent == "lower":
        action["z"] = relations["placement_tcp_from_tcp"]["directions"]["z"]
    action["gripper"] = (
        "close"
        if intent == "grasp"
        else "hold"
        if intent in {"lift", "carry", "lower"}
        else "open"
    )
    return action


def code_predicates(state: dict) -> dict[str, dict]:
    return {
        name: {"value": evaluate(state), "p_true": None, "source": "code"}
        for name, (_, evaluate) in PREDICATES.items()
    }


def model_predicates(
    client: SystemOneClient,
    state: dict,
    sources: Mapping[str, str] = PREDICATE_SOURCES,
) -> tuple[dict[str, dict], dict]:
    predicates = {
        name: result
        for name, result in code_predicates(state).items()
        if sources[name] == "code"
    }
    questions = {
        name: {"type": "noul", "instructions": PREDICATES[name][0]}
        for name, source in sources.items()
        if source == "noul"
    }
    response = client.evaluate(state, questions)
    for name, source in sources.items():
        if source != "noul":
            continue
        probability = float(response.answers[name]["noul"])
        predicates[name] = {
            "value": probability >= THRESHOLD,
            "p_true": probability,
            "source": "noul",
            "uncertain": UNCERTAIN[0] < probability < UNCERTAIN[1],
        }
    return predicates, {
        "latency_ms": response.latency_ms,
        "input_tokens": response.input_tokens,
        "response": response.payload,
    }


def decide(predicates: Mapping[str, dict], state: dict) -> dict:
    values = {name: item["value"] for name, item in predicates.items()}
    intent, consulted = compose_intent(values)
    uncertain = [name for name in consulted if predicates[name].get("uncertain")]
    return {
        "intent": intent,
        "consulted": consulted,
        "uncertain": uncertain,
        "action": dict(HOLD) if uncertain else motion(intent, state),
    }
