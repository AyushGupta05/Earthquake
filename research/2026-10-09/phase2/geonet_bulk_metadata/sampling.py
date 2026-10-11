"""Deterministic CMT-frame sampling. No network, waveform or fitting code."""
import collections
import datetime as dt
import hashlib
import math
import re

SELECTION_SALT='geonet-bulk-feasibility-v1'
QUERY_SALT='geonet-bulk-feasibility-query-v1'
PARTITIONS={'train2003_2014':(2003,2014),'dev2015_2017':(2015,2017),'test2018_2024':(2018,2024)}
BANDS=('<3.5','[3.5,4)','[4,4.5)','[4.5,5)','[5,5.5)')


def digest(text):return hashlib.sha256(text.encode()).hexdigest()


def list_digest(ids):return digest('\n'.join(ids)+'\n')


def frame(groups):
    """Keep rejection denominator; no metadata-success selection/replacement."""
    strata=collections.defaultdict(list);tail=[];rejected=[];seen=set()
    for group in groups:
        eid=group['event_id']
        if eid in seen:raise ValueError('duplicate group identity')
        seen.add(eid);reasons=[]
        if group.get('eligible') is not True:reasons.append('earlier_census_ineligible')
        if not re.fullmatch(r'(?:[0-9]{5,7}|[0-9]{4}p[0-9]{6})',eid) or eid=='9999999':reasons.append('invalid_identity')
        lo,hi=group.get('mw_min'),group.get('mw_max')
        try:valid_mw=lo is not None and hi is not None and math.isfinite(lo) and math.isfinite(hi) and lo==hi
        except TypeError:valid_mw=False
        if not valid_mw:reasons.append('invalid_or_conflicting_mw')
        dates=group.get('dates',[]);year=None;partition=None
        if len(dates)!=1:reasons.append('nonunique_cmt_time')
        else:
            try:
                if not re.fullmatch(r'[0-9]{12}00',dates[0]):raise ValueError('date format')
                date=dt.datetime.strptime(dates[0],'%Y%m%d%H%M%S');year=date.year
                if not dt.datetime(2003,8,1)<=date<dt.datetime(2025,1,1):reasons.append('outside_source_window')
                partition=next((p for p,(a,b) in PARTITIONS.items() if a<=year<=b),None)
                if partition is None:reasons.append('outside_calendar_frame')
            except ValueError:reasons.append('invalid_cmt_time')
        if reasons:
            rejected.append({'event_id':eid,'reasons':sorted(set(reasons))});continue
        item={'event_id':eid,'mw':lo,'cmt_time':dates[0],'candidate_calendar_partition':partition}
        if lo>=5.5:tail.append(item);continue
        band=next(label for bound,label in zip((3.5,4,4.5,5,5.5),BANDS) if lo<bound)
        item['Mw_band']=band;strata[(partition,band)].append(item)
    return strata,tail,rejected


def select(groups,spec):
    if spec['selection_salt']!=SELECTION_SALT or spec['query_order_salt']!=QUERY_SALT:raise ValueError('sampling salt changed')
    if spec['strata_order']!=list(PARTITIONS) or spec['Mw_band_order']!=list(BANDS):raise ValueError('strata definition/order changed')
    strata,tail,rejected=frame(groups);selected=[];denominators=[]
    expected_keys=[(p,b) for p in PARTITIONS for b in BANDS]
    specified={(s['candidate_calendar_partition'],s['Mw_band']):s for s in spec['strata']}
    if len(spec['strata'])!=15 or set(specified)!=set(expected_keys):raise ValueError('strata coverage/duplicate changed')
    for p,b in expected_keys:
        candidates=strata[(p,b)];N=len(candidates);n=min(24,N);s=specified[(p,b)]
        if s['frame_N']!=N or s['sample_n']!=n:raise ValueError('frozen stratum denominator changed')
        pi=n/N if N else None;weight=N/n if n else None
        if s['inclusion_probability_n_over_N']!=pi or s['inverse_probability_N_over_n']!=weight:raise ValueError('sampling probabilities changed')
        ordered=sorted(candidates,key=lambda g:(digest(SELECTION_SALT+'|'+p+'|'+b+'|'+g['event_id']),g['event_id']))
        selected.extend([dict(g,inclusion_probability=pi,inverse_probability=weight,frame_N=N,sample_n=n) for g in ordered[:n]])
        denominators.append({'candidate_calendar_partition':p,'Mw_band':b,'frame_N':N,'sample_n':n,'not_selected_N_minus_n':N-n,'inclusion_probability':pi,'inverse_probability':weight})
    query_order=sorted(selected,key=lambda g:(digest(QUERY_SALT+'|'+g['event_id']),g['event_id']))
    if len(query_order)!=spec['new_lower_M_unique_events'] or len(tail)!=spec['reused_existing_tail_events']:raise ValueError('frozen population/sample count changed')
    if list_digest(sorted(g['event_id'] for g in selected))!=spec['selected_set_sha256'] or list_digest(g['event_id'] for g in query_order)!=spec['query_order_sha256']:raise ValueError('selected/query list digest changed')
    return query_order,sorted(tail,key=lambda g:g['event_id']),denominators,rejected
