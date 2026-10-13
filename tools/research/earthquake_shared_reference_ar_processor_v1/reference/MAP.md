# L integration map — source-only, 13 October 2026

**Recommendation:** implement a separate, small L processor/scorer and independent L audit extension, then a single nine-stage controller. Reuse the frozen native representation, numerical transport, prior architecture and reviewed operating-system helpers by exact source binding. Do not add an `L` alias to the current S/P/D study or reuse its admission/authority receipts as permission for new execution.

This map inspects public protocol and code only. No feature values, targets, forecasts, checkpoints, private execution proofs, cloud resources or shared Git were accessed. It does not authorize implementation or execution. All paths below are relative to the workspace's `work/` directory; line numbers identify the inspected frozen sources.

## 1. Scientific difference and minimum evidence

The controlling specification is `earthquake_shared_reference_ar_study_v1/PROTOCOL.md`. For component c and zero-based cell j, retain the existing affine intercept A, magnitude slope B and residual scale, but use

```
A_jc = a_c + d_c log(1+.25j) + rho_c y_(j-1,c) - B_jc mref
B_jc = b_c + e_c log(1+.25j)
lambda_0c = 1; lambda_jc = 1-rho_c for j>0
y_jc | M,ell ~ Normal(A_jc + B_jc M + lambda_jc nu_ell,c, sigma_c²).
```

The first lag is exactly zero. Here `lambda` avoids confusing the noise loading with the existing time-intercept coefficient named `d`. The later conditional-mean derivative with respect to rho is `y_previous - nu_ell,c`; the first factor has no rho dependence. S remains a coherent shared-innovation model with loading one. L is a different observation assumption, not a repair of an invalid S density.

`earthquake_shared_reference_ar_kernel_v2/kernel.py:86` (`reference_loading`) and `:92` (`marked_nll`) already implement this differentiably. Use B=1 for each original event/horizon term. Preserve 24 separate backward calls, division by 24, accumulation order, clipping and fresh Adam. Its returned dictionary is **not** the original `Posterior` object API.

Keep the original 12 joint three-component support points outside the entire likelihood product, five prior components, and noise-major/prior-minor 60-component ordering. Recompute each deadline from the same static prior, or carry the full joint `(M,ell)` state. Do not use a marginal M posterior as a new prior while drawing the shared nuisance again.

L forecast evidence must explicitly contain mode L, original prefix prior, coefficients/rho, observed lag per cell, chronological loading vectors, native support, horizon/offset, cell count/last cell and complete posterior/log evidence/noise probabilities. The independent auditor derives each loading and lag from the saved coefficients and bound native prefix; a supplied mode/loading flag is insufficient. New fields need a new exact schema, not extra unvalidated dictionary keys.

## 2. Producer: precise extension points

| Frozen source/function | Separate L work needed |
|---|---|
| `earthquake_marked_sixfit_processor_v1/processor.py:11–18,43` — constants, `Bindings` | New fitting/study identity and order `[(20261012,L),(20261013,L)]`; bind kernel, L scorer/reference, processor and protocol separately. Existing five source-role names do not positively bind all new execution modules. Native feature V1 identity remains unchanged. |
| Same `:102,115,137,203` — `validate_packet`, `static_scaler`, `context`, `event_order` | Retain native115/345 and common65TRAIN/22DEV checks. Load and positively compare archived original TRAIN schema/rank/scalers, D active mask and event order; do not silently replace them with newly fitted floating-point equivalents. Independent reconstruction remains a verification check. |
| Same `:155,209,255` — `model_for`, `prepare`, `bind_admission` | New two-L admission. Load each seed's exact **original admission** S/P common initial prior and 18 coefficients, never a trained state. Retain old admission/source/initial receipt origins separately; generate new L initial receipts under the new identity. Seed regeneration alone is not byte-identity proof. Both initial195-term probes must finish before either optimizer. |
| Same `:167,177,277` — `posterior`, `gradient_probe`, `fit_one` | Bridge B=1 `marked_nll` to a scalar conditional NLL while retaining original scalar prior/context. New L model has `16K+544` genuine parameters, no learned loading. Preserve parameter/optimizer traversal, all195 initial/final gradient masks,300 updates,batch8,seed+1009 orders,Adam1e-3/noWD,norm5 and final-only checkpointing. |
| Same `:342,357,407,450,466` — final validation/scoring/evidence/population | Validate L final state and history against its new admission plus original initialization provenance. Score66 per seed without optimizer. Export the extended evidence above and preserve every proper-score/quantile/coverage field and numerical rejection. Current evidence validation assigns60 components only to S, assumes four-field factors and accepts only S/P noise semantics. |
| Same `:489` — `aggregate` | Accept two new L scores, six independently closed S/P/D scores and eight independently closed B/F/H/T scores, retaining distinct original source/admission/checkpoint origins. Build42 L comparisons; do not mutate original36 S checks or reinterpret historical scores as new L outputs. |

The frozen Gaussian operator is not an L scoring bridge: `earthquake_marked_noise_gaussian_pilot_v1/gaussian_operator.py:163` (`marked`) and `:235` (`MarkedNet`) reject L; `:189` (`checked_scores`) treats every non-S mode as zero nuisance and builds a loading-one reference. Reusing it with a renamed mode would certify the wrong model. Its prior architecture and all-real mixture scoring formulas are reusable ingredients; the L scorer must bind an L-aware reference and carry the same record budget through construction and scoring.

The kernel's `reference.py:38,59,66,70` provides independent synthetic facts/start/append/completion, including 60-digit Decimal completion. It is useful for the producer crosscheck and invented fixtures; it is not an existing authority for actual checkpoint/population closure. Do not let the independent final auditor import the Torch kernel or merely trust this producer crosscheck.

## 3. Independent numerical and provenance audit

Extend in a new package; leave `earthquake_marked_sixfit_independent_audit_v2` unchanged.

* `math_core.py:60,112` (`factors`, `complete`): independently derive lambda and replace each residual `y-A-nu-B*mu_k` with `y-A-lambda*nu-B*mu_k`. Conditional precision still uses the same B/sigma; nuisance affects information, posterior mean and component evidence. Complete all factors independently, retaining determinant/normalization terms and60 shared-support components. No Gaussian approximation or re-initialized nuisance between deadlines.
* `auditor.py:181` (`affine_bounds`) and `math_core.py:140` (`completion_mean_error`): account for subtraction `1-rho`, multiplication by nu and residual arithmetic before reusing the precision/information bound. The loading can be negative or zero; no relative-only bound near zero, clipping, detached rho or new rho restriction. Preserve existing representation/ULP/mean rejection and strict softplus threshold20 semantics. The independent high-precision completion and operation-aware source checks must agree, not replace one another.
* `auditor.py:34,48,62` (`shape_state`, `admission_checked`, `checkpoint_checked`): L is currently routed to D state shapes. Add explicit L coefficients, two-model admission, source roles and original-initialization equality proof. Retain independent TRAIN rank/scaler/order reconstruction, both195 probes,300 histories and exact final-state/optimizer bindings. Old S/P/D admission continues to identify historical comparator states.
* `auditor.py:68,79,96` (`reconstruct`, `source_checked`, `audit_fit`): reconstruct the L prior and all factors from native data and final weights; compare the new loading/lag/clock evidence, then every66 forecasts. Keep source-forward bounds plus all-real mean/NLL/logZ parity≤1e-4, CDF/CRPS/median/seven quantiles≤1e-6, inclusive Boolean coverage,10s/1M-point limits and partial retention on failure. Numerical closeness does not establish actual optimizer history; ROOT must still authenticate execution custody.
* `auditor.py:128,148` (`stronger_checked`, `aggregate`): current code accepts eight old comparators and six new audits, reporting396. New aggregate validates **132 newly replayed +396 reused +528 reused =1056 comparison records**. Report those counts separately so reused closure is not represented as a new numerical replay. Preserve original old-packet storage-pair semantics and comparison-join origins; no source-pin relabeling.

Algebra/gradient fixtures: rho0 fixed-parameter posterior equals S (not generally its rho gradient); nu0 gives the P marginal; first-cell law equals S; rho1 removes only later nuisance; mixed signs work; direct latent substitution and finite-difference/autograd rho derivatives agree; joint-state suffix equals once-only full prefix; future marks cannot affect shorter prefixes. At1s a one-cell prefix has no fixed-parameter loading advantage. Separately test the complete model/bridge and loss accumulation, not only kernel identities.

## 4. One nine-stage control chain

| Stage | Action | Source / manager seconds |
|---|---|---|
|0|Native/original-initial/schema admission; both L195 probes|300 /360|
|1|L20261012 fit300 updates|300 /360|
|2|L20261012 score66|900 /960|
|3|L20261013 fit300 updates|300 /360|
|4|L20261013 score66|900 /960|
|5|Producer aggregate, all closed comparators|300 /360|
|6|Independent L20261012 audit66|900 /960|
|7|Independent L20261013 audit66|900 /960|
|8|Independent aggregate42 guards|900 /960|

All nine share one newly authorized7200s whole clock plus200s closure, with no reset at stage6. Source caps sum5700s; manager caps sum6240s, leaving960s within7200 for other whole-clock work. These sums are capacity accounting, not a runtime guarantee. Preserve2GiB/swap0/Tasks64/oneCPU/CUDAhidden/control-group/stop5, no retries/skips/overwrites, and ROOT's fresh financial/resource/publication gates.

Specific hard-coded assumptions preventing direct reuse:

* `earthquake_marked_sixfit_parent_controls_v1/controller.py:8–14,49,66` and `child.py:7`: six-fit ORDER,14-stage roster, old source/input roles and source-kind caps. Require new nine-stage specification/dispatch and original-initial/reused-closure inputs.
* `earthquake_marked_seven_audit_deployment_v1/first_clean/audit_control.py:7,12,16,57`: seven-stage S/P/D audit identities. `audit_deployment.py:12,33,51` loads exact role groups and assumes900s child work. It cannot be attached as a second whole clock to L.
* `earthquake_marked_sixfit_audit_wrapper_v1/wrapper.py:7,37,46,58`: six PAIRS, stage0..6,396 count,24+12 guards. New L audit wrapper maps overall stages6/7/8 explicitly and retains full reports before final deadline checks; no silent index alias.
* `earthquake_marked_audit_input_adapter_v1/adapter.py:48,61`: original14 directories, six initial snapshots, score indices2/4/6/8/10/12 and six previous audits. New adapter must distinguish six L producer stages, historical S/P/D fourteen-stage custody and closed seven-audit evidence. Old source pins describe old work, not the L dependency graph.
* `earthquake_marked_audit_root_hooks_v2/hooks.py:125,174,217`: exact original14 and audit7 resource/config/namespace/proof shapes. A new authority assembly is required for9 L stages and closed396 reuse. Existing financial/source booleans alone are not permission.

Reuse frozen V6 `secure_io`, vendor/runtime verification and `Systemd` primitives without weakening them. `source_binding.py:238` (`scientific_modules`) explicitly imports original Gaussian/processor groups; use a separately bound L loader with exact aliases/dependencies. Independent stages must follow `audit_deployment.independent_modules`, loading only native NumPy and independent auditor modules, never producer/operator math. Retain existing2MiB checkpoint versus16MiB audit-member/64MiB-stage limits; validate the full aggregate storage envelope prospectively rather than increasing a frozen limit.

## 5. Reporting and readiness boundaries

Extend `metrics.py:37` (`guards`) to **L vs S/P/D/B/F/H/T**,2seeds×3deadlines×7=42. Each requires high-Mw≥5.5 MAE gain≥.02 plus nonworse whole/lower MAE and MedAE,CVaR95,max. Require strictly lower NLL and CRPS against B/F/S/P/D; H/T proper scores remain descriptive. Keep both seeds/deadlines separate. Report PIT, coverage50/80/95, median action, Mw≥6 and strata without recalibration or alternate selection.

`metrics.py:14` (`paired`) already supplies grouped1000-draw bootstrap(seed9919), rejects mismatched identities and labels insufficient support. Reuse that fixed descriptive convention for L−S at each seed/deadline even on a negative42-check gate. Do not add bootstrap selection, averaging away a failure or DEV-tuned calibration. New output must distinguish numerical/custody completeness from scientific advancement.

Implementation blockers are concrete: independently closed S/P/D reuse; positively identified **original** admission initialization/schema; L-specific scorer/export and independent loading/bound reconstruction; target-runtime synthetic fit/scorer tests; new nine-stage source/runtime/control/publication authority. No actual fit is justified by this map. The kernel proves a conditional-law computation, not that empirical delete-one noise support is calibrated or that L improves magnitude prediction. This remains an exploratory reused-DEV ablation with no novelty or benchmark-superiority claim.
