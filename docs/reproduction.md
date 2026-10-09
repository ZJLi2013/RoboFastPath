# Reproduce Decision-1.0-Nox-4B on RoboJEV

This reproduction keeps four boundaries fixed:

1. RoboJEV remains at commit `707cfec`.
2. Decision-1.0-Nox-4B remains at revision `0bb8335`.
3. Code and model predicates use the same intent table and action mapping.
4. RoboJEV's physical evaluator supplies the final task verdict.

The reference run used one AMD Instinct MI300X (`gfx942`) GPU. The pinned Nox
bundle validates this architecture before loading and rejects MI350X
(`gfx950`); do not bypass that check and call the result a reproduction.
MuJoCo rendering ran on the CPU through OSMesa. Other hardware and decision
providers can implement the same `/v1/systemone` contract, but they are not
part of the reported result.

## 1. Prepare RoboJEV

Install the system packages required by MuJoCo and Python virtual environments.
On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y git python3-venv libosmesa6
```

Then run:

```bash
git clone https://github.com/ZJLi2013/RoboFastPath.git
cd RoboFastPath
bash scripts/run_robojev.sh setup
```

The command creates `.work/`, checks out the pinned RoboJEV revision, installs
both projects in a virtual environment, and downloads the Franka Panda assets.

Verify the simulator and deterministic task path:

```bash
SEED=2000 EPISODES=1 bash scripts/run_robojev.sh rule
SEED=2000 EPISODES=1 bash scripts/run_robojev.sh code
```

Both conditions should end with `success: true`. If they fail, fix the shared
environment or task adapter before testing a model.

## 2. Serve Nox

Download the pinned model bundle:

```bash
python -m pip install "huggingface_hub[cli]"
huggingface-cli download \
  llm-semantic-router/Decision-1.0-Nox-4B \
  --revision 0bb833504965c0eabdb9630b7bbd385cb2fe5cd4 \
  --local-dir .work/Decision-1.0-Nox-4B \
  --exclude "assets/*"
```

Use the runtime prescribed by the model bundle. The reference run built
`Dockerfile.runtime` from that revision and mounted this repository plus the
downloaded model:

```bash
MODEL=$PWD/.work/Decision-1.0-Nox-4B
docker build -f "$MODEL/Dockerfile.runtime" -t decision-runtime:1.0 "$MODEL"

docker run --rm \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --ipc=host --shm-size=16g --security-opt seccomp=unconfined \
  -e HIP_VISIBLE_DEVICES=0 \
  -p 30001:30001 \
  -v "$PWD":/workspace:ro \
  -v "$MODEL":/model:ro \
  decision-runtime:1.0 \
  python3 /workspace/providers/nox/serve.py /model \
    --host 0.0.0.0 --port 30001 \
    --served-model-name Decision-1.0-Nox-4B
```

The server must print `matches_validated_runtime: true` in the loaded runtime
metadata. Do not silently enable an unvalidated runtime when reproducing the
reported result.

Probe the endpoint from another terminal:

```bash
curl -s http://127.0.0.1:30001/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Decision-1.0-Nox-4B",
    "state": {"held": false},
    "questions": {
      "holding": {
        "type": "noul",
        "instructions": "Is state.held true?"
      }
    }
  }'
```

## 3. Run the frozen conditions

Export the provider settings:

```bash
export ROBOFASTPATH_URL=http://127.0.0.1:30001/v1/systemone
export ROBOFASTPATH_MODEL=Decision-1.0-Nox-4B
```

The native condition uses RoboJEV's original two-stage `Choice` requests:

```bash
SEED=0 EPISODES=10 bash scripts/run_robojev.sh native
```

The code condition computes all predicates exactly. The mixed condition uses
Nox for seven direct field judgments and code only for `withdraw_clear`, which
requires subtraction:

```bash
bash scripts/run_robojev.sh code
bash scripts/run_robojev.sh mixed
bash scripts/run_robojev.sh analyze
```

Defaults are ten episodes starting at seed 2000. The seed is incremented by
RoboJEV for each episode. Run directories are separate and existing evidence is
not overwritten by a different condition.

## 4. Expected result

The frozen reference campaign produced:

- native Nox `Choice`: 0/10 on the earlier seeds 0–9;
- exact code predicates: 10/10 on seeds 2000–2009;
- seven Nox predicates plus one code predicate: 9/10 on seeds 2000–2009.

The mixed failure is seed 2000. At the grasp pose, all three geometric
directions were `zero`, but `grasp_ready` was repeatedly false. The exact code
condition completed the same seed.

Exact replication depends on the pinned model, runtime, RoboJEV revision, task
seeds, and threshold settings. Report deviations instead of replacing failed
episodes.

## 5. Add another decision provider

`robofastpath.systemone.SystemOneClient` expects:

```json
{
  "model": "provider-model-name",
  "state": {},
  "questions": {
    "question_id": {
      "type": "noul",
      "instructions": "A bounded yes/no question"
    }
  }
}
```

The response must contain `answers.<question_id>.noul` as a probability in
`[0, 1]`. A new provider can use any model or serving engine as long as it keeps
that boundary. Provider-specific setup belongs under `providers/`; task
composition does not change.
