# NEW pure numbered transport auditor

`auditor.py` independently replays the authored V6 two-literal1/2 transport accounting contract. It reads only caller-supplied exact bytes through a bounded callback. It cannot acquire, enumerate files, decode waves, verify scientific prerequisites or authorize an actual invocation.

Run the invented-only focused lane with Python3.14.5:

```sh
python3.14 -B -Werror -m unittest -v test_auditor
```

The source adapts frozen independent auditor V4, preserving useful adversarial framing/hash/clock/finalization/strict JSON tests and adding V6 pair, prerequisite, cardinality and failure-mask checks. No collector implementation/tests or actual inputs were read. See PROTOCOL.md and byte-exact public_contract/ for the normative boundary. Earlier results remain unchanged. Source publication and the parent's new private custody/authority gate remain required before actual replay.
