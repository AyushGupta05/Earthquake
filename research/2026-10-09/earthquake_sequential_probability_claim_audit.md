# Sequential distributions: overlap, entropy and the novelty boundary

Checked 10 October 2026. This is a mathematical and primary-source audit, with no new waveform reads, predictions, fits or paid resources. It does not propose a validated new loss. The failed censored-innovation, growth and revision pilots remain negative evidence; this note does not reopen them.

The user's idea of using the one-second distribution as a prior for three seconds is legitimate only with an incremental evidence model. Let X1 be the already observed prefix and Z the newly observed interval. Bayes gives

`p(M | X1,Z) ∝ p(M | X1) p(Z | M,X1)`.

If q3 already estimates `p(M | X1,Z)`, multiplying q1 and q3 counts X1 twice. For example, a prior tail probability 0.2 and likelihood ratios 1/9 then 9 yield q1=1/37 and q3=0.2. Normalizing the product of those two binary posteriors produces tail probability 1/145≈0.00690, despite correct q3=0.2. A ratio q3/q1 can be an algebraic update on shared support, but it merely recovers q3; it supplies neither new evidence nor a performance claim. Learned increments need an equally optimized direct-prefix null and explicit support/overlap controls.

A calibrated sequence has a conditional, rather than samplewise, consistency requirement. For a fixed magnitude threshold a and nested information sets F1⊂F3, the tower law gives

`E[P(M≥a | F3) | F1] = P(M≥a | F1)`.

A June 2026 primary preprint treats fixed-event probability forecasts as measure-valued martingales and develops synthetic-PIT calibration tests. It also explains why forcing each adjacent KL revision to have expectation zero would force unchanged distributions. Thus temporal distribution coherence is established statistical prior art, not a new EEW principle. [Wilkinson & Ferro, 2026](https://arxiv.org/html/2606.31621v1)

The binary example above also shows why entropy need not decrease on every event path: entropy rises when probability moves from 1/37 to 0.2 after surprising evidence. Under correct conditioning, uncertainty decreases in expectation. A penalty demanding monotonically shrinking entropy for every earthquake could suppress a justified tail revision. A one-step KL penalty similarly needs a model of forecast revisions; closeness alone cannot define correctness.

Sequential Bayesian estimation is established within EEW as well: a 2015 primary paper uses model-class selection and a sequential proposal to infer parameters for concurrent earthquakes. Its reported alarm improvement concerns a distinct multi-event task, not this project's magnitude-error benchmark. [Multi-event Bayesian EEW, 2015](https://authors.library.caltech.edu/records/0cdjs-00z18)

A defensible later coherence experiment would first diagnose predictable probability revisions on event-disjoint data, then compare an optimized direct density against a conditionally constrained density at identical capacity, clock distribution and budget. Samplewise teacher matching is a separate control, not the martingale property. No threshold or critic would use future observations at deployment. Proper scores, point errors, tail-event errors and CVaR would all need independent evaluation; calibration alone cannot guarantee smaller tail MAE. Current small tail support and negative revision results do not earn such a fit yet. The matched clock control and independent-tail catalogue census have clearer immediate prerequisites.
