# Prospective diagnostic controls V2

V2 changes only the parent public controls-publication receipt path in wrapper.py. Root creates that receipt after publishing V2 source and Linux proof, before actual invocation. Original trained fit_proof commit/source pins and every scientific, mathematical, custody, deadline and partial-artifact operation are unchanged. V1 remains frozen and unchanged. Do not execute/import wrapper.py, child.py or remote.py in source tests; tests use AST-only extraction and invented temporary files/mocked subprocesses. See ORIGIN.md for exact source provenance.

24 invented tests PASS, zero skips, approximately0.091seconds local Python3.10: `python -m unittest discover -s <packet-directory> -p test_*.py -q`. Root Linux synthetic verification remains separate from code review.
