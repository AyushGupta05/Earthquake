# Synthetic numerical results V3

21 invented tests pass with zero failures/errors/skips. The eight fixed invented cases measured on the existing local Python3.14.5/NumPy2.5.4/SciPy1.18.1 runtime show warm scalar proper-score execution in0.0275–0.0400s. Three repeats per case, all BLAS/OMP/MKL/NUMEXPR threads1. Imports are outside these timings; cold rule/cache construction plus first normal score took0.02863s. The legacy column measures the old full scalar scorer including its failures; it is not an error-free ground truth or a training benchmark. Complete exact scalar outputs and failures are in SYNTHETIC_BENCHMARK.json.

| Invented case | V3 median seconds | Old median seconds | V3 disposition | Old disposition |
|---|---:|---:|---|---|
| normal | 0.02753 | 0.21248 | accepted | returned |
| moderate_19 | 0.03433 | 0.26679 | accepted | returned |
| multimodal | 0.03167 | 0.23919 | accepted | returned |
| tail | 0.02977 | 0.20962 | accepted | returned |
| broad_narrow | 0.03461 | 0.51778 | accepted | failed |
| sharp_20 | 0.03835 | 0.24749 | rejected GH | returned |
| far_label | 0.02860 | 0.11436 | accepted | failed |
| rare_far_symmetric | 0.03996 | 0.10950 | accepted | returned |

The slope20 case is deliberately refused by default: GH64/128/adaptive mean disagreement is0.006057512457, above the unchanged1e-4 check. Its explicitly diagnostic GH-disabled result always has acceptedFalse. No support truncation, sigma clipping, normal substitute or success denominator repair is used. Broad/narrow and far-label old CRPS paths fail; those failures remain visible. A faster return alone proves no scientific correctness.

## Verified inherited narrow-mode counterexamples

The frozen old reference is unchanged. Its absolute-moment method integrates two infinite intervals split only at the label, so QUADPACK can return nearzero without sampling a narrow component located far from that split. Norm,mean,NLL and CDF can still agree. Its global CDF-product integral can likewise miss a narrow CDF transition near an interval endpoint. V3 does not use either legacy CRPS method for acceptance.

For the invented zero-hazard tail mixture with y15, weights[.001,.009,.09,.3,.6], means[−5,0,4,8,12], sigma[.05,.2,.8,1,2]:

| Quantity | Frozen old path | Independently seeded/analytic value |
|---|---:|---:|
| logZ |0|0|
| mean |9.955|9.955|
| NLL |3.24791133746|3.24791133746|
| PIT |.959915679238|.959915679238|
| Eabs |4.960336305030|5.115336305030|
| CDF×survival integral |1.837094307503|1.837094307503|
| CRPS |3.123241997527|3.278241997527|

The missing Eabs is exactly.001×20+.009×15=.155. The component label splits are400 and75 local standard deviations. Analytic Gaussian-mixture CRPS and V3 agree; agreement between two integration implementations is not the ground truth.

Adding factors sigmoid(2−.2x)×sigmoid(−2+.4x) gives old Eabs5.185806099962, mode-seeded Eabs5.223412988431 and matching CDF-product1.614996058626. V3 CRPS3.608416929805 versus old3.570810041336. A separately authored direct grid (20/40/80 samples per smallest sigma) converges3.608416795662→3.608416896656→3.608416921705. Gaussian envelopes bound omitted probability≤2.20e−33 and absolute moment≤6.04e−32; grid discretization error is assessed separately. Both constructions give logZ−.951038642241, mean9.815104418315, NLL3.628284310655, PIT.975744604345 within the declared grid discretization tolerance.

A second zero-hazard counterexample uses weights1e−9,.2,.599999998,.2,1e−9 at means−10000,−1,0,1,10000 and sigma.1,1,1,1,.1. Analytic Eabs.945403111356 and CDF-product.668111567240 give CRPS.277291544116, matching V3. Old Eabs.945383111356 drops the rare tail absolute contributions, while old CDF-product.434246931334 also misses central transition area, returning CRPS.511136180022. No tiny component is removed in V3. These are synthetic method counterexamples, with no actual-data implication asserted.

## Scope and limits

Normal/empty-factor analytic scores, constant logistic likelihoods,19-edge censor factors, reactivation versus reset/calendar factors, translation invariance, zero weights, far labels, sharp slope rejection and finite-difference logZ derivatives are tested. Optional derivatives cover logits,means,log sigma,intercepts and slopes; they do not supply autograd through adaptive mesh or CRPS gradients.

32/64 estimates and two identities share the same continuous spectral CDF. Independent adaptive checks cover normalization,mean,NLL,CDF and mode-seeded Eabs, with independent GH checks. Direct-grid and analytic tests provide a third reference on chosen cases. Error estimates are not a formal uniform guarantee for every finite input. Extreme representation/bracketing failures are retained as failures. Hard resource containment and target Linux3.9 performance remain unverified in this packet. The current source is a potential numerical building block, not a new trained method or a claim of earthquake accuracy, novelty or published-benchmark superiority. Root must freeze any later adopted study and verify its runtime/data/checkpoint/scorer gates independently.
