autoreview findings: 1
[P2] [P2] Terminate the child group when supervision is interrupted
supervisor.py:187
A SIGINT during supervision raises KeyboardInterrupt, which bypasses this Exception handler. The finally block only closes pipes and writes the receipt; it never terminates or waits for the child group. Because Popen uses start_new_session=True, the child does not receive the supervisor's terminal interrupt and can continue projecting after the watchdog exits, potentially beyond the invocation limit. Move group cleanup into an unconditional finalizer, or handle BaseException and re-raise after terminating and reaping the group.

overall: patch is incorrect (0.96)
The normal gate, timeout, bounds and clock reconstruction paths align with the supplied contracts, but interruption can leave the child running without supervision. Review used read-only source inspection; no tests or actual invocation were run.
