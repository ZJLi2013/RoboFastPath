from copy import deepcopy

from robofastpath.robojev import code_predicates, compose_intent, decide, motion


def state() -> dict:
    return {
        "robot": {"held_object": None, "tcp_position": [0.0, 0.0, 0.04]},
        "objects": [{"id": "cube", "position": [0.0, 0.0, 0.02]}],
        "relations": {
            "cube_inside_target_xy": False,
            "cube_resting_height": False,
            "cube_clear_of_table_for_transport": False,
            "grasp_tcp_from_tcp": {
                "xy_aligned": False,
                "directions": {"x": "positive", "y": "negative", "z": "negative"},
            },
            "target_from_cube": {
                "xy_aligned": False,
                "directions": {"x": "negative", "y": "positive", "z": "zero"},
            },
            "placement_tcp_from_tcp": {
                "directions": {"x": "zero", "y": "zero", "z": "negative"}
            },
        },
    }


def test_intent_table_covers_pick_and_place_stages() -> None:
    base = {
        "holding_cube": False,
        "cube_in_target": False,
        "cube_resting": False,
        "grasp_ready": False,
        "target_xy_aligned": False,
        "transport_clear": False,
        "placement_z_aligned": False,
        "withdraw_clear": False,
    }
    cases = [
        ({}, "approach"),
        ({"grasp_ready": True}, "grasp"),
        ({"holding_cube": True}, "lift"),
        ({"holding_cube": True, "transport_clear": True}, "carry"),
        ({"holding_cube": True, "target_xy_aligned": True}, "lower"),
        (
            {
                "holding_cube": True,
                "target_xy_aligned": True,
                "placement_z_aligned": True,
            },
            "release",
        ),
        ({"cube_in_target": True, "cube_resting": True}, "withdraw"),
        (
            {
                "cube_in_target": True,
                "cube_resting": True,
                "withdraw_clear": True,
            },
            "finish",
        ),
    ]
    for updates, expected in cases:
        assert compose_intent(base | updates)[0] == expected


def test_approach_descends_only_after_xy_alignment() -> None:
    snapshot = state()
    assert motion("approach", snapshot) == {
        "x": "positive",
        "y": "negative",
        "z": "zero",
        "gripper": "open",
    }
    snapshot["relations"]["grasp_tcp_from_tcp"]["xy_aligned"] = True
    assert motion("approach", snapshot)["z"] == "negative"


def test_uncertain_consulted_predicate_holds_position() -> None:
    snapshot = state()
    predicates = code_predicates(snapshot)
    predicates["grasp_ready"]["uncertain"] = True
    step = decide(predicates, snapshot)
    assert step["intent"] == "approach"
    assert step["uncertain"] == ["grasp_ready"]
    assert step["action"] == {
        "x": "zero",
        "y": "zero",
        "z": "zero",
        "gripper": "hold",
    }


def test_withdraw_threshold_is_inclusive() -> None:
    snapshot = state()
    snapshot["objects"][0]["position"][2] = 0.0
    below = deepcopy(snapshot)
    below["robot"]["tcp_position"][2] = 0.0999
    boundary = deepcopy(snapshot)
    boundary["robot"]["tcp_position"][2] = 0.1
    assert code_predicates(below)["withdraw_clear"]["value"] is False
    assert code_predicates(boundary)["withdraw_clear"]["value"] is True
