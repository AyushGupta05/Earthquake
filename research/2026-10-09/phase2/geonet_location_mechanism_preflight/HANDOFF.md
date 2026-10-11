# Location mechanism handoff

**The fixed synthetic mechanism gate failed; no geometry fit is earned.** [REPORT.md](REPORT.md) gives the derivation, exact criteria, all twelve arrival-only comparisons, six base joint comparisons and primary links. [CALCULATIONS.json](CALCULATIONS.json) retains every arm, mean/median decision and proper score. This is a chosen toy failure, not a universal impossibility for learned nonlinear current-arrival fusion.

- Linear conditional means integrate to the same prediction as the matched E[log R] plug-in; maximum observed arithmetic difference is 7.99e−15. A moment-matched Gaussian has exactly the same primary errors as its mixture.
- One shared source induces correlated station distances. In this toy, independent draws reduce average-log-distance variance from 0.209065 to 0.070209 and invent six impossible source combinations. Their occasional tail gains do not preserve all other criteria.
- Timing-only location weights omit amplitude evidence. Exact joint weighting strongly improves bulk/proper scores, but still fails the all-duration tail criterion; its one-report tail and maximum errors worsen versus ElogR.
- Both fixed seeds fail the arrival-only guard at all three snapshots in base and locator-stress regimes. The first-report magnitude–distance alias remains prior dependent, and overconfident wrong geometry can leave large-event errors despite unbounded magnitude support.

[ANALYTIC_CASES.json](ANALYTIC_CASES.json) contains explicit invented inputs/component weights for independent recalculation. Nine scalar quadrature checks agree within 7.11e−15. The original NumPy matrix warnings remain recorded in [WARNING_CHECK.json](WARNING_CHECK.json): all saved values are finite, and explicit broadcast means agree within 1.43e−14; the warning cause is undiagnosed.

Ordinary currently observed arrival times remain a defensible baseline input if independent data support that test. A later learned coupling must share geometry labels, out-of-fold predictions, full location summaries/ElogR, capacity and observations with direct/point controls. Generic location marginalization and robust timing inference already have close prior art. No TRAIN data, acquisition, learned fits, persistent Python implementation, reviewer, AWS or Git was used here.
