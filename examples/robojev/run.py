from __future__ import annotations

import os
import sys

from jev_vla_sim import mujoco_cli, policy
from jev_vla_sim.mujoco_cli import main

from examples.robojev.policy import FastPathPolicy


def _use_local_endpoint() -> None:
    original_init = policy.JevPolicy.__init__

    def local_init(self, config, *args, **kwargs):
        object.__setattr__(config, "api_url", os.environ["ROBOFASTPATH_URL"])
        object.__setattr__(config, "model", os.environ["ROBOFASTPATH_MODEL"])
        original_init(self, config, *args, **kwargs)

    policy.JevPolicy.__init__ = local_init


mode = os.environ.get("ROBOFASTPATH_MODE", "native")
if mode == "native":
    _use_local_endpoint()
elif mode in {"code", "mixed"}:
    mujoco_cli.JevPolicy = lambda config: FastPathPolicy(config, mode)
else:
    raise ValueError(f"unsupported ROBOFASTPATH_MODE: {mode}")


if __name__ == "__main__":
    sys.exit(main())
