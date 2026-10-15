# ROOT L primitives: first clean source packet

This is a public, source-only implementation. It issues no actual execution authority and contains no private inputs, observed account balances, weights, results, or cloud access. ROOT must provide the externally held exact root pin and independently issued narrow receipt documents described in PRIVATE_SCHEMA.md.

Use the flat root_primitives.py as the bootstrap composite member. It is byte-identical to the reviewed work/earthquake_shared_reference_ar_root_primitives_v1/root_primitives.py. `make_primitives(held, *, expected_root_pin, root_spec, modules, source_begin=None, clock=time.monotonic)` returns `(Primitives, Custody)`; pass `p.retain_return` as the concrete ROOT return retainer. The source has no import-time scientific or cloud work. Custody.snapshot is read-only.

Five primitives preserve the frozen root-glue ABI and reject mismatched evidence. They verify the full inherited source/runtime, live current gate and whole7200+200 stop readbacks, raw input receipt pins, complete original14 plus closed7 manager/journal custody, and L optimizer/probe custody before audit flags. Raw external observations retain original formatting only at the explicitly documented edges. New protocol controls remain canonical. Full runtime and historical checks are cached per positively anchored instance only with exact subsequent inventory/stat seals; clocks are never restarted or enlarged.

## Validation

35 invented focused tests pass using real frozen secure_io/control/journal/source_binding.source with fixture OS readbacks. Run from this directory:

    python3 -B -m unittest discover -s work/earthquake_shared_reference_ar_root_primitives_v1 -p test_primitives.py -v

TEST_v3.txt records the exact reviewed package run. Tests do not exercise the full target10112-file runtime, actual native data, provider account, actual historical stores, or a fit. Two audit tests use explicitly synthetic authenticated-input state to isolate retained300-step custody.

Required default Codex autoreview used the local helper with `--mode local --engine codex --no-web-search --prompt-file work/earthquake_shared_reference_ar_root_primitives_v1/REVIEW_CONTEXT.md`. The bundled Codex binary was selected because the global shim was broken; no model override was used. REVIEW_v3 is clean (exit0, no findings, confidence0.78). Reviewer performed source inspection, while TEST_v3 is the separate test evidence. Prior reviews are retained: four concrete findings were accepted and fixed (cache inventory additions, final callback checkpoint binding, foreign-global source replacements, stop-timer coverage). No clean review was repeated.

## Read-only historical compatibility entry

The operator may separately invoke `Primitives.historical(context, proof)` in the authorized UNBOUND/no-authority stdlib-only context. Required fields are io, c, modules.source_binding, h.loader.original_source_pins, h.history.reused_scores[*].spec.pin, h.facts.original_execution_closure_sha256, g.input_pins.original_admission/closed_comparator_report, check(), input_paths=set(), input_directories={}, input_profiles=[]. Proof contains original_execution spec and seven independent_returns specs. This format check creates no Primitives instance, opens no numeric payload, sets no authority flags, and grants no execution permission.

MANIFEST.json is canonical and pins every file except itself. It includes the flat source, the exact reviewed public dependency context, review reports, test output, and this handoff. Its independent raw pin is delivered separately to ROOT; it does not contain its own hash. All files are made read-only after closure.
