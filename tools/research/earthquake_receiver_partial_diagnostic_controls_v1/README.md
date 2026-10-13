# Prospective partial diagnostic wrapper custody

Source-only packet for parent-owned no-refit diagnostic replay. wrapper.py is an exact copy of the unlaunched /tmp wrapper; child.py and remote.py are exact AST literal extracts for readable review. Never import/execute wrapper.py, child.py or remote.py in this source-test lane. test_controls.py extracts only selected definitions/manager boundaries and executes them with invented temporary files and mocked subprocesses. No referenced real input/source/runtime file was read.

23 invented tests pass, zero skips, approximately0.08seconds on local Python3.10. Source syntax is compiled only. Test command: python -m unittest discover -s <packet-directory> -p test_*.py -v. No SSH/AWS/model loading/fit was executed.
