# Narrow ROOT composition for frozen L execution — draft before first clean

Public implementation: `root_glue.py`, `bootstrap.py`, `comparator_population.py`.
No actual payload, account values, credentials, model, private receipts, or provider action belongs in this packet. Source-only fixtures are invented. Frozen bridge36/execution38/runtime22/comparator26/scientific source profiles remain unchanged.

ROOT loads `Root`/`compose`, or calls `execute_child` and `run_parent`. All arguments are mandatory positive ROOT bindings. Expected root pin is independently held before imports; a requested object or its self-chosen hash is insufficient. A new root composition config references the exact pre-existing execution/loader configs and their separately held pins.

## Held config

Canonical JSON, <=2MiB, schema `root-held-L-composition-v1`, exact fields:

```
{
 schema, execution, execution_pin, loader, loader_pin,
 inputs, history, documents, evidence, facts, launch
}
```

`execution` is the exact frozen9-stage config; `execution_pin` is ROOT's expected pin. `loader` is the exact frozen runtime adapter config and `loader_pin` its ROOT-held pin. Scientific file counts/copies/limits are unchanged. `inputs` is the bridge's exact8 readonly `{path,pin,mode:256}` specs; `history` is its ordered6 `{seed,arm,spec}` reused scores plus `stronger_envelope` spec (the authenticated old list8, not an outer fits8 envelope). Specs/pins must match execution inputs. 2MiB reused-score and16MiB historical/report caps remain.

`documents` is exact `{funding,publication,protocol,root_context}` readonly specs. First3 match execution's corresponding pins. root_context<=1MiB; other documents<=16MiB. The CURRENT verifier must parse/authenticate actual funding/publication/stop/resource/boot/lease semantics. The glue never converts requested values, balances, proof flags, version strings, or mere matching hashes into authority.

`evidence` is exact `{source_runtime,current,inputs,projection,audit}`, each an independently authenticated readonly spec <=16MiB. Except projection's structural schema below, private evidence formats are owned by the mandatory concrete ROOT primitive implementation. Glue passes their exact raw bytes unchanged; primitives must check their precise schemas and actual referenced artifacts. These five subjects must be independently constructed/verified by ROOT before this config is held. No requested hash or caller Boolean authenticates them.

`facts` is exact `{packet_sha256,original_execution_closure_sha256}`, both lowercase64hex, independently established from native/current packet identity and actual original14fit/7audit/source/history/probe closure. Inputs primitive must independently reproduce exactly these facts.

`launch` exact fields:

```
bootstrap: readonly spec for this bootstrap.py
primitive_source: readonly spec for ROOT's concrete factory module
modules: {canonical_module_name: readonly .py spec}
store_directory: absolute canonical frozen journal root
prefix: eew_l_[a-z0-9_]{1,64}
python: exact loader.runtime.python
commands: unchanged frozen Systemd command specs
```

`modules` exact canonical names, loaded in this order:
`secure_io,vendor_inventory,generated_source,metadata_finder,source_binding,systemd_adapter,codec,bridge,runtime_adapter,control,child,journal,projection,comparator_population,root_glue`.
Every supporting/preloaded module and primitive_source must belong to a positively closed existing supporting profile (e.g. bootstrap); no broad directory allowance. ROOT source/runtime primitive checks actual loaded code/global/transitive identities and all profile/runtime/publication subjects. The original v6 source helpers must retain their original paths/profile and exact identities expected by frozen runtime loader.

## Mandatory primitive ABI

`primitive_source.make_primitives(held, *, expected_root_pin, root_spec, modules, source_begin, clock)` returns exactly `(primitives,custody)`. It must be a positively source-bound ROOT implementation. It must not import producer/Torch/scientific modules before the frozen runtime context. Independent branch imports no producer/Torch. No default factory/verifier is supplied here.

The five methods below are mandatory read-only verifiers. They reject by raising and return an exact structured attestation, never bool/None:

```
{schema:'root-L-primitive-verification-v1', kind,
 scope_pin: pin(canonical(exact_requested_scope)),
 evidence_pin: independently held exact raw evidence pin,
 claims: purpose-specific exact fields below}
```

`source_runtime(scope, held, module_graph, source_runtime_raw, now)`:
module_graph exact `{support: positively loaded supporting modules, scientific: active frozen loader result or None}`. Verify the closed source graph/publication, original copied helper identities, full runtime and current semantic role subjects before any science/native decode; never accept __file__ or version string alone. Return kind=source_runtime, evidence_pin=held.evidence.source_runtime.pin, claims exact `{source:pin(canonical(execution.source_pins)),runtime:execution.runtime_pin}`.

`current(scope, held, documents_raw4, current_raw, now)`:
verify CURRENT independently observed financial credit/service/bound/reservation/expiry, source publication commit, same-host boot/monotonic lease, available exact new units for parent or actual current unit for child, fixed resources/storage reservation, installed7200science+200closure stop and every scope. Return kind=current, evidence_pin=held.evidence.current.pin, claims `{expires,resources:positive_pin,storage:positive_pin}`. Expiry must cover fixed parent manager and never extend config lease; child lease cannot extend parent. No default true flags or numeric account values appear in glue.

`inputs(scope, held, raw_base8, raw_history, input_custody_raw, projection_raw, now)`:
verify all raw pins AND actual native115/345/same87/allpositive custody, original14 full execution/source/returned history/probes and archived both-seed S/P initial states, closed7 independent audits/full924report/14 immutable historical origins/cohort joins/list8 stronger projection. No trained state substitutes for original initialization. Preserve historical packet/storage-pair/source/report identities. Scope is either frozen parent/child stage-authority scope (authorize calls this BEFORE issuance) or exact bridge input scope (before bind decode). Return kind=inputs, evidence_pin=held.evidence.inputs.pin, claims exactly held.facts. Merely returning held facts without independently checking evidence is invalid.

`prior(scope, held, snapshot, requested_inventory_or_None, now)`:
verify a completed ACTUAL new L manager return against independently retained ROOT last in-memory returns, exact full current journal inventory/streams/hash/count/EOF/issued child+parent lease/zero exit/actual own stopped empty cgroup and persisted files. No provisional closed.json is sufficient. Reject failure/late markers and mismatch. scope identifies stage plus either exact closed pin or exact request+result pin. Return kind=prior, evidence_pin=snapshot.known_pin, claims exact `{known_return_pin,closed_pin,result_pin}`.

`audit(scope, held, raw_previous, authenticated_input_receipt, prior_cache, audit_evidence_raw, now)`:
verify new L300 full actual optimizer/history/probes/original initialization custody and/or complete actual two independent fit returns and historical924/14origins, deriving semantic authority from authenticated raw bytes and held facts. Perfit indices0/1/2 or0/3/4; aggregate0/2/4/6/7. `prior_cache[index]=(claims,raw_file_map,snapshot)`. Return kind=audit, evidence_pin=held.evidence.audit.pin, claims exact `{authority: complete exact frozen perfit/aggregate authority}`. This is the only source of literal authority flags: all required true flags must be positively earned by the concrete verifier. Glue compares every nonflag candidate field and exact flag set before forwarding it.

## Custody and retention

`custody.snapshot(index)` is read-only and returns exact:

```
{
 known_raw: canonical independently retained metadata bytes <=1MiB,
 known_pin: independently held pin of those bytes,
 files: {single_basename: readonly spec for actual current stage member},
 inventory: exact actual independently held inventory
}
```

`known_raw` schema `root-L-known-parent-return-v1`, exact keys `{schema,stage,config_pin,returned,inventory}`. returned is the exact actual frozen parent return, not a manufactured/reparsed provisional assertion. `files` includes closed.json/result.json/child_report.json/claim.json/dispatch.json and complete actual retained evidence. Glue rejects late_or_failed.json/child_failure.json. Primitive must independently verify full inventory and actual stream/OS/lease truth, not trust the snapshot's own matching hashes. root_known metadata stays within the original1MiB external ROOT custody cap.

`run_parent(..., retain_return=...)` calls mandatory ROOT `retain_return(index, actual_return, actual_inventory, actual_Systemd_answer, actual_request)` AFTER frozen control closure, including failed returns. It must verify all actual evidence and fsync immutable ROOT known-return metadata, then return exact `{schema:'root-L-last-return-retention-v1',stage,return_pin:pin(canonical(actual_return)),proof_pin:positive_pin}`. Glue rechecks parent/child/whole closure deadlines after retention and adds a late failure marker on expiry; it never grants retry. ROOT implements durable custody/persistence independently; no default retainer exists.

## Child, early prior authentication, projection

`execute_child(held,request,*,expected_pin,root_spec,modules,primitives,custody,journal,systemd,source_begin,clock=...)` owns one ExitStack through the ENTIRE real frozen child execution, result/report/negative persistence and frozen runtime context exit. source_begin is ROOT's clock captured before bootstrap imports.

`compose(root,*,bridge,runtime,systemd,stack)` builds the real frozen bridge with a relay retaining its active module graph. All bridge trusted callbacks are concretely implemented on Root: documents/authorize/prior_closed/launch/authenticate_raw/project_comparators/previous_raw/authenticate_previous/verify_audit_authority. Prior bytes are read/positively authenticated during bind before the frozen child can decode its previous admission. Exact stage prior sets remain1[0],2[0,1],3[0],4[0,3],5[0,2,4],6[0,1,2],7[0,3,4],8[0,2,4,6,7].

Projection evidence raw schema `root-L-held-comparator-joins-v1`, exact keys `{schema,joins,comparison_schema}`. joins is the frozen comparator module's exact14 authenticated join objects; comparison_schema is the original admitted schema required by full auditor.comparators_checked (including exact dev ordinals). The inputs primitive independently authenticates these raw bytes/full origins/provenance before glue parses them. Root builds the stage contract from its own held config/facts/captured clock/authenticated receipt/joins, not requested hashes. It passes this positively ROOT-constructed contract+pin to frozen projection.make_projector.

Independent uses already loaded auditor group. Producer comparison validation reuses the already admitted full-auditor35 profile via the frozen loader's `_source`/`_group` inside its ACTIVE unchanged V6 guard and checks NumPy/global aliases; no new scientific profile/cap/whitelist. Scalar population validators are exact copied function spans, with source/function hashes back to frozen processor; the support wrapper rejects L/unknown arms, so producer/Torch/model code is never imported for independent comparator checks.

## Sole-stage bootstrap

Root.launch requires its locally issued parent receipt and exact immutable dispatch bytes. It writes only frozen journal's immutable bootstrap.json control (<=512KiB), then returns held Python/inline source/bytepin/requestpin. Inline captures source clock before imports and nofollow-opens the pinned bootstrap. Bootstrap reads/hash-checks ALL supporting module and factory bytes before importing helpers, validates canonical launch/root raw, constructs mandatory private primitives/custody and frozen Journal/Systemd, and calls execute_child. Bootstrap root_spec pin originates from independently held parent Root, never from a requested config hash.

Remaining ROOT work: construct/verify private held config/evidence/docs/specs and factory+custody+retainer; positively close/publish support profiles; run actual cold source/runtime/host/resource/stop/financial gates; only then capture one new fixed clock/config/id/store and invoke frozen nine stages without retry, cap change, outcome selection or initialized-from-trained state. No actual execution authorization is established by this source packet.
