#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORK=${WORK:-"$ROOT/.work"}
ROBOJEV_DIR=${ROBOJEV_DIR:-"$WORK/RoboJEV"}
VENV=${VENV:-"$WORK/venv"}
OUT=${OUT:-"$ROOT/results/robojev"}
COMMIT=${COMMIT:-707cfeca5025b4af3e521612482c6d7bae55c09b}
SEED=${SEED:-2000}
EPISODES=${EPISODES:-10}
MUJOCO_GL=${MUJOCO_GL:-osmesa}
PYTHON="$VENV/bin/python"

setup() {
    mkdir -p "$WORK" "$OUT"
    if [[ ! -d "$ROBOJEV_DIR/.git" ]]; then
        git clone https://github.com/lykycy123/RoboJEV.git "$ROBOJEV_DIR"
    fi
    git -C "$ROBOJEV_DIR" checkout --detach "$COMMIT"
    if [[ ! -x "$PYTHON" ]]; then
        python3 -m venv "$VENV"
    fi
    "$PYTHON" -m pip install --upgrade pip
    "$PYTHON" -m pip install -e "$ROOT[test]" -e "$ROBOJEV_DIR[test,video]"
    (
        cd "$ROBOJEV_DIR"
        "$PYTHON" scripts/fetch_panda.py
    )
}

run_condition() {
    local mode=$1
    if [[ "$mode" != "code" ]]; then
        : "${ROBOFASTPATH_URL:?set ROBOFASTPATH_URL to a /v1/systemone endpoint}"
        : "${ROBOFASTPATH_MODEL:?set ROBOFASTPATH_MODEL to its served model name}"
    fi
    mkdir -p "$OUT/$mode"
    PYTHONPATH="$ROOT" \
        MUJOCO_GL="$MUJOCO_GL" \
        TYPESAFE_API_KEY=local \
        ROBOFASTPATH_MODE="$mode" \
        "$PYTHON" "$ROOT/examples/robojev/run.py" \
        --task pick_place \
        --policy jev \
        --seed "$SEED" \
        --episodes "$EPISODES" \
        --env-file /nonexistent \
        --output "$OUT/$mode"
}

case "${1:-}" in
setup)
    setup
    ;;
rule)
    MUJOCO_GL="$MUJOCO_GL" "$VENV/bin/robojev" \
        --task pick_place --policy rule --seed "$SEED" --episodes "$EPISODES" \
        --output "$OUT/rule"
    ;;
native|code|mixed)
    run_condition "$1"
    ;;
analyze)
    PYTHONPATH="$ROOT" "$PYTHON" "$ROOT/examples/robojev/analyze.py" \
        "$OUT/code" "$OUT/mixed"
    ;;
*)
    echo "usage: $0 {setup|rule|native|code|mixed|analyze}" >&2
    exit 2
    ;;
esac
