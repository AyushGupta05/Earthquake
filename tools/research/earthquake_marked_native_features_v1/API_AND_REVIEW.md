# Marked native feature builder V1 — source-only handoff

This packet implements the approved marked-noise proposal's native observation layer. It contains invented fixtures and unchanged safe reference source, no actual dataset, IDs, inventory, clocks, gains, fitted state or scientific result. It does not authorize extraction or fitting. ROOT owns all private input/source/runtime/custody bindings and all real runs.

## API

`marked_native.project_anchor(original_packet, source_pins={archive,manifest}) -> bytes`

ROOT first loads its independently verified original observation packet through the original `packet_io.py`. The projection consumes original initial.context35 and horizon ratios/states/run_ages, fixed row roles/statuses and original six input pins; it never inspects original waveform arrays. ROOT must independently prove equality to its bound original packet BEFORE invoking this new builder. A self-generated anchor from new marked outputs is invalid. The projection's source archive/manifest hashes bind its provenance; a hash assertion alone is not custody proof.

`build_marked(old_plan_bytes, old_qualified_bytes, old_bodies, new_plan_bytes, new_qualified_bytes, new_bodies, metadata_bytes, roster_bytes, activity_anchor_bytes, decode_record, *, bindings, pins, processing_begin)`

`bindings = Bindings(positively_bound_original_observations_module)` reuses the original V2 `qualified_validate`, `metadata_validate`, `replay_batch`, `components`, `context` and native reducers. It adds no scanner, decoder, request manager, file access, cloud command, source selection, clock reconstruction or model import. Original old17/new13 namespaces remain separate; every actual decode is charged before returned count/grid/dtype/hash reconciliation, including valid failure counts. Per-body and aggregate bounds are inherited unchanged. The caller's before-import monotonic start is shared with the 300-second source deadline. ROOT must bind source bytes and decoder identity independently; the module name/schema checks are not proof of source identity.

`event_marks(native_components,row,meta,anchor_row,*,bindings,processing_begin)` is the feature-only callable after original whole-record/native-sample and current piece/view hashes are verified. The public function is useful for invented fixtures; calling it without the build replay chain does not establish real source integrity.

`packet_io.save(packet,processing_begin=...) -> (archive_bytes,manifest_bytes)` and `load(...,pins,processing_begin)` provide pure memory numeric custody. Closed names, exact dtypes/shapes, little-endian payload hashes, ≤1MiB numeric payload, ≤4MiB manifest, ≤8MiB archive, bounded NPY headers, no pickle/object dtype, reference closure and complete feature semantics are checked. ROOT owns storage. Successful output has exactly115 rows/345 statuses,91TRAIN24DEV,65TRAIN22DEV common, fit_authorized=false. Unavailable rows retain explicit null features and all horizons.

`FeatureError` carries completed `partial_rows`, charged `observed_samples` and bounded partial event `diagnostics` privately. It never returns a successful reduced cohort or promotes a partial event. Original inputs remain ROOT-owned evidence. No retry or repair is implemented. Numerical boundary case: if R exceeds exp(-12) but float64 log(R) rounds to exactly -12, reject as `censor_log_roundoff`; never manufacture an uncensored value at the censor boundary or change the fixed threshold.

## Exact semantics

The three-second pre-T0 scalar mean is shared by all12 chronological quarter powers and current post-P powers. N=max(1,median12), with floor only for rawmedian<1. Twelve joint support points delete the SAME quarter index in all components, use log(max(1,median11)) and component-wise fsum/12 centering. Duplicate/zero-spread supports stay unchanged with uniform1/12 weights. This is an empirical sensitivity prior, not an identified true-noise law.

Current complete quarters start at the original P time; J=floor((h*1e9−(P−T0))/250000000). Each factor enters once. R is retained per literal native component; Rmax, strict >9 states and consecutive run ages must equal the original anchor bit-for-bit. Every shorter prefix must be byte-identical inside later prefixes. Immutable initial context drops ONLY original index6 (first activity bit); native counts/float widths are never reconstructed from normalized float32. Literal ENZ/12Z and original pieces are preserved, without rotation, resampling, gap/overlap repair or physical response conversion.

## Reference source and tests

`reference/` contains seven unchanged safe original source files for reproducible invented tests and reviewer context; `reference/SOURCE_PINS.json` records their hashes. The production builder uses ROOT-injected originals, not automatic path imports. `fixtures.py` loads only those local source files in isolated module bindings and synthesizes MiniSEED bytes with i4/f4/f8 encodings, separate namespaces, large integers and changing quarter powers. No actual private path appears in executable source.

Tests compare against independent rational sample-index enumeration, not only calls through the implementation. They cover exact activity parity, distinct joint noise indices, integer float32-loss counterexamples, rational grids/empty cells, current offsets, first-cell behavior, future-suffix invariance, floors/censors, full-body/record hashes, count charging on failures, whole-stage rejection, all statuses and strict numeric-byte round trips/adversarial mutations.

Run: `/Users/ayush/.venvs/ml/bin/python3 -m unittest -v test_marked_native test_packet_io` in this packet directory. Test/model results are synthetic only. Required isolated default Codex autoreview must finish clean before a first-clean source freeze; ROOT then independently binds actual inputs. No novelty or accuracy claim is made.
