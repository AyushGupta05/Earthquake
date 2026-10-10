# Independent audit of completed distribution grids

Both grids pass the independent artifact/metric audit. Both frozen scientific gates fail. These are completed negative comparisons, not evidence of a new method meeting the full project goal.

All figures below are candidate C minus reference, using the fixed **PMF mean** as primary. Negative errors favor C. Tables display eight decimal places; linked compact JSON retains full precision, absolute candidate/reference metrics, both seeds and secondary PMF-median decisions. The equal-PMF ensemble is evaluated after averaging distributions; it is not the average of seed errors.

Response support is 0.0–6.5; exposure support is 0.05–6.55, both in0.1 steps. These separate frozen grids must not be pooled or treated as the same baseline. All evaluation panels are held events drawn from the original TRAIN population; original DEV/TEST remains unread.

## Integrity and resource evidence

| Grid | Runs | Seed/ensemble score rows (each mean+median) | Comparisons | Audit seconds | Peak RSS GiB | MAE replay difference | Scientific gate |
|---|---:|---:|---:|---:|---:|---:|---|
| response | 8 | 72 | 6 | 33.932 | 4.480 | 0.0 | failed |
| exposure | 6 | 54 | 12 | 28.906 | 2.434 | 0.0 | failed |

The two audits and later compact extractions ran serially under two-CPU,12GiB,CUDA-hidden,600-second guards. Every service ended inactive/dead,Result=success,ExecMainStatus=0,MainPID=0. Checkpoints were byte-hashed; no forward inference or fitting occurred. Normalizer provenance, all completed runs, fitting schedules/sampler draws, metadata rows, PMF normalization, all main scores and fixed bootstrap/gate values were independently checked. Stratum/common-event subpanel metrics and raw waveform causality are outside this audit.

## Response C−B primary ensemble effects

| Seconds | Stations | Reference | Δ MAE | Δ MedAE | Δ M4 record MAE | Δ M4 event MAE | Δ CVaR95 | Δ weighted P95 | Δ maximum |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | seen | B native-late | +0.00063453 | +0.00311324 | +0.01954718 | +0.01178123 | +0.00065035 | -0.00021895 | +0.00107343 |
| 1 | held | B native-late | +0.00029206 | +0.00256971 | -0.00168838 | -0.00546671 | +0.00167172 | +0.00080844 | +0.07903326 |
| 3 | seen | B native-late | -0.00061692 | -0.00017819 | -0.01381377 | -0.01611754 | +0.00019879 | -0.00789577 | +0.00877515 |
| 3 | held | B native-late | -0.00005457 | -0.00163919 | -0.01190340 | -0.00895362 | -0.00168862 | -0.00727560 | +0.06064968 |
| 5 | seen | B native-late | -0.00031066 | -0.00060800 | +0.00767045 | +0.00247568 | -0.00244709 | -0.00276959 | +0.02056116 |
| 5 | held | B native-late | -0.00019914 | -0.00077264 | -0.02634982 | -0.01854098 | +0.00009342 | +0.00077386 | +0.04110976 |

| Seconds | Stations | Reference | 95% CI Δ bulk MAE | 95% CI Δ MedAE | 95% CI Δ M4 record MAE | 95% CI Δ M4 event MAE |
|---:|---|---|---|---|---|---|
| 1 | seen | B native-late | [-0.00026037, +0.00153818] | [+0.00058490, +0.00597607] | [+0.00647082, +0.03190770] | [-0.00127691, +0.02445383] |
| 1 | held | B native-late | [-0.00082955, +0.00133350] | [-0.00032182, +0.00530423] | [-0.01852727, +0.01455044] | [-0.02209004, +0.00935265] |
| 3 | seen | B native-late | [-0.00167852, +0.00049920] | [-0.00311564, +0.00254533] | [-0.03739375, +0.00664490] | [-0.03166276, -0.00112414] |
| 3 | held | B native-late | [-0.00110236, +0.00097643] | [-0.00421771, +0.00130946] | [-0.02752541, +0.00334224] | [-0.02416672, +0.00763933] |
| 5 | seen | B native-late | [-0.00138851, +0.00078805] | [-0.00288291, +0.00199823] | [-0.01481586, +0.03021325] | [-0.01186892, +0.01587516] |
| 5 | held | B native-late | [-0.00131729, +0.00084743] | [-0.00319456, +0.00217334] | [-0.04710061, -0.00752400] | [-0.03591091, -0.00310770] |

## Response both-seed patterns and failed criteria

Seed pair order is20261009 /20261010. The entries below are PMF-mean differences. Frozen gate results are preserved from the independent replay.

| Seconds | Stations | Reference | Δ bulk MAE, seeds | Δ MedAE, seeds | Δ M4 record MAE, seeds | Δ M4 event MAE, seeds | Δ CVaR95, seeds |
|---:|---|---|---|---|---|---|---|
| 1 | seen | B native-late | +0.00071201 / +0.00001807 | -0.00043650 / -0.00061313 | +0.02588085 / -0.00555185 | +0.01361623 / -0.00539549 | +0.00044778 / -0.00101001 |
| 1 | held | B native-late | +0.00016501 / +0.00089631 | +0.00163645 / -0.00139978 | -0.01719664 / +0.01670222 | -0.01566136 / +0.00816718 | +0.00060359 / +0.00796284 |
| 3 | seen | B native-late | -0.00008501 / -0.00053244 | -0.00231167 / +0.00030314 | +0.01204861 / -0.01515791 | +0.00414991 / -0.01169813 | +0.00251092 / -0.00445103 |
| 3 | held | B native-late | +0.00041272 / -0.00003096 | +0.00143949 / -0.00185834 | +0.00181978 / -0.00897288 | -0.00659472 / -0.00097633 | -0.00170560 / -0.00160442 |
| 5 | seen | B native-late | -0.00045622 / +0.00077203 | -0.00172215 / +0.00231518 | +0.02633025 / +0.00608673 | +0.00952886 / -0.00072816 | -0.00231771 / -0.00129990 |
| 5 | held | B native-late | -0.00040343 / +0.00105417 | +0.00163385 / +0.00139546 | -0.02705260 / -0.01316798 | -0.02685043 / -0.00277657 | -0.00832519 / +0.00572685 |

- 1s seen vs B native-late: 20261009 fails m4_weighted_mae, m4_event_macro_mae; CI upper-bound failures: medae, m4_weighted_mae, m4_event_macro_mae.
- 1s held vs B native-late: 20261010 fails m4_weighted_mae, m4_event_macro_mae; CI upper-bound failures: medae, m4_weighted_mae, m4_event_macro_mae.
- 3s seen vs B native-late: 20261009 fails m4_weighted_mae, m4_event_macro_mae; CI upper-bound failures: medae, m4_weighted_mae.
- 3s held vs B native-late: 20261009 fails m4_weighted_mae; CI upper-bound failures: m4_weighted_mae, m4_event_macro_mae.
- 5s seen vs B native-late: 20261009 fails m4_weighted_mae, m4_event_macro_mae; 20261010 fails medae, m4_weighted_mae; CI upper-bound failures: m4_weighted_mae, m4_event_macro_mae.
- 5s held vs B native-late: CI upper-bound failures: medae.

## Exposure C−A and C−B primary ensemble effects

| Seconds | Stations | Reference | Δ MAE | Δ MedAE | Δ M4 record MAE | Δ M4 event MAE | Δ CVaR95 | Δ weighted P95 | Δ maximum |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | held | A Huber+CE | -0.00143155 | -0.00322516 | +0.00605668 | +0.00297110 | -0.00044746 | +0.01148714 | -0.34113713 |
| 1 | held | B natural CE | +0.00103281 | -0.00656504 | +0.03053621 | +0.01439218 | +0.03571840 | +0.01710349 | +0.07391172 |
| 1 | seen | A Huber+CE | +0.00532198 | +0.00537269 | +0.00059835 | -0.00377080 | +0.00516342 | +0.01006184 | -0.02839259 |
| 1 | seen | B natural CE | +0.00441285 | +0.00015969 | +0.02634342 | +0.00677408 | +0.02883362 | +0.01732464 | +0.61587170 |
| 3 | held | A Huber+CE | +0.00005147 | -0.00544888 | +0.07498654 | +0.04647451 | +0.01735137 | +0.03618340 | -0.26674847 |
| 3 | held | B natural CE | -0.00169143 | -0.00346655 | +0.05058401 | +0.02440357 | +0.01277096 | +0.02478604 | +0.28208150 |
| 3 | seen | A Huber+CE | +0.00402204 | +0.00400407 | +0.02583720 | +0.00208663 | -0.00009279 | +0.00998210 | -0.35749016 |
| 3 | seen | B natural CE | +0.00416770 | +0.00124650 | +0.07527521 | +0.04242766 | +0.01848985 | +0.01844789 | +0.42915730 |
| 5 | held | A Huber+CE | -0.00077719 | -0.00758040 | +0.09506526 | +0.09427371 | +0.01708275 | +0.02363844 | -0.25990509 |
| 5 | held | B natural CE | +0.00160363 | -0.00512806 | +0.07778941 | +0.05748651 | +0.02690980 | +0.01519798 | +0.34969012 |
| 5 | seen | A Huber+CE | +0.00051109 | +0.00442175 | +0.03988446 | +0.03168623 | +0.00109450 | +0.00203080 | -0.03006605 |
| 5 | seen | B natural CE | +0.00344157 | +0.00634219 | +0.06852381 | +0.04068557 | +0.01913721 | +0.01917041 | +0.73534698 |

| Seconds | Stations | Reference | 95% CI Δ bulk MAE | 95% CI Δ MedAE | 95% CI Δ M4 record MAE | 95% CI Δ M4 event MAE |
|---:|---|---|---|---|---|---|
| 1 | held | A Huber+CE | [-0.00469565, +0.00178793] | not prespecified | not prespecified | [-0.03984315, +0.04617404] |
| 1 | held | B natural CE | [-0.00205894, +0.00436900] | not prespecified | not prespecified | [-0.03027395, +0.05499272] |
| 1 | seen | A Huber+CE | [+0.00208790, +0.00884757] | not prespecified | not prespecified | [-0.04098841, +0.03158908] |
| 1 | seen | B natural CE | [+0.00114781, +0.00785520] | not prespecified | not prespecified | [-0.02876783, +0.04360633] |
| 3 | held | A Huber+CE | [-0.00329395, +0.00341418] | not prespecified | not prespecified | [-0.00364487, +0.09631214] |
| 3 | held | B natural CE | [-0.00494373, +0.00176370] | not prespecified | not prespecified | [-0.02334948, +0.06833604] |
| 3 | seen | A Huber+CE | [+0.00063266, +0.00730953] | not prespecified | not prespecified | [-0.03768367, +0.04354232] |
| 3 | seen | B natural CE | [+0.00098623, +0.00728829] | not prespecified | not prespecified | [-0.00261147, +0.08188404] |
| 5 | held | A Huber+CE | [-0.00388035, +0.00253540] | not prespecified | not prespecified | [+0.04885114, +0.13865935] |
| 5 | held | B natural CE | [-0.00152631, +0.00479479] | not prespecified | not prespecified | [+0.02109876, +0.09098510] |
| 5 | seen | A Huber+CE | [-0.00240806, +0.00394663] | not prespecified | not prespecified | [-0.01173449, +0.07558083] |
| 5 | seen | B natural CE | [+0.00047633, +0.00680002] | not prespecified | not prespecified | [+0.00436556, +0.07865787] |

## Exposure both-seed patterns and failed criteria

Seed pair order is20261009 /20261010. The entries below are PMF-mean differences. Frozen gate results are preserved from the independent replay.

| Seconds | Stations | Reference | Δ bulk MAE, seeds | Δ MedAE, seeds | Δ M4 record MAE, seeds | Δ M4 event MAE, seeds | Δ CVaR95, seeds |
|---:|---|---|---|---|---|---|---|
| 1 | held | A Huber+CE | -0.00396443 / +0.00389261 | -0.00744229 / +0.00333405 | +0.01384225 / +0.00765518 | -0.00566691 / +0.01902868 | +0.02265974 / +0.00730352 |
| 1 | held | B natural CE | -0.00048915 / +0.00020822 | -0.01023033 / -0.00686729 | +0.03860228 / +0.05155188 | +0.01164503 / +0.04676243 | +0.04856367 / +0.04311543 |
| 1 | seen | A Huber+CE | +0.00490637 / +0.00628397 | +0.00282581 / +0.00243785 | +0.00402580 / -0.02835269 | -0.02110701 / -0.01428300 | -0.00468741 / +0.02854522 |
| 1 | seen | B natural CE | +0.00004129 / +0.00378678 | -0.00263777 / -0.00378775 | +0.03701895 / +0.03295116 | -0.00307071 / +0.03823322 | +0.00922448 / +0.04985535 |
| 3 | held | A Huber+CE | +0.00407696 / +0.00060363 | +0.00263998 / -0.00562177 | +0.03534093 / +0.08543453 | -0.00756574 / +0.06240534 | +0.03243294 / +0.02795894 |
| 3 | held | B natural CE | -0.00063209 / -0.00419982 | -0.00101962 / -0.00594327 | +0.05261701 / +0.08146220 | +0.00978075 / +0.08312274 | +0.02283539 / +0.00935575 |
| 3 | seen | A Huber+CE | +0.00143331 / +0.00698926 | +0.00078337 / +0.00689702 | +0.01729404 / +0.03654440 | -0.01654473 / +0.01598785 | +0.01818508 / +0.00487250 |
| 3 | seen | B natural CE | +0.00155790 / +0.00218544 | -0.00212222 / -0.00320376 | +0.06973214 / +0.12293520 | +0.02336043 / +0.10129561 | +0.02341674 / +0.02675247 |
| 5 | held | A Huber+CE | -0.00077920 / +0.00138778 | -0.00200818 / -0.00541491 | +0.05519247 / +0.10671817 | +0.06597799 / +0.10269492 | +0.01553576 / +0.02500497 |
| 5 | held | B natural CE | -0.00355915 / +0.00153636 | -0.00528912 / -0.00312040 | +0.05388518 / +0.11806076 | +0.01880405 / +0.12424079 | +0.02645390 / +0.02488204 |
| 5 | seen | A Huber+CE | -0.00262655 / +0.00233235 | +0.00076537 / +0.00109480 | +0.02383132 / +0.01152809 | +0.02977316 / +0.00107531 | -0.00051505 / +0.01462245 |
| 5 | seen | B natural CE | +0.00139513 / +0.00161099 | +0.00294062 / -0.00338284 | +0.08235943 / +0.07394512 | +0.04155434 / +0.06199258 | +0.00987843 / +0.02326853 |

- 1s held vs A Huber+CE: ensemble fails M4 event improvement <0.02; 20261010 M4 event MAE worsens; M4 event CI upper >=0.
- 1s held vs B natural CE: ensemble fails M4 event improvement <0.02; 20261009 M4 event MAE worsens; 20261010 M4 event MAE worsens; M4 event CI upper >=0.
- 1s seen vs A Huber+CE: ensemble fails weighted_mae, medae, M4 event improvement <0.02; bulk MAE CI upper >0.005; M4 event CI upper >=0.
- 1s seen vs B natural CE: ensemble fails weighted_mae, M4 event improvement <0.02; 20261010 M4 event MAE worsens; bulk MAE CI upper >0.005; M4 event CI upper >=0.
- 3s held vs A Huber+CE: ensemble fails M4 event improvement <0.02; 20261010 M4 event MAE worsens; M4 event CI upper >=0.
- 3s held vs B natural CE: ensemble fails M4 event improvement <0.02; 20261009 M4 event MAE worsens; 20261010 M4 event MAE worsens; M4 event CI upper >=0.
- 3s seen vs A Huber+CE: ensemble fails weighted_mae, medae, M4 event improvement <0.02; 20261010 M4 event MAE worsens; bulk MAE CI upper >0.005; M4 event CI upper >=0.
- 3s seen vs B natural CE: ensemble fails weighted_mae, M4 event improvement <0.02; 20261009 M4 event MAE worsens; 20261010 M4 event MAE worsens; bulk MAE CI upper >0.005; M4 event CI upper >=0.
- 5s held vs A Huber+CE: ensemble fails M4 event improvement <0.02; 20261009 M4 event MAE worsens; 20261010 M4 event MAE worsens; M4 event CI upper >=0.
- 5s held vs B natural CE: ensemble fails M4 event improvement <0.02; 20261009 M4 event MAE worsens; 20261010 M4 event MAE worsens; M4 event CI upper >=0.
- 5s seen vs A Huber+CE: ensemble fails medae, M4 event improvement <0.02; 20261009 M4 event MAE worsens; 20261010 M4 event MAE worsens; M4 event CI upper >=0.
- 5s seen vs B natural CE: ensemble fails weighted_mae, medae, M4 event improvement <0.02; 20261009 M4 event MAE worsens; 20261010 M4 event MAE worsens; bulk MAE CI upper >0.005; M4 event CI upper >=0.

## Interpretation preserved without threshold changes

Response: support is sufficient in all six panels. Only the5s held-station panel passes both-seed effects. Its ensemble tail-event MAE improves by0.01854098 and tail-record MAE by0.02634982; both tail intervals exclude zero. It still fails because the MedAE interval upper bound0.00217334 exceeds the frozen0.002 tolerance. The mean-action maximum error worsens in every response ensemble panel. The3s seen-station event-tail interval also excludes zero, but its seed consistency and record-tail/MedAE precision fail. These isolated effects do not satisfy the all-panel criterion.

Exposure: C minus natural CE has worse ensemble M4 event MAE in all six panels. Seed20261010 worsens on that metric in all six; seed20261009 worsens in five (the exception is1s seen stations). At5s held stations, both Huber and natural-CE comparisons have positive tail-event95% CI lower bounds, indicating regression within this exploratory resampling analysis. Both5s seeds worsen in both station panels against both references. No ensemble reaches the required0.02 event-tail improvement against either reference.

Worst-error behavior is separate from the frozen primary gate. Response C−B has at least one CVaR95/P95/maximum regression in27/36 seed-or-ensemble/action contrasts. Exposure has one in68/72. Against natural CE, all six exposure primary ensembles worsen all three worst-error statistics. Against Huber, exposure improves maximum error in all six ensembles but worsens P95 in all six and CVaR95 in four. A lower median error alone therefore does not meet the user’s combined rare-magnitude and worst-error objective.

Paired bootstrap intervals are exploratory and do not provide familywise confirmation, cross-region superiority or raw-stream causal guarantees. No model, threshold, support, seed, action or split was changed after these results.

## Exact compact evidence

- [response_effects_v1.json](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/independent_distribution_result_audit/response_effects_v1.json)
- [exposure_effects_v1.json](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/independent_distribution_result_audit/exposure_effects_v1.json)
- [response_receipt_v1.json](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/independent_distribution_result_audit/response_receipt_v1.json)
- [exposure_receipt_v1.json](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/independent_distribution_result_audit/exposure_receipt_v1.json)
- [REAL_AUDIT_EXECUTION.json](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/independent_distribution_result_audit/REAL_AUDIT_EXECUTION.json)
