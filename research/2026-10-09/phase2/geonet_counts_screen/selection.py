"""Fixed source selection, current-arrival views and pre-channel query geometry."""
import collections
import hashlib
import re
import urllib.parse

PARTITIONS=('train2003_2014','dev2015_2017','test2018_2024')
BANDS=('<3.5','[3.5,4)','[4,4.5)','[4.5,5)','[5,5.5)')
UNRESOLVED=('missing_or_ambiguous_pick_reference','invalid_or_naive_pick_time','missing_station_identity')

def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def list_hash(ids):return digest('\n'.join(ids)+'\n')
def rank(row,band):return (digest('geonet-counts-screen-v1|'+row['candidate_calendar_partition']+'|'+band+'|'+row['event_id']),row['event_id'])

def choose(source_rows,outcomes,core,spec):
    if len({r['event_id'] for r in source_rows})!=len(source_rows):raise ValueError('duplicate source identity')
    lower=[r for r in source_rows if r['source']=='new_lower_M'];tail=[r for r in source_rows if r['source']=='reused_tail']
    if (len(lower),len(tail))!=(346,149):raise ValueError('frozen bulk denominator changed')
    if list_hash(sorted(r['event_id'] for r in lower))!='6ed849d32a6ab180b7ddb4ddbf85d085d6819011fcebe7c093384c0806452d7c':raise ValueError('frozen bulk selected-set changed')
    selected=[r for r in tail if r['mw']>=6]
    if len(selected)!=60:raise ValueError('60-event tail allocation changed')
    for p in PARTITIONS:
        for band in BANDS:
            cell=[r for r in lower if (r['candidate_calendar_partition'],r['Mw_band'])==(p,band)]
            if len(cell)<2:raise ValueError('insufficient frozen lower cell')
            selected+=sorted(cell,key=lambda r:rank(r,band))[:2]
        cell=[r for r in tail if r['candidate_calendar_partition']==p and 5.5<=r['mw']<6]
        if len(cell)<2:raise ValueError('insufficient frozen tail cell')
        selected+=sorted(cell,key=lambda r:rank(r,'[5.5,6)'))[:2]
    if len(selected)!=spec['events'] or len({r['event_id'] for r in selected})!=96:raise ValueError('96-event allocation changed')
    selected.sort(key=lambda r:(digest('geonet-counts-query-v1|'+r['event_id']),r['event_id']))
    events=[]
    for row in selected:
        eid=row['event_id'];base=outcomes[eid].get('base',{});stations=collections.defaultdict(list)
        if base.get('status')=='ok':
            for pick in base.get('accepted_picks',[]):
                if pick['network']=='NZ':stations[pick['station']].append(pick)
        earliest=[min(ps,key=lambda p:(core.stamp_ns(p['time']),p['location'],p['channel'],p['pick_id'])) for ps in stations.values()]
        earliest.sort(key=lambda p:(core.stamp_ns(p['time']),p['station']))
        t0=core.stamp_ns(earliest[0]['time']) if earliest else None
        if t0 is not None and core.iso(t0)!=core.iso(core.stamp_ns(base['nz']['t0_utc'])):raise ValueError('accepted subset T0 changed')
        masks={str(t):[p['station'] for p in earliest if core.stamp_ns(p['time'])<t0+t*core.NS][:8] if t0 is not None else [] for t in (1,3,5)}
        targets=[]
        for p in earliest:
            if p['station'] not in masks['5']:continue
            queryable=bool(re.fullmatch('[A-Z0-9]{1,8}',p['station']) and re.fullmatch('[A-Z0-9]{0,2}',p['location']) and re.fullmatch('[A-Z0-9]{3}',p['channel']))
            targets.append({'network':'NZ','station':p['station'],'location':p['location'],'prefix':p['channel'][:2],'pick_ns':core.stamp_ns(p['time']),
                            'queryable':queryable,'unqueryable_reason':None if queryable else 'invalid_seed_identity'})
        partial=any(base.get('reasons',{}).get(k,0)>0 for k in UNRESOLVED)
        events.append({'event_id':eid,'candidate_calendar_partition':row['candidate_calendar_partition'],'Mw_band':row.get('Mw_band','[5.5,6)' if row['mw']<6 else '[6,7)' if row['mw']<7 else '>=7'),
                       'mw':row['mw'],'t0_ns':t0,'P_status':base.get('status','unknown'),'incomplete_associated_P_structure':partial,'current_station_masks':masks,'targets':targets})
    return events

def envelope(event,target,core):
    return {'network':target['network'],'station':target['station'],'location':target['location'] or '--','channel':target['prefix']+'?',
            'starttime':core.iso(event['t0_ns']-5*core.NS),'endtime':core.iso(event['t0_ns']+5*core.NS)}

def queries(events,core,cache):
    metadata=[];batches=[]
    for event in events:
        for t in event['targets']:
            if not t['queryable']:continue
            e=envelope(event,t,core);key=(event['event_id'],t['station']);slot=event['event_id']+'|'+t['station']
            metadata.append({'kind':'channel','method':'GET','slot':slot,'file':f'channel_{len(metadata):03d}.xml','envelope':e,
                'url':'https://service.geonet.org.nz/fdsnws/station/1/query?'+urllib.parse.urlencode(e|{'level':'channel','format':'xml'})})
    for block in range(0,len(events),16):
        lines=[];slots=[]
        for event in events[block:block+16]:
            for t in event['targets']:
                slot=event['event_id']+'|'+t['station']
                if not t['queryable'] or cache.get(slot,{}).get('waveform'):continue
                e=envelope(event,t,core);lines.append(' '.join(e[k] for k in ('network','station','location','channel','starttime','endtime')));slots.append(slot)
        body='\n'.join(lines)+'\n' if lines else ''
        batches.append({'kind':'waveform','method':'POST','file':f'waveform_{len(batches):02d}.mseed','url':'https://service.geonet.org.nz/fdsnws/dataselect/1/query',
                        'post_body':body,'post_body_sha256':digest(body),'slots':slots,'source_event_count':len(events[block:block+16])})
    if len(metadata)>768 or len(batches)>6:raise ValueError('frozen query count exceeded')
    return metadata,batches
