# V3 narrow coverage compatibility

Invented covered/uncovered Normal cases verify both prior scalar scoring functions emitted float0/1 and the unchanged strict comparator rejected stored builtinbool, because its numeric finite() excludesbool. INVENTED_DIAGNOSIS.json retains12such source-only cases. No actual input/outcome or producer implementation was read.

New independent source changes only the two per-record coverage casts to builtinbool. bool comparison is exact through the comparator's existing type-identity branch; no tolerance change. Malformed float/int/string/null/NumPybool indicators fail. Per-record bool truth is freshly computed from the same inclusive quantile intervals. Metric/strata/paired-bootstrap coverage averages remainfloat; labels/modelmath/gates/denominators are unchanged. Independent audit output schema is V3 while original study/packet/result contracts remain V2.

The new invented complete fixture has10fits/660predictions/24comparisons, literal115/345 roles and false advancement. This verifies integration of the dtype path; it is not an actual checkpoint/model run. An audit failure still forces false/empty authoritative advancement.

Known invented narrow-mode CRPS integration defects in the frozen V2 numerical method remain unchanged in this compatibility fork, as explicitly required. Fast all-real integratorV3 is a separate package and is not imported/adopted. A compatibility pass alone does not certify universal numerical accuracy or scientific advance. Parent retains independent actual failure anchors and must separately validate any source/runtime/data use.
