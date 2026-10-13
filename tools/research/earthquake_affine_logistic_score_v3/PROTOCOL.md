# Numerical operator and independent checks

This package preserves Gaussian-mixture×affine-logistic multiplication over the real line. “Exact operator” describes that mathematical choice; every reported score is a controlled numerical approximation, not a symbolic exact integral. No model/checkpoint/data transformation or outcome threshold is changed.

Each positive-weight Gaussian times the logistic factors is strongly log-concave: its log second derivative is at most−1/sigma². A unique mode is bracketed by mu+sigma²∑min(b,0) and mu+sigma²∑max(b,0). These brackets are used for mode roots only. Floating-point endpoint sign inconsistencies fail closed. A center and scale from all active modes define `x=center+scale*t/(1−t²)`,−1<t<1; endpoints represent±infinity. Integration includes both open tail intervals. Knots at means/modes/local scales/logistic transitions/label are partitions; none is a magnitude support cutoff.

Vectorized32/64 Gauss-Legendre rules evaluate density and likelihood across intervals. A Legendre polynomial interpolant has a continuous analytic antiderivative, providing CDF and survival with separate forward/reverse sums. The [official SciPy roots_legendre documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.roots_legendre.html) describes the quadrature rule; the compactification, CDF primitive, refinement and acceptance checks are authored here. This rule's polynomial guarantee does not itself certify our nonpolynomial density.

For continuous q, F and survival S, mean μq, and finite first moment:

- Eabs = E|X−y|.
- E|X−X′|/2 = ∫F(x)S(x)dx = E[(X−μq)(F(X)−S(X))].
- CRPS = Eabs−E|X−X′|/2.

The last expectation gives a single density quadrature using the continuous CDF, eliminating nested scalar CDF integration. The integral of F×S is computed independently as a second **identity on the same spectral CDF** and compared; it is not an independent CDF implementation.32/64 score checks trigger bounded interval refinement. Quantiles are roots of the continuous compact CDF, not node-rounded sample quantiles.

Separate checks use positively pinned prior authored component-scaled adaptive integration for Z,mean,NLL and target/quantile CDFs. An added mode-seeded independent absolute-moment check partitions every component around−8,−4,−1,0,1,4,8 plus the label and infinite tails. The copied prior reference remains byte-identical; its known flawed legacy CRPS method is used only in diagnostics/benchmarks, never in V3 acceptance. Mandatory NumPy GH64/GH128 comparison remains for Z/mean/NLL. A sharp synthetic case intentionally fails that gate even when other methods agree. No fail-open GH, support truncation, sigma clipping or Gaussian substitution exists.

Independent CRPS validation in tests uses an independently authored analytic Gaussian-mixture identity when factors are empty: A(d,s)=2sφ(d/s)+d(2Φ(d/s)−1), CRPS=∑wA(y−mu,s)−0.5∑ww′A(mu−mu′,sqrt(s²+s′²)). Nonzero-factor tests use a separately authored direct dense magnitude grid, cumulative trapezoid CDF and repeated grid refinement. That diagnostic grid has finite support **only for reference work**, and its omitted tails have explicit Gaussian envelope bounds; the accepted V3 scorer always has all-real support.

For each independently computed anchor x0, derivative d0, component log value h0, curvature K=1/sigma²+∑b²/4: h0+d0*u−Ku²/2 ≤ h(x0+u) ≤ h0+d0*u−u²/(2sigma²). The lower Gaussian integral gives a positive lower bound for whole Z, while the upper Gaussian gives probability/absolute-moment bounds outside the grid endpoints. This does not assume a floating-point root is an exact mode. Grid error is assessed by20/40/80 refinement separately from analytic tail bounds; floating-point calculations are not interval-certified.

An optional logZ gradient computes posterior expectations of analytic score derivatives, checked32/64 and against central finite differences on invented cases. This is useful for assessing a later differentiable integration design, not a ready training-autograd replacement. Adaptive topology is nondifferentiable and gradients of downstream scores are outside this API.

No actual outputs, candidate implementation/tests, provider/AWS calls, installs or shared Git operations occur. No novelty, empirical earthquake accuracy, published-benchmark superiority, model readiness or production containment claim follows from synthetic numerical correctness/speed. Any adoption is a new parent-frozen study, with independent target-runtime verification and actual scorer/checkpoint gates.
