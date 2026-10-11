autoreview findings: 2
[P2] Validate four ordered diagnostics before marking completion
supervisor.py:192
Only the envelope's top-level keys and protocol ID are validated. An invented child returning `private: {}` and `public_aggregate: {}` is therefore marked complete despite returning no diagnostics; the existing lifecycle fixtures explicitly exercise this acceptance. Arbitrary public fields are also copied unchanged. Before publication and completion, validate the four ordered slot rows and the declared aggregate keys, count types and fixed false flags.

[P2] Validate every body path before beginning body reads
child_harness.py:81
`validate_slot` accepts any string as `body_path`, so canonical absolute-path schema checks happen only when each body is read. In an invented four-slot plan with valid first three paths and a relative fourth path, `validate_gate` succeeds and `run` reads and decodes the first three bodies before rejecting the fourth. This violates the stated requirement that all slot checks pass before any body read. Validate canonical absolute paths for all four slots during the gate, retaining the reader's checks when opening each file.

overall: patch is incorrect (0.94)
The implementation leaves two declared gates incomplete: supervisor completion does not establish that four diagnostics returned, and body-path schema failures can be discovered after earlier body reads. Review used source and permitted runtime metadata only; no tests or actual-input processing were performed.
