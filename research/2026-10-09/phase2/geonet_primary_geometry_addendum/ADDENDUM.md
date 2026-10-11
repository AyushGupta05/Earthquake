# Focused geometry prior-art update, 11 October 2026

Distance-aware neural supervision and robust probabilistic location already have relevant prior art. Neither new search result demonstrates the proposed integrated Mw model or matched 1/3/5-second performance.

TREAD's indexed publisher abstract describes station-to-target distance regression as an auxiliary task for a transformer predicting ground shaking on Taiwan and Japanese networks. This narrows any claim that geometry-aware attention or distance supervision is new. The direct publisher page returned403 here; full equations, splits and numeric comparisons remain unverified. [Publisher DOI](https://doi.org/10.1785/0220260045).

The full March2026 arXivv2 location manuscript models heavy-tailed timing noise with a Student-t scale mixture and separate contamination probabilities, using a neural travel-time surrogate for posterior sampling. Its task is robust catalogue location. It supports a locator-misspecification control, not an EEW magnitude improvement claim. Use the primaryv2 title, because the search-indexed title differs. [Primary full text](https://arxiv.org/html/2512.06407v2).

The June2026 INSTANCE magnitude/distance paper is already recorded in the amplitude/source-scaling audits: pseudo-normalization, preserved amplitude and Gaussian outputs are existing ideas. The publisher's indexed abstract is accessible but a direct full-page request returned403. Its aggregate .1977 magnitude MAE is not a matched first-arrival1/3/5 result. [Publisher abstract](https://doi.org/10.1016/j.acags.2026.100356).

No model, acquisition or protocol changes follow from these reads. Preserve direct timing/geometry fusion and shared auxiliary supervision as controls. A robust location density alone cannot establish a magnitude point-error benefit; test coherent marginalization against point geometry and E[log distance] under the same information and capacity.
