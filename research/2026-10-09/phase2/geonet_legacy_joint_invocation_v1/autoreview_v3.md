autoreview findings: 1
[P2] Recheck the processing deadline before accepting child completion
supervisor.py:148
If handling the final pipe EOF events crosses `processing_deadline`, the selector loop exits because no streams remain registered, bypassing its deadline check. The subsequent `proc.wait()` still receives at least 1 ms and a successful exit becomes `candidate_complete` without another processing-deadline check. Promotion then checks only the later whole-invocation deadline, so a late child completion can receive a complete receipt using the reserved cleanup interval. Recheck `processing_deadline` before accepting the successful exit and retain an incomplete deadline receipt when it has elapsed.

overall: patch is incorrect (0.91)
The watchdog has a completion path that bypasses the documented processing deadline. The remaining reviewed source/input bindings, profile handling, and clock reconstruction appear consistent with the supplied contracts. Review used source inspection only; no tests, frozen modules, or actual invocation were executed.
