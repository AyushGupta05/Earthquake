# Proposed six-event SCML representation check

This is a **proposal, with zero event requests authorized or made by this artifact**. It creates no private roster or executable collector and changes no existing census, counts96, parser, clock, acquisition or benchmark rule. Parent approval, a separately frozen private plan, reviewed implementation and launch receipt would precede any request.

The question is narrow: does the source-backed original-SCML route expose a uniquely linked pick absent/ambiguous in QuakeML for the same event and preferred-origin record? It is not an operational clock reconstruction or permission to enlarge the EEW dataset.

## Exact candidate requests and limits

Published [GeoNet routes.go](https://github.com/GeoNet/fdsn/blob/3040322c7bf0818c9b42a6666284b86f674cb706/cmd/fdsn-ws/routes.go) registers /sc3ml alongside the FDSN routes. [sc3ml.go](https://github.com/GeoNet/fdsn/blob/3040322c7bf0818c9b42a6666284b86f674cb706/cmd/fdsn-ws/sc3ml.go) selects the stored original SCML by eventid. [GeoNet's FDSN documentation](https://www.geonet.org.nz/data/access/FDSN) provides the service host. Combining these gives the following exact candidate HTTPS requests; **public proxy exposure and live schema remain unverified**. The pinned server README does not advertise that alternate route.

    GET https://service.geonet.org.nz/fdsnws/event/1/query?eventid=FROZEN_ID
    GET https://service.geonet.org.nz/sc3ml?eventid=FROZEN_ID

For each of six fixed events, obtain one fresh QuakeML and one SCML response, in that order, and retain the original pinned QuakeML as a third, read-only reference. Fresh pairs avoid treating a newer SCML revision as a pure representation change from the older cached QML. Sequential requests are not atomic; missing/conflicting revision information remains an explicit comparison limitation. No inclusion flags, qsearch invocation, alternate host, GET retry, redirect, replacement, family search or adaptive follow-up is allowed.

Proposed caps are 12 total attempts, 4 MiB per body, 48 MiB total newly returned bytes, 20 seconds per whole request,>=1 second start spacing and 360 seconds absolute launch time with 10 seconds for finalization. Persist attempt/chunk accounting before connections and retain failed, partial and unattempted records. A body, resource or deadline cap stops the phase incomplete. No waveforms, StationXML, AWS, models or fitting are involved. HTTP/parse failure is an unknown comparison, not zero picks or a reason to pick another event.

## Fixed six-event roster rule

Use only the immutable original 149 tail metadata and completed 495 independent bindings. Include all four candidateTEST Mw>=6 events with flagged incomplete associated-P structure: three [6,7), one >=7. Take one complete control from each of those two bands among candidateTEST, with no unresolved-reference/time/station flag. Rank controls by SHA256 of UTF-8 geonet-scml-paired-control-v1|test2018_2024|BAND|EVENT_ID, then lexical ID; take the first per band. Freeze the six-event request order by SHA256 of geonet-scml-paired-query-v1|EVENT_ID, then ID. Publish only 4/2 and band counts; identities/URLs/roster/body bytes stay private.

Eligibility/status, completeness, original magnitude and calendar labels are declared selection inputs for this diagnostic. New format contents, recovery outcomes, waveform success, geometry or any model result cannot select controls. If the fixed input pins or expected 4+2 allocation fail, preparation fails without replacement. This proposal intentionally specifies the rule before new representations, without reading or creating an actual six-ID roster here.

## Cross-format comparison contract

Pin raw original QML, fresh QML and fresh SCML plus receipts. Require one matching event and one uniquely linked preferred origin. Compare identities, preferred-origin time/location/depth and creation/revision metadata, then arrival multisets including phase, pick reference and weight/use fields. Keep counts for every source representation before acceptance. Multiple/missing objects, unsupported namespaces or mapping collisions remain unknown/ambiguous.

For audited SCML 0.13/0.14, map an ID unchanged if it starts smi: or quakeml:; otherwise prepend smi:nz.org.geonet/ after replacing each space/colon with underscore. Retain raw IDs and reject collisions; never use suffix-only matching. Other schema versions require a prior source-only mapping audit or remain unsupported. Do not execute author XSLTs.

Apply the frozen QML phase, weight, rejection and timestamp/station predicate to a source-derived SCML projection; report native weight/use flags separately. SCML 0.14 emits timeWeight from weight/use rules, so filtering by native weight alone would change the old predicate. Preserve absent versus zero rather than silently treating them as equivalent. Freeze invented parser/linkage fixtures and code-only review before acquisition implementation.

Report original-to-fresh-QML catalogue drift separately from fresh-QML-to-SCML representation differences. A recovery count requires unchanged mapped event/preferred-origin identity, matching original associations and a newly unique pick with valid time/station. If substantive preferred-origin/arrival data differ, report revision or association drift; do not call it representation-only recovery. A transform-only ID change can match solely through the pinned mapping above.

For each representation, report all referenced/unique/resolved/ambiguous/rejected/accepted NZ P denominators, earliest accepted time and strict 1/3/5 second station counts. Show changes at both the preserved old T0 and each representation's recalculated T0, so adding an earlier pick cannot masquerade as a monotonic improvement. These are diagnostic alternatives only: no automatic re-clock, overwrite of old receipts or revision of counts96. Negative results remain useful. Even complete references do not establish actual telemetry, operational picker timing, waveform availability or a better magnitude model.
