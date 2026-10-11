autoreview findings: 1
[P2] [P2] Disable site startup until the runtime inventory is verified
supervisor.py:117
Launching with `-I -B` still processes site-packages `.pth` files before the child reaches its start gate or `verify_runtime()`. The documented runtime contains `distutils-precedence.pth`, which imports `_distutils_hack` during startup. Consequently, changes to either file execute before their pinned hashes are checked. A narrow invented reproduction is a temporary venv containing a `.pth` import line that writes an `INVENTED` marker to stderr: the marker appears even with no start-gate byte and an invalid authorization. Rejecting the inventory afterward cannot undo arbitrary code execution or private-file reads. Start with site initialization disabled, then expose the scientific package directory only after authorization and inventory verification.

overall: patch is incorrect (0.96)
The runtime launch executes unverified site-packages startup code before the authorization gate, undermining the declared runtime pinning and read boundary. Source and allowed dependency files were inspected; no tests were run.
