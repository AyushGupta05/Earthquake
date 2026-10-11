autoreview findings: 1
[P1] P1: Disable site startup until the runtime inventory is verified
supervisor.py:117
`-I -B` still enables Python's site initialization, including executable `.pth` lines and `sitecustomize`, before the child reaches its start gate or `verify_runtime()`. The documented inventory contains `distutils-precedence.pth`, which imports `_distutils_hack` during startup, so installed code executes before its digest is checked. A narrow invented reproduction is a disposable runtime fixture with a `.pth` line `import os; os.write(1, b'PTH_SENTINEL\n')`: the sentinel executes even with the start gate withheld and unchanged expected inventory hashes. Subsequent inventory rejection cannot undo filesystem or network actions performed by that startup code. Launch with site startup disabled and enable the required package paths only after the gate and inventory verification, without executing unverified startup hooks.

overall: patch is incorrect (0.98)
The runtime pinning boundary permits installed startup code to execute before authorization and inventory verification. The prescribed core digest matches. Review was read-only; tests were not run, as requested.
