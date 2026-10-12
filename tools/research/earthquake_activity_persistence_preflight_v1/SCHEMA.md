# Pure API and parent projection

Source-only stage0/1. No decoder, file/network IO, provider library, actual data, fit or cloud launcher is provided. Actual producer/runtime/custody and data authority remain root-owned. Every caller assertion is explicitly labelled as an assertion; `fit_authorized` staysfalse.

## Metadata grouping: root's exact neutral projection

`grouping.group_events(rows)` accepts an exact builtinlist of65 builtindicts, original ordinal ascending, with exactly:

```text
ordinal: builtin int,0..2^31-1,unique,increasing
partition: exact TRAIN|DEV,counts41|24
origin_ns: builtin signed64 integer OR unknown/malformed metadata
latitude: builtin finite int|float in[-90,90] OR unknown/malformed metadata
longitude: builtin finite int|float in[-180,180] OR unknown/malformed metadata
```

Missing/invalid/ambiguous origin fields make that rowUNKNOWN_ORIGIN. No known singleton is invented. Missing keys/extra fields/invalid partition/ordinal/container are structural errors; no Mw/activity/waveform/TEST fields are accepted. Root supplies allthree origin fieldsNone for an unknown slot. Integer timestamps retain root's metadata microsecondprecision convention; this source cannot authenticate UTC provenance or raw origin-time accuracy.

Edges: inclusive absolute origin-time gap<=30days and binary64 haversine distance<=200km, Earth radius6371km, shortest longitude difference, rounding-only clamp[0,1]. Components are transitive; identifier is minimumoriginalordinal. Acomponent spanningTRAIN/DEV excludes both. All65 outputs retain implicitcompactslot0..64 andoriginalordinal. Known singletons are operational groups only. Full-catalogue bridges, long/repeating sequences and physical independence remain unresolved.

Grouping output is private scalar JSON containing rows/components/edges. No origincoordinates/timevalues are echoed, but ordinal mapping is still private. Root independently verifies projection custody and recomputes the group arithmetic before activity values are inspected. Root maps the integergroupidentifier to an opaque string for the next API; unknowngroup maps toNone. Group construction never sees magnitude labels.

## Activity event API: one event at a time

`activity.extract_event(event, qualification)` accepts exact builtindicts. Event keys:

```text
slot: compact original ordered slot0..64
partition: TRAIN|DEV
t0_ns: builtin integer (signed64 bounds allowing-3/+5s arithmetic)
p_ns: builtin signed64 integer P>=T0,unchanged accepted selectedP
family: ENZ|12Z|None (root-qualified literal metadata;None never inferred)
mw: builtin finite numeric-5..15 (typedMw binding owned byroot)
group: opaque builtinstr length1..128,orNone for unknown
components: None ifdenied/deferred;otherwise three ordered literal components
```

Qualification has exactly `horizon_support:[bool,bool,bool]` for1/3/5 and `group_eligible:bool`, asserted externally. DEV is alwaysdeferred and mustcontainno componentarrays. UnsupportedTRAIN,unknownfamily,unknown/ineligiblegroup andP+.25>T0+1 mustalsohave componentsNone. Allthree root horizon-support flags mustbeTrue before any TRAIN valuesareinspected. Aboolean doesnot authenticate transport, native-grid support, sourceversion/runtime/cgroup/readonlyhashes, physicalsequence independence or authority.

Each component is `{name,pieces}`; name is literal3ASCIIuppercase/alphanumeric characters. Components share exacttwo-characterprefix and arrive inE,N,Z orliteral1,2,Z order accordingto the already knownfamily. No rotation/renaming/unknownfamily inference. Every piece is exactly:

```text
start_ns: builtin signed64 integer
rational_period: [positive builtin numerator<=10^12,
                  positive builtin denominator<=10^9],gcd=1,nanoseconds
values: exactbuiltinlist|tuple,nonempty nativecountsamples
```

Piece starts are strictlyincreasing. Per-event cumulative caps32768pieces/8millionsamples acrossallthree components; source checkscontainerlengths without globally inspecting samplevalues. Root still enforces originalperbody/wholeinvocation caps and processesoneeventat a time. Numeric samples are builtinint|float,finite,abs<=1e12; bool/subclass/customconversion rejects. Only actual currentwindow values are numerically validated; an invalid later sample cannot alter an earlier returned horizon. The1e12 guard is an explicit arithmetic safety/support bound, not a hardware-rail claim.

Recordpieces stay separate. Each requested window requires exact contiguous nonoverlapping coverage in rational timestamp arithmetic and>=1 actual sample. Halfopen membership usesexactceil indices. No fill, interpolation, repair, piece reordering, resampling or future endpoint value. Root's independent decodedqualification additionally owns source-native period/rate/lattice identity. This source checks its own requested crop coverage; it is not a substitute decoder or custody verifier.

Noise usesonly[T0-3,T0), fixed12quartercells, onecomponentmean overthefull preT0 interval, median centeredcellpower,floor1count². Activity uses onlycompleteP-anchored.25scells at/beforeT0+h,maxliteralcomponentmean-square/noisepower,active iff>9. Every horizon returns cumulative currentstates/runages/actualon-offtransitions/episodes/rightcensor/noise-floorflags; its finalrun is rightcensored with no appendedexit. Quietcanreactivate. These are receiver-energy states,not physicalrupture orP-only states.

All deniedrows retainthree placeholders. Strictstructural violations raisebounded `InvalidInput` codes; crop numeric/coverage failures retain boundedunknown horizonstatuses. An invalid later sample can mark3/5unknown while1remainsavailable; such an eventfails all-horizoneligibility and staysoutside thegate. Root preserves theoriginaldenominator and error result ratherthan substitutinganother event.

## Cohort summary

`activity.summarize(results, external)` accepts exactly65 originalcompactslotordered `extract_event` results with41/24 partitions and validates boundedsequencefields/recomputedderivedstates. No DEV activitycanbe available. `external` is exactly `{grouping_frozen:bool,prior_support_floor_pass:bool}`. These flags remaincallerassertions.

Only fullyavailableTRAIN5s results enter variationcounts. The validator requires1..4/9..12/17..20 currentcells,exact8cell increments,identical earlier ratio prefixes and sharednoiseestimates/floorflags acrossavailablehorizons. Impossible short5s orfuture-filled1s outputs cannot count as completeexposure. Variationrequires at least5 distinct frozenoperationalgroupids withofftransitions,5 witha finalactivecensoredrun,atleast2distinct terminalactive-runages (observedoffexitages orfinalactivecensorages),andbothMw>=5.5/lowerMwamongusableTRAIN. This concretizes the proposal's run-agevariation gate withoutusingDEV. `combined_prospective_gate` additionally requiresboth externalassertions; itneverauthorizesfits. Perfamily literal-orderfloorcounts prevent mixing E/N with1/2 axes. Root owns the prior20TRAIN/12DEV/8TRAINtail/5DEVtail/5lowerperpartition/3DEVtailoperationalgroup floor fromtheprior diagnostic; this extraction doesnot readDEVvalues tocertifyit.

Root mustbound actualprivateJSON16MiB/publicaggregate64KiB/stderr128KiB and enforce itsfrozenLinux300s/1GiB/cgroup/processlimits. This modulehasnofilewriter,processcontroller,rawclockproof or actualexecution authority. Its outputshapes arebounded but thatdoesnot certify parent memorycontainment or serializedfilecustody.

## Frozen public ancestors

Root activityproposal: `work/earthquake_activity_persistence_preflight_proposal_v1/PROPOSAL.md`, SHA256 `8d025c18547a749f301805881f3b2f138439588c3b4895761e3dfb83959238d9`.

Root operationalgroupingproposal: `work/earthquake_operational_sequence_grouping_proposal_v1/PROPOSAL.md`, SHA256 `b69632b79647f43967785cef2cea367cd3b89658abbf2acdc57b37f7a70abe69`.

Candidateprotocol: `work/earthquake_tail_innovation_candidates_v2/PROTOCOL.md`, SHA256 `989c6e5f13e3589adad58b13d378630f03d0d66932ba8e5c04b916e225d3d61a`.
