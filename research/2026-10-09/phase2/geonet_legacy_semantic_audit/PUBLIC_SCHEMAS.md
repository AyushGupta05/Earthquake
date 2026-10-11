# Minimal independent semantic interface

`project(bytes, requested_event_id, 'qml'|'scml', profile=None)` returns a JSON-serializable dictionary. Caller misuse raises; unsupported content returns status `unknown_representation`, requested event_id, reason string, and null accepted_picks/denominators/picks/arrivals. Physical, operational timing, atomic DB, converter bug, automatic reclock, model improvement, original rewrite/clock change, new request, deployed converter/profile and full-schema claims are false in every outcome.

An `ok` result contains:

| Field | Shape |
|---|---|
| event_id / raw_event_id / mapped_event_id | requested string / literal object ID / source-derived mapped candidate |
| version / legacy_profile | QML1.2 or SCML0.10/SCML0.11 / explicit or exact native version, nullable for core QML |
| preferred_origin_id / raw_preferred_origin_id | projected stripped reference / original element text |
| origin | time_us nullable int; latitude/longitude/depth_m nullable exact Decimal strings; creation and raw_creation dictionaries |
| event_creation / raw_event_creation | seven fields agencyID, agencyURI, author, authorURI, creationTime, modificationTime, version; string or null; candidate mapping separate from raw |
| arrivals | preferred-origin ordered records: pick_id, phase, time_weight, raw_pick_id, raw_phase, reference_identity_known, native_reference_mapping_ambiguity, native_flags nullable dict, native_use_flag_states nullable dict, projected_weights dict |
| picks | dictionary mapping projected pick ID to list of event-scoped records; duplicate objects retained |
| pick record | pick_id, raw_public_id, time, raw_time, network, station, location, channel, evaluation_status, raw_evaluation_status, evaluation_mode |
| accepted_picks | accepted-ID-deduplicated list of pick records plus phase, time canonicalized UTC ISO |
| qualifying_reference_decisions | ordered {pick_id, disposition} per qualifying arrival; unresolved resolution checked before weight |
| denominators | numeric counts all_preferred_arrivals, qualifying_P_references (occurrences), unique_qualifying_P_reference_ids, unique_resolved_qualifying_P_reference_ids, accepted_P_picks, accepted_NZ_P_picks, event_scoped_pick_objects, event_scoped_amplitude_objects |
| reasons / unresolved_pick_ids | rejection occurrence counters / distinct sorted unresolved references |
| incomplete_associated_P_structure / NZ_coverage_known | booleans; positive subset knowledge does not mean full completeness |
| legacy_extensions | ordered observed field/namespace/parent/text/profile diagnostics; schema membership claim false; boolean lexical validation annotation for passedQC |
| native_reference_mapping_ambiguity | boolean preferred-arrival raw/projected correspondence ambiguity; prevents guarded comparison promotion |
| native_scope | null for QML; raw_origin_references, pick_scope_paths, station_magnitudes, amplitudes, outside_scope_pick_ids, outside_scope_origin_ids for native |

`native_scope.pick_scope_paths` retains each route `arrival` or `amplitude`, original pick/origin IDs and arrival/stationMagnitude ordinal; amplitude paths also include raw amplitude/stationMagnitude IDs. Station magnitude records retain raw ID/parent origin/originID/amplitudeID/passedQC, mapped public/origin candidates, identity_correspondence_known, origin_id_synthesized, passed_qc_projected_namespace and ordinal. Missing stationMagnitude IDs have null candidate identity and false correspondence. Amplitude records retain raw ID/pickID, has_amplitude_value_child and source_mapping_emission_count. These annotations do not claim QML conversion provenance or magnitude-model semantics.

`compare(left, right)` returns `available: false` and no recovery counters if either projection is unknown. Otherwise fields are:

| Field | Meaning |
|---|---|
| identity_match / source_profile_consistency | event/preferred identity equal / no explicit profile conflict |
| reference_mapping_consistency | no native raw-to-projected reference ambiguity; trimming never substitutes an object |
| origin_fields_complete / origin_content_match | both complete core origins / equal projected core values |
| arrival_multiset_match / arrival_multiset_lexical_match | identical primary Counter of projected pickID, phase, lexical timeWeight |
| arrival_multiset_finite_canonical_match | nullable secondary Counter comparison using finite binary-float hex weights; never promotion |
| revision_evidence | known_conflict, matching_recorded_revision or missing_or_incomplete |
| recorded_revision_guard_policy | all_present_times_aware_nonempty |
| same_record_content | guarded identity/profile/core/primary-arrival match with no known lexical revision conflict |
| newly_unique_reference_object_count | distinct qualifying-left IDs gaining a unique right object |
| newly_resolved_reference_count | distinct qualifying-left IDs accepted right and not accepted left, all networks |
| newly_accepted_NZ_reference_count | newly resolved intersect accepted-right NZ |
| content_matched_resolution_candidate_count | NZ newly accepted if same_record_content, otherwise zero |
| paired_recorded_revision_resolution_count | candidates additionally matching recorded revision evidence |

Every ok projection/comparison has conditional_source_mapping_only true. The caller must preserve all nulls and unknowns, distinguish raw counters from guarded candidates, and compare only frozen pure-function results. Unsupported namespaces, mixed legacy fields or profileless legacy extensions are retained as unknown rather than silently dropped. Parent holds source/profile/input provenance and actual-read authority; no fields here assert transport integrity, selection, clocks, physical correctness, atomic revisions, deployed converter or model improvement.
