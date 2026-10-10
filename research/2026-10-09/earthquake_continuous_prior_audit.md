# Continuous prior adjustment: source and mathematical audit

The Chile sampler repeats original labels by right-closed magnitude bands: factors 1, 8, 16, 32, 64 and 128 through M≤9, then resets to 1 above 9. It also perturbs labels with magnitude-dependent Gaussian noise. Dividing the resulting forecast by a smooth exponential—or even the exact repeat factor evaluated at the perturbed label—does not generally recover the original-label posterior.

An invented M=5 example isolates this failure: the noisy natural and repeated-label distributions are identical, yet inverse correction at the noisy label moves the mean to 4.98670. Exact piecewise Gaussian integrals agree with numerical quadrature to 3.34e−13. These are arithmetic checks, not earthquake performance results.

The source likelihood floor adds another limitation to an exact posterior-recovery claim. Inverse exposure also moves predictions downward where the repeat law is increasing; it is not a justified default remedy for underestimated large earthquakes. Normalized continuous prior adjustment has established prior art, including [Balanced MSE](https://openaccess.thecvf.com/content/CVPR2022/html/Ren_Balanced_MSE_for_Imbalanced_Visual_Regression_CVPR_2022_paper.html).

No extra fit is justified by this audit. The frozen clock control remains unchanged, and the completed negative INSTANCE categorical experiment is kept separate from the continuous Chile problem.

The later [rupture-source audit](earthquake_rupture_survival_audit.md) also finds direct EEW inverse-upsampling prior art in the 2022 rupture-predictability study, under a different sampler.

[Exact laws, derivations and source pins](phase2/chile_continuous_prior_audit/AUDIT.md)
