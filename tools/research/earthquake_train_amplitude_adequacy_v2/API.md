# API

adequacy.validate_input(value) returns strict normalized copied numeric dataset or raises ValueError. It never removes failed rows.
adequacy.run_outer(value, *, deadline=None) returns full bounded private outer result; deadline is a parent monotonic absolute deadline, at most900s from entry. A failed fit/numerics/time returns incomplete with retained completed fit statuses and zero advance. This function cannot perform fullTRAINfits.
adequacy.continue_train(value, outer_result, *, deadline=None) validates input hash, exact outer receipt hash/control/counts and gate before performing26fullTRAINfits. Parent must independently preserve readonly outer result FIRST; pure code cannot prove filesystem preservation. Failure is incomplete, not retry authority.
adequacy.public_summary(result) emits count/status-only <=64KiB-compatible summary. No slot/group/label/prediction or actual pin in public summary.

Low-level numeric modules expose immutable fitted prior/scalers, deterministic fit, normal/selection-normal posterior and weightedmetrics for invented tests. Source version binds complete code-only manifest/review/protocol; root performs positive pin/publication/custody before actual. No mutable learned or external-global state.
