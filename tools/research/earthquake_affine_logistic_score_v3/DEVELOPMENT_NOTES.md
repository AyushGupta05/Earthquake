# Retained synthetic negative findings

1. Initial tests incorrectly treated the preserved old nested CRPS as a universal reference. The remote-narrow-mode tail case disagreed by0.037606888469. Independent analytic zero-hazard and converging nonzero-hazard grids verified the old missed-mode cause; frozen predecessors were not changed. Tests now separate valid scalar likelihood/CDF agreement from independently established CRPS.
2. An initial rare-tail assertion that CRPS should exceed0.3 was false; the analytic value is0.277291544116. It was replaced by the analytic identity, including separate absolute/pair moments and the old CDF-transition failure. No runtime threshold was relaxed.
3. A draft grid helper used a NumPy integration alias unavailable on the current NumPy version; it now uses SciPy trapezoid, compatible with the target declared SciPy family. A draft variable-shadowing error in diagnostic mean was caught by independent scalar-field tests and corrected before review.
4. Finite parameters a−40,b.01 can yield a rounded root bracket endpoint with the wrong derivative sign. New source explicitly refuses that bracket rather than silently repairing support/parameters; production/reference representation failures remain unknown. The19-edge extreme-normalizer test uses the exact constant-factor operator to verify subnormal-scale likelihood handling without claiming all finite parameter sets are representable.
5. Sharp b20 GH64/128 disagreement remains a mandatory failure; diagnostic evaluation has acceptedFalse. Legacy broad/narrow and far-label CRPS failures remain reported.

Only invented source/test inputs were used. No scientific negative result was erased, actual outcome inspected, model fitted, provider queried, dependency installed or AWS/Git mutated.
