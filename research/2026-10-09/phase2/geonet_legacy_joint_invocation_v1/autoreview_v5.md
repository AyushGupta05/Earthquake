autoreview findings: 1
[P2] [P2] Handle interruptions during final receipt writing
supervisor.py:207
The final receipt write and close occur in `finally`, outside the `BaseException` handler. If SIGINT raises `KeyboardInterrupt` after the complete receipt has been flushed but before the post-close elapsed check, supervision exits with `receipt.json` still declaring `complete: true`. This also bypasses overrun invalidation when receipt close consumed the remaining time. Because publication eligibility depends on that receipt, an interrupted invocation can retain an eligible aggregate, contrary to the protocol's failure handling. Protect finalization and invalidate only the owned, inode-verified receipt before propagating the interruption.

overall: patch is incorrect (0.91)
Final receipt handling can leave a complete publication receipt after an interruption bypasses the elapsed-time check. Review used read-only inspection of the supplied snapshot; no tests or actual invocation were run.
