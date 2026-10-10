# GeoNet small availability audit: independently verified result

The bounded local audit completed with15of18frozen station targets providing coherent three-component samples, epoch-spanning transfer-response metadata and a passing clipping screen at each strict global1/3/5second window. When also requiring the station's retrospective annotated P pick before that deadline, the counts are9/18,11/18and13/18. Every failure remains in the denominator. This is a six-event historical availability check, not a calibrated EEW benchmark or new magnitude model.

| Global time after earliest NZ-associated P | Frozen targets | Audited | Strict3C availability and screen | Annotated P before deadline, all targets | Available+annotated P+screen |
|---|---:|---:|---:|---:|---:|
|1second|18|16|15|10|9|
|3seconds|18|16|15|13|11|
|5seconds|18|16|15|15|13|

The deterministic stress sample has two events/six stations in each nonoverlapping band. Its oldest/latest selected years are2003/2024for[5.5,6),2003/2023for[6,7),and2003/2023forMw≥7. No target was replaced after reading responses or samples.

| Band | Frozen stations | Strict3C+screen at each horizon | Available+annotated P+screen at1/3/5s |
|---|---:|---:|---|
|[5.5,6)|6|4|2/4/4|
|[6,7)|6|5|3/3/4|
|Mw≥7|6|6|4/4/5|

Two[5.5,6)targets received HTTP204/no data for response-level StationXML; their paired waveform requests were unattempted. This demonstrates missing response metadata for the frozen query, not proof that no waveform exists. One[6,7)target decoded successfully but had no matched prefix samples at1second (all three components), then failed required left-edge/prebuffer coverage at3and5seconds (all three components). It was retained rather than filled or shifted. The other45component records per horizon passed native finite/rate/strict-edge/interior-gap/sample-lattice checks. There were no observed gaps, overlaps, nonfinite samples, rate/grid failures or clipping candidates among these retained component checks. Missing samples/unaudited metadata remain separate failure categories.

The run used34of36planned queries (two paired waveforms skipped),1,167,804response-body bytes and67.850691seconds reported worker elapsed. Minimum request spacing was1.142551seconds and the longest request3.198363seconds. Parent confirmed exit0 and completed manifest, with the frozen1800second outer validation/loading watchdog; exact successful parent startup duration was not separately persisted. No retry, redirect, replacement, cap extension, training or AWS resource was used. An earlier wrong-directory parent startup failed before requests and is retained locally. Both successful and empty response attempts are accounted for. The native worker log is empty and saved response warnings are zero.

Independent analysis imported no audit/core helpers and made no additional request. It verified all5census input hashes, actual committed source/protocol/receipt/dependency bindings,36manifest member hashes/sizes,34response-attempt files and exact query order/body totals. It reconstructed48audited station/deadline outcomes,144component records and144response evidence records directly from raw local StationXML/miniSEED. All matched. At each of the48audited windows it replaced actual future samples with NaN and confirmed prefix evidence stayed unchanged. All54station/deadline slots, including six unaudited slots from the two failed metadata targets, remain represented.

Source freeze commit:0c377649b06feb81824169d98b4b51291d6db72e. Plan SHA256:`1adcce537f0b9bcff0fc69d74aab530c541c594252e620c020ce33dedff6c205`. Worker manifest SHA256:`6401841db190b617431f3c7d4f330cfd1e01c0177f242e8f2d558c6e89297aa3`. Machine-readable aggregates and replay receipts are in summary.json and independent_replay.json; raw rows/IDs/query URLs/StationXML/miniSEED stay ignored locally.

A finite transfer response and valid epoch/units are metadata consistency, not independently verified physical calibration. A clean clipping screen does not establish physical absence of clipping. The clocks and P picks are retrospective; no operational picker, packet receipt, latency or detection accuracy was replayed. Six earliest/latest-year events cannot estimate149-event coverage, independent sequence counts, magnitude-error improvement, method novelty or superiority over published research. This result supports only a future explicitly frozen acquisition/calibration plan; it does not authorize enlargement or fitting.
