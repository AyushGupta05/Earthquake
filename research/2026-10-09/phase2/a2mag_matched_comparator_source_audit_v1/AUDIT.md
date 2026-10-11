# A2MAG matched-comparator source audit

Checked 11 October 2026 UTC. **A clock adaptation is supportable; a faithful implementation is not yet verified.** This documentation-only pass inspected the existing authored reviews and inert cached publisher text, then followed this paper's official PDF, supplement and code links. Other previously audited models were not re-audited. No private metadata, datasets, author code, accounts or AWS were accessed.

The [publisher page](https://www.nature.com/articles/s44304-026-00242-3) lists publication on 29 June 2026. The accessible [accepted manuscript](https://www.nature.com/articles/s44304-026-00242-3_reference.pdf) remains an unedited article in press. The current Version of Record was not established.

The following compact evidence and adaptation use fewer than 200 words derived from that manuscript:

| Boundary | Verified description or explicit limit |
|---|---|
| Architecture, pp. 26–28 | U-net, four Conv2D stages (8/16/32/64 formula); kernel 5, strides 1/2, same padding, BN/LeakyReLU, sequence LSTM/attention, mirrored upsampling/skips/cropping, Conv2D output. MSE/Adam .001; ≤500 epochs; patience 20. |
| Clock/label, pp. 28–29 | 100 Hz (600,1,3), six seconds: training 1–5 post-P plus remaining pre-P; test 3+3. Labels 0 before P/Mj+1 afterward; output (600,1,1); event threshold .5. |
| Split/selection, pp. 7–9 | Events 60/10/30; eight nearest stations' records for training; single-station inference. Station disjointness/seed/manifest unstated. STA/LTA 2/5 seconds, threshold 1.75; demean/1–10 Hz; distance<150 km/depth<100 km/SNR>10 dB; SNR uses ten seconds post-P. |
| Limits | Filter causality/order, normalization/units, attention/scalar reduction and split rows unverified; 3,759 called records/events. |
| High M, pp. 10, 22 | MAE .33; underestimation; bias approximately .8 (M6–7), 1.2 (M7–8); bin counts unverified. |
| Adaptation | Six seconds ending tP+h (h=1/3/5); 6−h pre-P. Only h=3 repeats reported test geometry. |

The publisher lists [supplementary DOCX](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs44304-026-00242-3/MediaObjects/44304_2026_242_MOESM1_ESM.docx); its browser open failed, and one bounded retrieval timed out with zero bytes. The manuscript points to [code DOI 10.5281/zenodo.18050454](https://doi.org/10.5281/zenodo.18050454); the DOI and record landing opens failed. No release version, contents, executable correspondence or immutable code hash was verified. Failed retrieval does not establish that either resource is absent.

For a future same-data comparator, the proposed six-second geometry is one precise **A2MAG-style adaptation**, pending those implementation details. Our controls, not claims from the authors: preserve the same event split, label scale, station eligibility and training budget across arms; use only data available by each cutoff for demeaning/filtering and fit normalization on TRAIN; keep a retrospective P-labelled arm separate from a causal trigger arm with measured trigger availability. Do not use future SNR as an online admission gate. Report event-level errors, signed high-magnitude bias, sample counts and paired uncertainty; examine a station holdout separately. Geometry alone establishes neither a first-network-P clock nor online feasibility. Published Japanese Mj scores are context, not a matched leaderboard, novelty or superiority result. No implementation or acquisition is authorized by this packet.

The bounded pass used five targeted queries and seven conservative primary-open attempts (one was a direct supplement request), plus six PDF text finds and one failed figure screenshot. Source metadata and failures are recorded separately. No raw third-party content is in this curated packet.
