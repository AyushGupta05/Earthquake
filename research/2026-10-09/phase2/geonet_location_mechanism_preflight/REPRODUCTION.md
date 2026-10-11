# Recovered Python source and exact replay

The original calculation, warning-check and explicit-case tool cells are preserved verbatim as inert `original_*_cell.py.txt` source artifacts. Do not execute these directly: their historical output-root assignments are retained as provenance. [reproduce.py](reproduce.py) verifies source/protocol/reference hashes, changes only that root assignment in the compiled AST, and writes into a newly reserved `local_runs/<run-name>` directory. No arithmetic, seeds, distributions, controls, scores or gates are changed. Existing outputs, symlinks and unsafe path names are rejected.

The first execution did not save a source-byte hash. These source artifacts were recovered afterward from the retained tool-call text, so there is no earlier cryptographic source pin. The new hashes plus successful output replay are evidence of recovery; they are not a claim that a Python file existed at the original execution. The original REPORT/HANDOFF/manifest describe that earlier state and remain unchanged.

From this directory, use the exact original environment:

```sh
/Users/ayush/.venvs/ml/bin/python3 -m unittest -v test_reproduce.py
/Users/ayush/.venvs/ml/bin/python3 reproduce.py --run-name replay_new
```

Python3.10.20, NumPy2.2.6 and SciPy1.15.3 reproduced the twelve panels and seven arms. `local_runs/replay_v2/REPLAY_COMPARISON.json` verifies that CALCULATIONS.json, WARNING_CHECK.json and ANALYTIC_CASES.json are all **byte-identical** to the immutable originals. It also verifies source/protocol/reference bytes remain unchanged. No result or floating warning was fixed away. The three original matrix warnings recur and remain in replay stderr.

Semantic comparison excludes only CALCULATIONS.runtime and WARNING_CHECK.checked_calculations_sha256, whose derived link is separately checked against its own body. Every scientific float, all component cases, warnings, thresholds and pass/fail fields are compared exactly without rounding. This replay needed no exclusions because full bytes matched. A different numerical runtime can fail comparison; retain that mismatch and do not overwrite the reference.

The initial `replay_v1` attempt used the directory's bare Python3.14 environment, which lacks NumPy, and failed before calculation. Its failed receipt/stderr remain ignored locally; this was not a scientific result or a replacement draw. Use the explicit original interpreter. Runtime dependency compatibility is reported by execution/comparison rather than silently installed.

Twelve focused tests check the linear ElogR identity with correlated noise, common-source covariance/impossible combinations, no one-report timing information, joint posterior versus independent quadrature, analytic Gaussian CRPS, mixture/mean distinctions, exact AST redirection, source-pin rejection, no-overwrite/path/symlink ownership and narrow semantic exclusions. Code-only autoreview covers the safe runner, tests, recovered inert cells, invented reference artifacts and frozen protocol. Its receipt is separate from the original scientific manifest. No real data, model fitting or AWS is involved.
