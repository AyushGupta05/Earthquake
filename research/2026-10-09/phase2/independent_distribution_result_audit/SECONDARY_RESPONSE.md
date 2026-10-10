# Exploratory response controls: native units and gain augmentation

These are the two additional comparisons requested after the primary report: **B−A** (native-unit amplitudes with late metadata versus count amplitudes with late metadata) and **D−A** (counts with coherent digital-gain augmentation versus counts without augmentation). The original **C−B primary gate remains rejected and unchanged**. No new fit, prediction scoring, confidence interval, threshold, success criterion, hypothesis search or point-action selection was performed.

The source is the same independently audited completed response grid. Its PMF support is **0.0, 0.1, …, 6.5**. Do not combine these controls with the separate exposure grid, whose support is 0.05, 0.15, …, 6.55. Every comparison below uses identical observed held-event panels, with seen/held station grouping; these panels come from original TRAIN, not original DEV or TEST. Each panel has 66 M≥4 events.

Native preprocessing gives a repeatable bulk transfer effect: for PMF means, B improves both weighted MAE and MedAE on held stations at 1/3/5 seconds in both individual seeds and their equal-PMF ensemble. It does not give a repeatable rare-magnitude or worst-error improvement. Ensemble M≥4 event MAE and CVaR95 each worsen in five of six panels; seed 20261010 worsens M≥4 event MAE in every panel. The PMF-median ensemble has higher CVaR95 in all six panels.

Gain augmentation also fails to improve rare and worst errors consistently. For PMF means, D has worse ensemble M≥4 record MAE, M≥4 event MAE, and CVaR95 in all six panels. Both seeds worsen M≥4 event MAE in five of the six panels together; at 3 seconds/held stations only the first seed improves. Seen-station bulk MAE worsens at every horizon in both seeds. Held-station bulk MAE improves at 1/3 seconds in both seeds; the 5-second effect disagrees across seeds. Its PMF-median ensemble worsens both M≥4 MAEs in all six panels.

These are descriptive secondary effects. No uncertainty calculation or new pass/fail criterion was applied, and favorable subsets are not a replacement for the rejected primary hypothesis. Maximum error is a single-extreme observation and can disagree with CVaR/P95.

All values are **candidate minus A** in magnitude units: negative lowers the named error. Tables display eight decimal places; the JSON preserves exact values and all absolute candidate/reference metrics. Mean and median actions remain separate. Tiny signed zeros in quantized median statistics are floating-point effects, not evidence of a material gain.

## PMF mean, B−A: native preprocessing

| Identity | Seconds | Stations | ΔMAE | ΔMedAE | ΔM4 event MAE | ΔM4 record MAE | ΔCVaR95 | Δweighted P95 | Δmaximum |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble | 1 | seen | +0.00145336 | -0.00327100 | +0.01071717 | +0.02434367 | +0.01093480 | +0.00655530 | +0.43764346 |
| ensemble | 1 | held | -0.00314693 | -0.00146021 | +0.00278087 | -0.01107632 | +0.00524748 | +0.00381264 | -0.06912295 |
| ensemble | 3 | seen | -0.00002277 | +0.00009974 | +0.00937827 | +0.01025570 | +0.00773477 | +0.00448931 | +0.12528898 |
| ensemble | 3 | held | -0.00504100 | -0.00631631 | +0.02598089 | +0.01617754 | +0.00555387 | -0.00419374 | -0.00046344 |
| ensemble | 5 | seen | +0.00023329 | +0.00154554 | -0.00051791 | +0.00606866 | +0.00572141 | -0.00033453 | +0.10490987 |
| ensemble | 5 | held | -0.00391476 | -0.00520303 | +0.00988775 | +0.01262515 | -0.00346515 | +0.00645138 | -0.06415168 |
| 20261009 | 1 | seen | +0.00225634 | +0.00161680 | +0.01734842 | +0.03559381 | +0.01515453 | +0.01201910 | +0.26262821 |
| 20261009 | 1 | held | -0.00141458 | -0.00190500 | -0.01633044 | -0.01752122 | +0.00957033 | -0.00228472 | +0.14889291 |
| 20261009 | 3 | seen | +0.00116968 | +0.00288902 | -0.00587537 | +0.01141548 | +0.00575402 | +0.01551716 | +0.05972809 |
| 20261009 | 3 | held | -0.00404518 | -0.00850354 | +0.00352713 | -0.01026180 | +0.01163174 | -0.00605657 | +0.00868127 |
| 20261009 | 5 | seen | +0.00258469 | +0.00307243 | -0.03179184 | -0.00050008 | +0.00684446 | +0.00631607 | -0.04739527 |
| 20261009 | 5 | held | -0.00058846 | -0.00061231 | +0.01289151 | +0.01759710 | +0.00850964 | +0.00703219 | -0.01953172 |
| 20261010 | 1 | seen | +0.00171742 | -0.00229320 | +0.00415160 | +0.01531141 | +0.01115466 | +0.00020505 | +0.36172690 |
| 20261010 | 1 | held | -0.00292226 | -0.00362718 | +0.02543236 | -0.00066575 | +0.00114080 | +0.00612107 | -0.10199341 |
| 20261010 | 3 | seen | -0.00044856 | -0.00387230 | +0.01395945 | -0.00336580 | +0.00700140 | +0.00328270 | +0.19084986 |
| 20261010 | 3 | held | -0.00417454 | -0.00715678 | +0.03092946 | +0.02995152 | +0.00592751 | +0.00639305 | -0.00960815 |
| 20261010 | 5 | seen | -0.00346701 | -0.00540391 | +0.02861034 | +0.00913559 | +0.00154402 | -0.00340201 | +0.35594561 |
| 20261010 | 5 | held | -0.00706717 | -0.00806117 | +0.00398689 | +0.00618415 | -0.00985392 | -0.00208234 | -0.01814074 |

## PMF mean, D−A: coherent gain augmentation

| Identity | Seconds | Stations | ΔMAE | ΔMedAE | ΔM4 event MAE | ΔM4 record MAE | ΔCVaR95 | Δweighted P95 | Δmaximum |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble | 1 | seen | +0.00143145 | -0.00101576 | +0.02095996 | +0.03074813 | +0.00740726 | -0.00457601 | +0.45956940 |
| ensemble | 1 | held | -0.00403236 | -0.00287137 | +0.02527744 | +0.01543962 | +0.00296081 | -0.00253690 | +0.07841313 |
| ensemble | 3 | seen | +0.00383104 | +0.00510642 | +0.02210511 | +0.02417395 | +0.00774937 | +0.00050354 | +0.19064856 |
| ensemble | 3 | held | -0.00204675 | -0.00351218 | +0.01223189 | +0.01000447 | +0.00335402 | +0.00154277 | -0.02551205 |
| ensemble | 5 | seen | +0.00377100 | +0.00707268 | +0.00411639 | +0.00776974 | +0.00706683 | -0.00188521 | +0.13686647 |
| ensemble | 5 | held | -0.00097940 | -0.00156362 | +0.01682707 | +0.00664862 | +0.00463864 | +0.00916227 | +0.02176004 |
| 20261009 | 1 | seen | +0.00216215 | +0.00173992 | +0.03085787 | +0.03392325 | +0.00698715 | +0.00649650 | +0.38745843 |
| 20261009 | 1 | held | -0.00468438 | -0.00547124 | +0.00883223 | +0.00434351 | +0.00287623 | -0.01314327 | +0.05970915 |
| 20261009 | 3 | seen | +0.00499255 | +0.00416948 | +0.01480455 | +0.01883751 | +0.00403656 | +0.01692729 | +0.04543612 |
| 20261009 | 3 | held | -0.00036636 | -0.00196362 | -0.00365874 | -0.00969834 | +0.00783971 | +0.00375456 | -0.05980518 |
| 20261009 | 5 | seen | +0.00417465 | +0.00529006 | +0.01160190 | +0.02596850 | +0.00651437 | +0.00439805 | -0.07622449 |
| 20261009 | 5 | held | -0.00078565 | -0.00082215 | +0.01978402 | +0.01198860 | +0.01073966 | +0.01067687 | +0.00477123 |
| 20261010 | 1 | seen | +0.00168978 | -0.00080175 | +0.01432719 | +0.03126388 | +0.00455659 | +0.00023113 | +0.43685347 |
| 20261010 | 1 | held | -0.00167897 | -0.00233885 | +0.05275113 | +0.04064647 | +0.00339916 | +0.00960134 | +0.03418107 |
| 20261010 | 3 | seen | +0.00480553 | +0.00495539 | +0.01592947 | +0.01149252 | +0.00948322 | +0.00336226 | +0.33586100 |
| 20261010 | 3 | held | -0.00195435 | -0.00404697 | +0.01646596 | +0.02159640 | +0.00620839 | +0.00059231 | +0.00878108 |
| 20261010 | 5 | seen | +0.00467356 | +0.00324633 | +0.01828812 | +0.01858199 | +0.00731879 | +0.00289776 | +0.40150083 |
| 20261010 | 5 | held | +0.00031589 | +0.00262002 | +0.01569718 | -0.00051868 | -0.00022520 | +0.00144717 | +0.03874886 |

## PMF median, B−A: native preprocessing

| Identity | Seconds | Stations | ΔMAE | ΔMedAE | ΔM4 event MAE | ΔM4 record MAE | ΔCVaR95 | Δweighted P95 | Δmaximum |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble | 1 | seen | +0.00154747 | +0.00000000 | +0.01439394 | +0.02712491 | +0.00812708 | +0.00000000 | +1.00000000 |
| ensemble | 1 | held | -0.00285631 | +0.00000000 | -0.00138889 | -0.00858369 | +0.00281078 | -0.00000000 | -0.10000000 |
| ensemble | 3 | seen | -0.00015667 | -0.10000000 | +0.00000000 | -0.01242257 | +0.00385173 | +0.00000000 | +0.20000000 |
| ensemble | 3 | held | -0.00452393 | +0.00000000 | +0.01502525 | +0.01309013 | +0.00114629 | +0.00000000 | +0.00000000 |
| ensemble | 5 | seen | +0.00093423 | +0.00000000 | +0.00871212 | +0.03251893 | +0.00758428 | -0.00000000 | +0.20000000 |
| ensemble | 5 | held | -0.00293797 | +0.00000000 | +0.02891414 | +0.03118741 | +0.00190002 | +0.00000000 | +0.00000000 |
| 20261009 | 1 | seen | +0.00357799 | +0.00000000 | -0.00037879 | +0.02379560 | +0.01467031 | +0.10000000 | +1.10000000 |
| 20261009 | 1 | held | -0.00096414 | +0.00000000 | -0.00845960 | -0.00797568 | +0.01205964 | +0.00000000 | +0.00000000 |
| 20261009 | 3 | seen | -0.00004344 | +0.00000000 | -0.03863636 | -0.04051101 | +0.00641746 | +0.00000000 | +0.10000000 |
| 20261009 | 3 | held | -0.00396414 | +0.00000000 | +0.00656566 | -0.00278970 | +0.00590420 | +0.00000000 | +0.00000000 |
| 20261009 | 5 | seen | +0.00346421 | +0.10000000 | -0.02500000 | +0.00501549 | +0.00172826 | +0.00000000 | -0.20000000 |
| 20261009 | 5 | held | -0.00147448 | +0.00000000 | +0.01679293 | +0.00275393 | +0.00873068 | +0.00000000 | +0.00000000 |
| 20261010 | 1 | seen | +0.00084298 | +0.00000000 | +0.01515152 | +0.01508947 | +0.01278518 | +0.10000000 | +0.60000000 |
| 20261010 | 1 | held | -0.00326144 | +0.00000000 | +0.00505051 | -0.01577253 | +0.00124051 | +0.00000000 | -0.20000000 |
| 20261010 | 3 | seen | -0.00061854 | +0.00000000 | +0.02803030 | +0.01371301 | +0.00229598 | +0.00000000 | +0.40000000 |
| 20261010 | 3 | held | -0.00405207 | +0.00000000 | +0.03308081 | +0.04070100 | +0.00339177 | +0.00000000 | -0.10000000 |
| 20261010 | 5 | seen | -0.00159339 | -0.10000000 | +0.04696970 | +0.03137474 | +0.01199119 | +0.00000000 | +0.60000000 |
| 20261010 | 5 | held | -0.00622061 | +0.00000000 | +0.01628788 | +0.02421316 | -0.00518188 | +0.00000000 | +0.00000000 |

## PMF median, D−A: coherent gain augmentation

| Identity | Seconds | Stations | ΔMAE | ΔMedAE | ΔM4 event MAE | ΔM4 record MAE | ΔCVaR95 | Δweighted P95 | Δmaximum |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| ensemble | 1 | seen | +0.00104106 | +0.00000000 | +0.01553030 | +0.01679284 | +0.00456698 | +0.00000000 | +1.10000000 |
| ensemble | 1 | held | -0.00296859 | +0.00000000 | +0.02411616 | +0.01255365 | +0.00401988 | +0.00000000 | +0.00000000 |
| ensemble | 3 | seen | +0.00349981 | +0.00000000 | +0.01893939 | +0.01727460 | +0.00944427 | +0.00000000 | +0.20000000 |
| ensemble | 3 | held | -0.00171630 | +0.00000000 | +0.02032828 | +0.02389127 | -0.00251242 | +0.00000000 | +0.00000000 |
| ensemble | 5 | seen | +0.00407506 | +0.00000000 | +0.01477273 | +0.02032863 | +0.00932195 | +0.00000000 | +0.30000000 |
| ensemble | 5 | held | -0.00061790 | +0.00000000 | +0.02398990 | +0.01498569 | +0.00635958 | +0.00000000 | +0.00000000 |
| 20261009 | 1 | seen | +0.00218594 | +0.00000000 | +0.01174242 | +0.00216793 | +0.00996219 | +0.10000000 | +1.50000000 |
| 20261009 | 1 | held | -0.00397356 | +0.00000000 | +0.00391414 | -0.00904864 | -0.00072232 | +0.00000000 | +0.00000000 |
| 20261009 | 3 | seen | +0.00386804 | +0.00000000 | -0.00340909 | +0.00233138 | +0.00843429 | +0.00000000 | +0.10000000 |
| 20261009 | 3 | held | -0.00097121 | +0.00000000 | +0.00694444 | +0.00904864 | +0.00777281 | +0.00000000 | +0.00000000 |
| 20261009 | 5 | seen | +0.00427517 | +0.10000000 | +0.00340909 | +0.01238816 | +0.00445631 | +0.10000000 | -0.30000000 |
| 20261009 | 5 | held | -0.00194713 | +0.00000000 | +0.02537879 | +0.00557940 | +0.00923316 | +0.00000000 | +0.00000000 |
| 20261010 | 1 | seen | +0.00171199 | +0.00000000 | +0.01628788 | +0.02703889 | +0.00704180 | +0.00000000 | +0.60000000 |
| 20261010 | 1 | held | -0.00146113 | +0.00000000 | +0.01818182 | +0.00529328 | +0.01232658 | +0.00000000 | +0.00000000 |
| 20261010 | 3 | seen | +0.00395744 | +0.00000000 | +0.01742424 | +0.01322264 | +0.00724239 | +0.00000000 | +0.60000000 |
| 20261010 | 3 | held | -0.00038864 | +0.00000000 | +0.02398990 | +0.03029328 | +0.00948440 | +0.00000000 | -0.10000000 |
| 20261010 | 5 | seen | +0.00494186 | +0.00000000 | +0.02803030 | +0.03103063 | +0.01939354 | +0.00000000 | +0.70000000 |
| 20261010 | 5 | held | +0.00064930 | +0.00000000 | +0.00176768 | +0.00232475 | +0.00276367 | +0.00000000 | +0.00000000 |

## Evidence and execution

- Report SHA-256: `0f95382b0bc202429fb76833f30def63334c75e2e7bca37b0900246bb5416389`.
- Completed grid manifest SHA-256: `db1e52814650f60e269c434f9fd9506fd38df33282c77af1e5da20562b2f121e`.
- Independent response receipt SHA-256: `6e8cc224b666b5718dfad57a100547fa798c8891374a4c711a312bc8e4d674b7`.
- Compact secondary JSON SHA-256: `d0ffb14d22c88876f7db141bc609e1df0f10503174062904f5f4c8aed0f124bb`.
- New helper SHA-256: `8068765a8605e7db31a0af7aaaeddcaf939cdef04319662641de3a95d936ee82`; dependency hash recorded in the JSON.
- Six focused synthetic tests passed with warnings treated as errors. Code-only Codex autoreview v1 returned zero findings; main auditor/scorer/producer sources were unchanged.
- Read-only extraction completed in 17.127 seconds, CPU 17.114 seconds, peak RSS 5,933,348 KiB. CUDA was hidden, CPU capped at two cores, memory at 12 GiB, external timeout 600 seconds plus 30-second kill grace, cgroup deadline 780 seconds. Service exited 0 and has no remaining process/cgroup.
- The original 34-file audit dossier was rehashed unchanged. This document and its secondary manifest are an additive handoff.
