autoreview findings: 2
[P2] [P2] Verify retained trace identities before qualifying literal ENZ
supervisor.py:110
The retained NSLC is checked only for four strings, so it need not agree with observed_nslc or the component suffix. In an invented valid envelope, changing the Z trace's retained channel from HHZ to HH1 still passes validate_result and leaves Z and joint availability counts unchanged. This lets contradictory identity evidence pass the publication gate. Validate retained identities against observed_nslc and the literal E/N/Z correspondence before accepting qualified components.

[P2] [P2] Validate component primitives for every availability state
supervisor.py:205
Primitive validation and trace reconstruction run only when available is true. An invented envelope with incomplete cores containing samples=-1, finite="invalid", and an extra field, decoded_traces="invalid", and an extra decoded-row field passes validate_result after recomputing joint/public counts. The supervisor can therefore mark malformed diagnostics complete despite the required schema and primitive checks. Enforce decoded-row and core schemas, types, and applicable consistency checks for incomplete and unknown cells as well as available cells.

overall: patch is incorrect (0.99)
The immutable hashes match, and the qualification arithmetic preserves the intended fixed windows and joint lattice rules. However, two narrow invented reproductions confirm that the supervisor accepts contradictory literal identity evidence and malformed incomplete diagnostics, weakening the required publication validation gate.
