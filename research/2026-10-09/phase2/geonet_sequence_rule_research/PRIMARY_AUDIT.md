# Additional primary-paper and clock-support audit

## September 2026 LLM characterization paper

Bassani et al. fine-tune TinyLlama with LoRA on INSTANCE-v2 station coordinates, relative P times and vertical PGV in a 0.2-second window centered on each pick. They retain arrivals within five seconds of the first and require at least five stations, velocity records and bulletin S picks for the comparison cohort. Their 30,879-event final dataset has only two events in [6,7); it is not a GeoNet Mw-tail benchmark. Reported test magnitude MAE is .20, versus .24 for the one-chunk temporal split. Underestimation above M4 remains. In the fastest INGV automatic-pick comparison, magnitude MAE is .32 for the LLM versus .24 for INGV. Location improvements must not be described as a magnitude win. Neither the abstract nor those aggregates establish strict matched1/3/5 performance. [Primary paper](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2026JH001578).

The author repository identifies INSTANCE-v2 and contains data-formatting, split, fine-tuning and evaluation folders. Only its README/file list was accessed; the Data tree request failed, so no implementation equivalence is claimed. No author code was executed. [Author source](https://github.com/AuroraBassani/LLM-for-Earthquake-Characterization).

Our inference: a PGV window centered on a pick can require data after that pick. A strict wall-clock control must crop every station at the global deadline, including stations arriving immediately before it. This is a prospective comparability check, not a demonstrated bug in the authors' implementation. A costly LLM fit is not earned by this paper alone.

## Physical sequence identification versus exploratory graph percolation

Zaliapin and Ben-Zion2020 distinguish cluster identification from declustering. Their method uses directed nearest-neighbor proximity, spatial background normalization from reshuffled catalogues and stochastic thinning. It is not a fixed all-pairs distance/time connected-components graph. The threshold directly affects retained background counts; the paper recommends estimating spatial dimension for the catalogue and discusses parameter sensitivity. The result is a statistical background classification, not certainty of physical independence. [Author paper](https://zaliapin.github.io/pubs/Zaliapin_Ben-Zion_JGR20.pdf).

A public implementation of the2013 cluster algorithm explicitly distinguishes that predecessor from the2020 declustering method. The repository was inspected as source context only, not executed. [Author implementation](https://github.com/dttrugman/Nearest_Neighbor_Cluster).

Our inference: the existing90-day/150-km CMT graph's3,080-event component across2005–2024 can arise through transitive bridges. Its89-event TEST ceiling is a result of that frozen heuristic, not proof that those events form one physical sequence or that every event pair leaks. The original30-day and90-day outputs remain immutable. Do not switch rules merely to pass a support floor. Before a larger benchmark, define a source-backed evaluation target, catalogue completeness limits and independent split/embargo controls prospectively; sparse selected CMT data are not automatically a complete catalogue suitable for transplanting a background-rate estimator. No new rule, graph, exclusion or acquired cohort is created here.

## Separate association-clock ceiling

The independent495 replay shows49candidateTEST Mw>=5.5 events, with22 positive but unresolved P-reference structures. Four of those22 are Mw>=6. If a future primary analysis requires a fully resolved associated-pick clock, the arithmetic ceilings are27Mw>=5.5 and15Mw>=6 before waveform or sequence attrition. The27 ceiling is below the proposed30-test-tail floor. This is a conditional support calculation, not an exclusion from the frozen metadata/counts screen or proof that every missing pick preceded acceptedT0. Accepted-subset timing remains a separately qualified retrospective estimand. [Independent metadata evidence](../geonet_bulk_independent_audit/COMPLETED495_RESULTS.md).

The current96-event screen remains frozen at its accepted-subset clock and retains incomplete cases. An official-source completeness audit is being prepared before interpreting any later first-arrival benchmark. No live event query, refetch, request-flag experiment, new model or AWS action occurred.
