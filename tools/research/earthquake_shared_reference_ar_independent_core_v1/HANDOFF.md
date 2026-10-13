# Independent L core V1 — first clean

28 invented local tests pass; default Codex review1 exits0/no findings, confidence0.87. Same7 reviewed source/context bytes as pending snapshot1. No code change, extra test or extra review after first clean.

Production minimum (load exact positively pinned proper_core then ar_core):
- ar_core.py9406B SHA256 8ace396641bb21aa1909b98a71493870cd2d5fed94ec3bf201e2943c3b7ac081
- proper_core.py13500B SHA256 d805dbccfcae42cd0867581a677f8e2b9d6531ccfe7b2c616b5f7bf73c7df6ca (unchanged frozen S/P/D independent math_core V2)

API.md defines the exact reference/source schema and shared duck-budget interface agreed with the producer author. build_reference derives explicit first1/later1-rho factors; complete independently derives and completes all factors; verify_source requires independently bound primitive inputs/prior bounds, not a producer-supplied authority flag. Mixture uses sd for scale and keeps the caller's10s/1M-point budget.

Target source-only command from this folder: python3 -B -m unittest discover -s . -p test_ar_core.py -v. Tests use NumPy/SciPy, no Torch/kernel/producer/model imports and no actual data, checkpoints, scores, cloud or optimizer. ROOT owns later target-runtime checks/publication/actual proof.

This core is not the full L auditor: independent static-network forward reconstruction, original initialization/scaler/capacity/history/custody checks, source/record retention, final proper forecast comparison and42-guard aggregate must still be implemented and reviewed separately under the frozen L protocol. No prediction, novelty or advancement claim follows.
