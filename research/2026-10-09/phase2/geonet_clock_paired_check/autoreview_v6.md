autoreview findings: 1
[P2] [P2] Preserve child ownership when cancellation interrupts launch
work/geonet_clock_paired_check/paired.py:370
SIGTERM or the soft SIGALRM can raise after the OS creates the child but before `Popen` returns and assigns `process`. In that window, `process` remains `None`, so `stop_child`, the hard watchdog and the final cleanup cannot terminate or wait for the worker. Recovery can consequently run while the child is still writing, and the child can continue acquisition after cancellation. The [pinned CPython constructor](https://raw.githubusercontent.com/python/cpython/v3.14.5/Lib/subprocess.py) closes descriptors on this exception path but does not terminate the spawned child. Defer cancellation exceptions across launch until the child handle is retained, then stop and reap that child before recovery.

overall: patch is incorrect (0.94)
The launch cancellation race violates the owned-child termination and recovery-after-exit guarantees. Review used read-only inspection; no tests, acquisition or private-data access were performed.
