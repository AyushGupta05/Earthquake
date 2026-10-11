"""Native-count evidence; transfer metadata is a separate, optional panel."""
import collections
import math

def records(inventory,adapter):
    result=adapter.inventory_records(inventory)
    # Geometry is retained only on selected concurrent epochs, never used to
    # select stations/families or to substitute CMT event coordinates.
    for row,ch in zip(result,(c for n in inventory for s in n for c in s)):
        def numeric(v):
            try:return float(v)
            except (ValueError,TypeError):return float('nan')
        row['latitude']=numeric(ch.latitude);row['longitude']=numeric(ch.longitude);row['elevation_m']=numeric(ch.elevation)
    return result

def analyze(inventory,stream,event,target,core,adapter,cached_response=None,budget_exception=None):
    # The pinned response adapter already accepts exception tuples. Include
    # allocation failures so it cannot wrap resource exhaustion as bad response.
    interrupted=(MemoryError,)+(budget_exception if isinstance(budget_exception,tuple) else (budget_exception,) if budget_exception is not None else ())
    rows=records(inventory,adapter);answer={}
    cached=records(cached_response,adapter) if cached_response is not None else None
    for h in (1,3,5):
        if target['station'] not in event['current_station_masks'][str(h)]:
            answer[str(h)]={'status':'not_in_current_arrival_subset','count_valid':False};continue
        left=event['t0_ns']-5*core.NS;deadline=event['t0_ns']+h*core.NS
        result={'status':'unresolved','count_valid':False,'clipping_screen_passed':False,'full_transfer_response_available':False,'full_response_evidence_source':'frozen_completed_cache' if cached is not None else 'none','physically_calibrated_prefix_verified':False,'operational_picker_replayed':False}
        try:
            channels=core.triplet(rows,target,left,deadline)
            # Do not inspect a wholly future trace's sample rate or metadata.
            prefix_stream=[tr for tr in stream if tr.stats.starttime.ns<deadline]
            components={c['code']:core.component(adapter.stream_pieces(prefix_stream,target,c['code']),left,deadline,c['sample_rate']) for c in channels}
            aligned=core.compatible_lattices(components,channels[0]['sample_rate'])
            result.update(status='audited',count_valid=aligned,components=components,clipping_screen_passed=all(c.get('clipping_screen_passed',False) for c in components.values()),
                sensor_codes=[c['code'] for c in channels],channel_geometry={c['code']:{'latitude':c['latitude'] if math.isfinite(c['latitude']) and -90<=c['latitude']<=90 else None,
                    'longitude':c['longitude'] if math.isfinite(c['longitude']) and -180<=c['longitude']<=180 else None,'elevation_m':c['elevation_m'] if math.isfinite(c['elevation_m']) else None} for c in channels})
            evidence={}
            if cached is not None:
                try:
                    stronger=core.triplet(cached,target,left,deadline)
                    keys=('network','station','location','code','start_ns','end_ns','sample_rate','dip','azimuth')
                    if [{k:c[k] for k in keys} for c in stronger]!=[{k:c[k] for k in keys} for c in channels]:raise ValueError('cached response epoch/rate/orientation differs from channel metadata')
                    for c in stronger:
                        try:evidence[c['code']]=adapter.response_evidence(c,interrupted)
                        except adapter.ResponseEvidenceError as exc:evidence[c['code']]=exc.evidence
                    result['full_transfer_response_available']=all(e.get('full_transfer_response_available') is True for e in evidence.values())
                except Exception as exc:
                    if isinstance(exc,interrupted):raise
                    result['response_panel_error']=type(exc).__name__+': '+str(exc)[:200]
            result['response_evidence']=evidence
        except Exception as exc:
            if isinstance(exc,interrupted):raise
            result['reason']=type(exc).__name__+': '+str(exc)[:200]
        answer[str(h)]=result
    return answer

def initial_targets(events):
    return [{'slot':e['event_id']+'|'+t['station'],'event_id':e['event_id'],'station':t['station'],'status':'unattempted' if t['queryable'] else 'unqueryable',
             'horizons':{str(h):{'status':('unattempted' if t['queryable'] else 'unqueryable') if t['station'] in e['current_station_masks'][str(h)] else 'not_in_current_arrival_subset','count_valid':False} for h in (1,3,5)}} for e in events for t in e['targets']]

def event_outcomes(events,targets):
    lookup={r['slot']:r for r in targets};rows=[]
    for e in events:
        hresults={}
        for h in (1,3,5):
            # This view is intentionally built from the current mask only. The
            # private acquisition union and source labels never enter it.
            current=[]
            for t in e['targets']:
                if t['station'] not in e['current_station_masks'][str(h)]:continue
                r=lookup[e['event_id']+'|'+t['station']];v=r['horizons'][str(h)]
                current.append({'network':t['network'],'station':t['station'],'location':t['location'],'prefix':t['prefix'],'pick_ns':t['pick_ns'],'engineering':v})
            hresults[str(h)]={'count_available':any(v['engineering'].get('count_valid') is True for v in current),
                             'clean_screen_available':any(v['engineering'].get('count_valid') is True and v['engineering'].get('clipping_screen_passed') is True for v in current),
                             'full_response_consistent_count_available':any(v['engineering'].get('count_valid') is True and v['engineering'].get('full_transfer_response_available') is True for v in current),'current_view':current}
        rows.append({'event_id':e['event_id'],'Mw_band':e['Mw_band'],'candidate_calendar_partition':e['candidate_calendar_partition'],
                     'P_status':e['P_status'],'incomplete_associated_P_structure':e['incomplete_associated_P_structure'],'horizons':hresults,
                     'common_count_available':all(v['count_available'] for v in hresults.values()),'common_clean_screen_available':all(v['clean_screen_available'] for v in hresults.values())})
    return rows

def summary(events,targets,completed):
    rows=event_outcomes(events,targets)
    def panel(rs):return {'event_denominator':len(rs),'common_count_available':sum(r['common_count_available'] for r in rs),
        'common_clean_screen_available':sum(r['common_clean_screen_available'] for r in rs),'horizons':{str(h):{k:sum(r['horizons'][str(h)][k] for r in rs) for k in ('count_available','clean_screen_available','full_response_consistent_count_available')} for h in (1,3,5)}}
    return {'version':'geonet-counts-screen-v1','completed':completed,'scientific_interpretation_allowed':completed,'events':panel(rows),'target_denominator':len(targets),
        'target_status':dict(sorted(collections.Counter(r['status'] for r in targets).items())),
        'P_event_status':dict(sorted(collections.Counter(r['P_status'] for r in rows).items())),
        'cached_response_status':dict(sorted(collections.Counter(r.get('cached_response_status','not_evaluated') for r in targets).items())),
        'channel_retrieval_status':dict(sorted(collections.Counter(r.get('channel_retrieval_status','unattempted') for r in targets).items())),
        'waveform_source':dict(sorted(collections.Counter(r.get('waveform_source','unattempted') for r in targets).items())),
        'waveform_retrieval_status':dict(sorted(collections.Counter(r.get('waveform_retrieval_status','unattempted') for r in targets).items())),
        'target_horizon_clipping_candidates':{str(h):sum(any(c.get('clipping_candidate') is True for c in r['horizons'][str(h)].get('components',{}).values()) for r in targets) for h in (1,3,5)},
        'target_horizon_status':{str(h):dict(sorted(collections.Counter(r['horizons'][str(h)]['status'] for r in targets).items())) for h in (1,3,5)},
        'target_horizon_reasons':{str(h):dict(sorted(collections.Counter(r['horizons'][str(h)].get('reason','no_reason') for r in targets).items())) for h in (1,3,5)},
        'band_calendar':[dict(Mw_band=b,candidate_calendar_partition=p,**panel([r for r in rows if (r['Mw_band'],r['candidate_calendar_partition'])==(b,p)])) for p in ('train2003_2014','dev2015_2017','test2018_2024') for b in ('<3.5','[3.5,4)','[4,4.5)','[4.5,5)','[5,5.5)','[5.5,6)','[6,7)','>=7')],
        'claim_limits':{'native_counts_engineering_only':True,'calibrated_physics':False,'physically_unclipped':False,'operational_picker':False,'sequence_independence':False,'model_accuracy_or_novelty':False}}
