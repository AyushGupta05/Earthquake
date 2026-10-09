# Historical-waveform retrieval: closer prior art

9 October 2026. Research-only addendum; no retrieval model or earthquake result is claimed.

**Generic retrieval of similar past earthquakes is already an EEW method.** [Lin, Chen and Chen, RATE, IEEE GRSL 2025, DOI10.1109/LGRS.2025.3598322](https://ieeexplore.ieee.org/abstract/document/11124201/) describes retrieving historical events from initial P-wave similarity and incorporating them in a Transformer for regional ground-motion prediction on Japan/Taiwan. The publisher abstract is accessible through its search index; the full article did not open in this session. It is not a verified 1/3/5-second magnitude benchmark.

The [author's 2025 EQ-RAG thesis record](https://ndltd.ncl.edu.tw/cgi-bin/gs32/gsweb.cgi/login?o=dnclcdr&s=id%3D%22113NTUS5392017%22.&searchmode=basic) independently confirms the historical-event/Transformer intensity-prediction direction. I did not obtain its full text.

An [official Taiwan CWA research report, subproject2 chapter3, pp.65–78](https://scweb.cwa.gov.tw/webdata/PDF/Reports/motc-cwa-113-e-06.pdf) provides an inspectable related implementation description: databases indexed by observation time; retrieval from station-wise peak three-component amplitude; L2/cosine/inner-product alternatives; waveform and station-coordinate fusion through shared convolutions and a Transformer. Its training can retrieve the current event; inference takes the closest reference. It evaluates PGA/alerts against TEAM, with chronological train/validation/test years. These report details must not silently be attributed to the final RATE article. The code and exact reference-database exclusions remain unverified.

For our proposed same-path reference experiment, the potential distinction is narrower: use an earlier recording to constrain a causal relative-source forward model, quantify reference mismatch and unresolved source directions, and marginalize that uncertainty in the early magnitude distribution. Retrieval, empirical Green's functions and marginalization are all established. Combining their names is insufficient novelty.

A fair future test therefore needs a simple same-input retrieved-pair neural model alongside the physical forward construction, plus reference-label-only and deliberately mismatched-path controls. Fit/evaluation events must never retrieve themselves or future events. Every eligible event, including those without a useful reference, must remain in overall reporting. Catalogue-location retrieval is an oracle mechanism diagnostic and cannot count as deployable EEW. Passing that diagnostic would only justify testing causal waveform-based retrieval; it would not establish a published-benchmark win.

This addendum tightens the novelty boundary in [the missing-evidence memo](earthquake_missing_evidence_hypotheses.md). The running polarization and response-conditioning protocols are unchanged.
