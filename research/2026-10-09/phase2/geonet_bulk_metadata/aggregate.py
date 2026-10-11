"""Aggregate-only feasibility accounting; no IDs, URLs or pick rows in output."""
import collections
import math

ANOMALIES=('negative_depth','abs_origin_cmt_offset_ge_300s','earliest_NZ_P_before_origin',
           'earliest_NZ_P_later_than_600s','earliest_NZ_pick_outside_source_window')
MATCHES=('origin_cmt_utc_day_match','origin_cmt_utc_year_match','origin_cmt_candidate_partition_match')
UNRESOLVED=('missing_or_ambiguous_pick_reference','invalid_or_naive_pick_time','missing_station_identity')


def panel(rows):
    known=[];unknown=[];origins=[];unresolved=[]
    for row in rows:
        base=row.get('base',{})
        partial=any(base.get('reasons',{}).get(key,0)>0 for key in UNRESOLVED)
        if partial:unresolved.append(row)
        valid=base.get('status')=='ok' and isinstance(base.get('nz'),dict)
        # A valid accepted NZ subset proves >=1, but unresolved zero cannot prove
        # absence. Preserve the reviewed base counts/T0 exactly in either case.
        (known if valid and (base['nz']['stations']>0 or not partial) else unknown).append(row)
        origins.append(row.get('origin',{}))
    weight=lambda r:r.get('inverse_probability',1.0)
    total=sum(weight(r) for r in rows)
    positive=[r for r in known if r['base']['nz']['stations']>=1]
    positive_weight=sum(weight(r) for r in positive)
    unknown_weight=sum(weight(r) for r in unknown)
    return {
        'frozen_event_denominator':len(rows),'frame_weight_sum':total,
        'outcome_status':dict(sorted(collections.Counter(r['outcome_status'] for r in rows).items())),
        'known_NZ_P_coverage_events':len(known),'known_zero_NZ_P_events':len(known)-len(positive),
        'unknown_NZ_P_coverage_events':len(unknown),'events_with_at_least_one_NZ_P':len(positive),
        'incomplete_associated_P_structure_events':len(unresolved),
        'positive_NZ_P_with_incomplete_structure_events':sum(r in unresolved for r in positive),
        'zero_accepted_NZ_P_with_incomplete_structure_events':sum(r.get('base',{}).get('nz',{}).get('stations')==0 for r in unresolved),
        'unresolved_P_reason_counts':{key:sum(r.get('base',{}).get('reasons',{}).get(key,0) for r in rows) for key in UNRESOLVED},
        'weighted_positive_NZ_P_total':positive_weight,'weighted_unknown_NZ_P_total':unknown_weight,
        'weighted_positive_fraction_lower_bound':positive_weight/total if total else None,
        'weighted_positive_fraction_upper_bound':(positive_weight+unknown_weight)/total if total else None,
        'positive_NZ_P_and_valid_origin_time_in_window_events':sum(r.get('origin',{}).get('valid_origin_time_in_window') is True for r in positive),
        'positive_NZ_P_and_complete_finite_time_geometry_events':sum(r.get('origin',{}).get('valid_timezone_aware_origin_time') is True and r.get('origin',{}).get('geometry_complete') is True for r in positive),
        'positive_NZ_P_and_CMT_day_year_partition_agreement_events':sum(all(r.get('origin',{}).get(k) is True for k in MATCHES) for r in positive),
        'unique_preferred_origin_linkage_events':sum(o.get('unique_preferred_origin_linkage') is True for o in origins),
        'valid_timezone_aware_origin_time_events':sum(o.get('valid_timezone_aware_origin_time') is True for o in origins),
        'valid_origin_time_in_window_events':sum(o.get('valid_origin_time_in_window') is True for o in origins),
        'complete_finite_time_geometry_events':sum(o.get('valid_timezone_aware_origin_time') is True and o.get('geometry_complete') is True for o in origins),
        'origin_field_reasons':dict(sorted(collections.Counter(reason for o in origins for reason in o.get('reasons',[])).items())),
        'origin_anomaly_counts':{key:{'flagged':sum(o.get(key) is True for o in origins),'unknown':sum(o.get(key) is None for o in origins)} for key in ANOMALIES},
        'origin_CMT_match_counts':{key:{'match':sum(o.get(key) is True for o in origins),'disagree':sum(o.get(key) is False for o in origins),'unknown':sum(o.get(key) is None for o in origins)} for key in MATCHES},
        'strict_horizon_NZ_station_histograms':{str(t):dict(sorted(collections.Counter(str(r['base']['nz']['before_seconds'][str(t)]) for r in known).items())) for t in (1,3,5)},
        'station_histogram_interpretation':'Counts over accepted valid associated picks and their preserved T0; positive unresolved subsets are lower-bound evidence, not complete underlying P coverage.',
        'weighted_strict_horizon_NZ_station_histograms':{str(t):{str(k):sum(weight(r) for r in known if r['base']['nz']['before_seconds'][str(t)]==k) for k in sorted({r['base']['nz']['before_seconds'][str(t)] for r in known})} for t in (1,3,5)},
    }


def summarize(rows,denominators,spec,completed):
    lower=[r for r in rows if r['source']=='new_lower_M'];tail=[r for r in rows if r['source']=='reused_tail']
    strata=[]
    for d in denominators:
        selected=[r for r in lower if r['candidate_calendar_partition']==d['candidate_calendar_partition'] and r['Mw_band']==d['Mw_band']]
        if len(selected)!=d['sample_n']:raise ValueError('lost frozen stratum denominator')
        table=panel(selected);threshold=math.ceil(d['sample_n']/2)
        strata.append(dict(d,coverage=table,positive_NZ_P_gate_threshold=threshold,positive_NZ_P_gate_pass=table['events_with_at_least_one_NZ_P']>=threshold))
    if len(lower)!=spec['new_lower_M_unique_events'] or len(tail)!=spec['reused_existing_tail_events']:raise ValueError('lost frozen population denominator')
    p=panel(lower);g=spec['missingness_gate']
    passed=(completed and p['valid_origin_time_in_window_events']>=g['minimum_successfully_resolved_preferred_origin_events']
            and p['events_with_at_least_one_NZ_P']>=g['minimum_events_with_at_least_one_accepted_NZ_associated_P_pick']
            and all(s['positive_NZ_P_gate_pass'] for s in strata))
    tail_panels=[]
    for partition in spec.get('strata_order',('train2003_2014','dev2015_2017','test2018_2024')):
        for band,lo,hi in (('[5.5,6)',5.5,6),('[6,7)',6,7),('>=7',7,math.inf)):
            subset=[r for r in tail if r['candidate_calendar_partition']==partition and lo<=r['mw']<hi]
            tail_panels.append({'candidate_calendar_partition':partition,'Mw_band':band,'coverage':panel(subset)})
    return {'version':'geonet-bulk-metadata-v1','completed':completed,'combined_frozen_denominator':len(rows),
            'new_lower_M':p,'reused_tail':panel(tail),'strata':strata,'metadata_missingness_gate_pass':bool(passed),
            'reused_tail_band_calendar_panels':tail_panels,
            'claim_limits':{'retrospective_associated_pick_metadata_only':True,'operational_picker_replay':False,
                            'waveform_response_availability_verified':False,'independent_sequence_split_verified':False,
                            'origin_diagnostics_are_inference_inputs':False,'benchmark_or_method_superiority_verified':False},
            'weight_limit':'Fixed hash exchangeability design only; N/n does not correct availability-dependent missingness or CMT selection.'}
