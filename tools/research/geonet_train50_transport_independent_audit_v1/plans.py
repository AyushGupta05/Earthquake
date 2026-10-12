"""Independent canonical fixed50 GET/POST plan validators; no producer imports."""
from datetime import datetime,timedelta,timezone
import re
from urllib.parse import urlencode
from strict_inputs import decode,digest,fields,integer,need,same,sha,text

ROOT_SHA='36aafbb99d01c269593aae3e86725cccb6e01de88edd9ff5e7fad38f610363f4'
MIN_NS=-(1<<63);MAX_NS=(1<<63)-1
GET_PROTOCOL='geonet-train50-selected-epoch-GET-v1'
POST_PROTOCOL='geonet-train50-prefix-POST-transport-v1'
GET_STUDY='geonet-fixed50-TRAIN-prefix3-metadata-GET-v1'
POST_STUDY='geonet-fixed-TRAIN50-prefix3-native-POST-v1'
GET_ENDPOINT='https://service.geonet.org.nz/fdsnws/station/1/query'
GET_LIMITS=dict(connection_s=10.,first_body_s=20.,request_s=20.,start_spacing_s=1.,processing_s=1260.,whole_s=1500.,term_s=5.,kill_s=5.,body_bytes=4194304,total_retained_bytes=209715200,probe_bytes=1,total_consumption_upper=209715250,request_bytes=16384,header_diagnostic_bytes=131072)
POST_LIMITS=dict(connection_s=10.,first_body_s=60.,request_s=120.,start_spacing_s=1.,processing_s=2160.,whole_s=2400.,term_s=5.,kill_s=5.,body_bytes=8388608,total_retained_bytes=109051904,probe_bytes=1,total_consumption_upper=109051917,request_bytes=16384,header_diagnostic_bytes=131072)
GET_CLAIMS=dict.fromkeys(('metadata_rows_qualified','full_response_verified','physical_axes_verified','calibration_verified','operational_availability_verified','sequence_independence_verified','model_input_verified','magnitude_improvement_verified','novelty_verified','published_benchmark_superiority_verified'),False)
POST_CLAIMS=dict.fromkeys(('waveform_rows_qualified','scientific_coverage_verified','metadata_http204_repaired','full_response_verified','physical_axes_verified','calibration_verified','operational_availability_verified','sequence_independence_verified','model_input_verified','magnitude_improvement_verified','novelty_verified','published_benchmark_superiority_verified'),False)
PREREQS=('original_projection_sha256','frozen_roster_sha256','first_queryable_selection_proof_sha256','no_exact_complete_success_cache_proof_sha256')


def utc_ns(ns):
    integer(ns,'utc_ns',MIN_NS,MAX_NS);seconds,nanos=divmod(ns,10**9)
    t=datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(seconds=seconds)
    return t.strftime('%Y-%m-%dT%H:%M:%S')+f'.{nanos:09d}Z'


def ascii_text(v,pattern,label):
    need(type(v) is str and re.fullmatch(pattern,v) is not None,label);return v


def get_url(row):
    t=row['selected_target']
    if t is None:return None
    pairs=[('network',t['network']),('station',t['station']),('location',t['location'] or '--'),('channel',t['prefix']+'?'),('starttime',utc_ns(row['t0_ns']-3*10**9)),('endtime',utc_ns(row['t0_ns']+5*10**9)),('level','channel'),('format','xml')]
    return GET_ENDPOINT+'?'+urlencode(pairs)


def post_entity(rows):
    if not rows:return None
    lines=['format=miniseed']
    for r in rows:lines.append(' '.join((r['network'],r['station'],r['location'] or '--',r['prefix']+'?',utc_ns(r['t0_ns']-3*10**9),utc_ns(r['t0_ns']+5*10**9))))
    return ('\n'.join(lines)+'\n').encode('ascii')


def validate(raw,profile):
    need(profile in ('GET','POST'),'fixed_profile');p=decode(raw,131072,'plan')
    get=profile=='GET';protocol=GET_PROTOCOL if get else POST_PROTOCOL;study=GET_STUDY if get else POST_STUDY;key='selections' if get else 'batches'
    fields(p,('protocol','study_id','proposal_sha256','rows',key,'prerequisites'),'plan_fields')
    text(p['protocol'],protocol,'plan_protocol');text(p['study_id'],study,'plan_study');text(p['proposal_sha256'],ROOT_SHA,'plan_root')
    prereqs=PREREQS if get else PREREQS+('metadata_custody_sha256',)
    fields(p['prerequisites'],prereqs,'prereqs')
    for v in p['prerequisites'].values():sha(v,'prereq_sha')
    rows=p['rows'];need(type(rows) is list and len(rows)==50,'rows50');events=set();indices=set();family={'ENZ':0,'12Z':0};no_target=0
    for i,r in enumerate(rows):
        if get:fields(r,('row_index','global_index','event_id','partition','t0_ns','selected_target','selection_reason'),'GET_row_fields')
        else:fields(r,('row_index','global_ordinal','original_event_index','original_target_index','event_id','partition','network','station','location','prefix','t0_ns','pick_ns','metadata_status','nominal_family'),'POST_row_fields')
        need(integer(r['row_index'],'row_index',0,49)==i,'row_order')
        globalkey='global_index' if get else 'global_ordinal';need(integer(r[globalkey],'global_slot',65,114)==65+i,'global_slot_order')
        e=ascii_text(r['event_id'],r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}','event_id');need(e not in events,'event_unique');events.add(e);text(r['partition'],'TRAIN','TRAIN_only')
        if r['t0_ns'] is not None:integer(r['t0_ns'],'T0',MIN_NS+3*10**9,MAX_NS-5*10**9)
        if get:
            target=r['selected_target']
            if target is None:
                ascii_text(r['selection_reason'],r'[\x20-\x7e]{1,128}','null_target_reason');no_target+=1;continue
            fields(target,('network','station','location','prefix','pick_ns','original_target_index'),'selected_target')
            need(r['selection_reason'] is None,'target_reason_null');text(target['network'],'NZ','network_NZ');integer(target['original_target_index'],'original_target_index',0,7)
        else:
            oi=integer(r['original_event_index'],'original_event_index',0,494);need(oi not in indices,'original_index_unique');indices.add(oi)
            if r['original_target_index'] is None:
                need(all(r[k] is None for k in ('network','station','location','prefix','pick_ns','nominal_family')),'no_target_nulls');text(r['metadata_status'],'no_target','no_target_metadata');no_target+=1;continue
            integer(r['original_target_index'],'original_target_index',0,1000000);target=r
            if r['metadata_status']=='known':
                ascii_text(r['nominal_family'],r'ENZ|12Z','known_family');family[r['nominal_family']]+=1
            else:text(r['metadata_status'],'unknown','metadata_unknown');need(r['nominal_family'] is None,'unknown_family_null')
            ascii_text(target['network'],r'[A-Z0-9]{1,8}','network')
        need(r['t0_ns'] is not None,'queryable_T0');ascii_text(target['station'],r'[A-Z0-9]{1,8}','station');ascii_text(target['location'],r'[A-Z0-9]{0,2}','location');ascii_text(target['prefix'],r'[A-Z0-9]{2}','prefix');pick=integer(target['pick_ns'],'pick_ns',MIN_NS,MAX_NS)
        if get:need(pick<r['t0_ns']+5*10**9,'pick_before5')
    count=50 if get else 13;entries=p[key];need(type(entries) is list and len(entries)==count,'logical_count');requests=[];query_indices=[]
    for i,b in enumerate(entries):
        if get:
            fields(b,('selection_index','row_indices','request_url','request_sha256'),'GET_selection_fields');need(integer(b['selection_index'],'selection_index',0,49)==i,'selection_order');need(same(b['row_indices'],[i]),'selection_membership');url=get_url(rows[i]);need(same(b['request_url'],url),'canonical_GET_URL');rawreq=b'' if url is None else (url+'\n').encode('ascii');sha(b['request_sha256'],'request_SHA');need(digest(rawreq)==b['request_sha256'],'GET_request_pin');query=bool(url)
        else:
            fields(b,('batch_index','row_indices','requested_row_indices','request_body','request_sha256'),'POST_batch_fields');need(integer(b['batch_index'],'batch_index',0,12)==i,'batch_order');ids=list(range(i*4,min(i*4+4,50)));need(same(b['row_indices'],ids),'batch_membership');requested=[j for j in ids if rows[j]['original_target_index'] is not None];need(same(b['requested_row_indices'],requested),'requested_exact_subset');rawreq=post_entity([rows[j] for j in requested]);need(same(b['request_body'],None if rawreq is None else rawreq.decode('ascii')),'POST_canonical_entity');query=bool(requested)
            if query:sha(b['request_sha256'],'request_SHA');need(b['request_sha256']==digest(rawreq),'POST_request_pin')
            else:need(b['request_sha256'] is None,'empty_batch_no_hash')
        need(rawreq is None or len(rawreq)<=16384,'request_cap');requests.append(rawreq)
        if query:query_indices.append(i)
    annotations=None if get else {'queryable_rows':50-no_target,'no_target_rows':no_target,'metadata_unknown_rows':50-sum(family.values()),'nominal_ENZ_rows':family['ENZ'],'nominal_12Z_rows':family['12Z'],'no_selection_batches':13-len(query_indices)}
    return {'profile':profile,'plan':p,'entries':entries,'requests':requests,'query_indices':query_indices,'annotations':annotations,'protocol':protocol,'study':study,'count':count,'limits':GET_LIMITS if get else POST_LIMITS,'claims':GET_CLAIMS if get else POST_CLAIMS,'no_target':no_target}
