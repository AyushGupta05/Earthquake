"""Enable deterministic Torch execution before starting the unchanged TEAM runner.

Usage: python run_team_deterministic.py --determinism-audit NEW.json -- <runner args>

The audit file is required and must not exist; use a new file for each invocation,
including epoch recovery. The runner's checkpoint also records the resulting
determinism flags. This controls supported deterministic Torch operations within
a fixed runtime; it does not promise bitwise equivalence across GPUs, libraries,
drivers, or changes to the surrounding training/data-loading context.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--determinism-audit", type=Path, required=True)
    args, runner_args = parser.parse_known_args(argv)
    if runner_args[:1] == ["--"]:
        runner_args = runner_args[1:]
    if not runner_args:
        parser.error("Supply the TEAM runner arguments after --")
    if "torch" in sys.modules:
        raise RuntimeError("Launch in a fresh Python process before importing Torch")
    if args.determinism_audit.exists():
        raise FileExistsError("Use a new determinism audit path for each invocation")

    previous_workspace = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    import torch

    # Do not change TF32 or matmul precision. These flags select deterministic
    # algorithms and make unsupported nondeterministic operations raise errors.
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    wrapper = Path(__file__).resolve()
    runner = wrapper.with_name("train_team_lm.py")
    if not runner.is_file():
        raise FileNotFoundError(f"TEAM runner is missing: {runner}")
    audit = {
        "schema": "team-deterministic-launch-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "wrapper_sha256": hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
        "runner_path": str(runner),
        "runner_arguments": runner_args,
        "torch_version": str(torch.__version__),
        "torch_cuda": torch.version.cuda,
        "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
        "previous_cublas_workspace_config": previous_workspace,
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "deterministic_warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "cudnn_benchmark": torch.backends.cudnn.benchmark,
        "cuda_matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
        "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
    }
    args.determinism_audit.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents a repeated invocation from replacing its
    # provenance. Audit creation failure aborts before any training is started.
    with args.determinism_audit.open("x") as handle:
        handle.write(json.dumps(audit, indent=2, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    print("DETERMINISTIC_RUNTIME", json.dumps(audit, sort_keys=True), flush=True)
    sys.path.insert(0, str(runner.parent))
    sys.argv = [str(runner), *runner_args]
    runpy.run_path(str(runner), run_name="__main__")


if __name__ == "__main__":
    main()
