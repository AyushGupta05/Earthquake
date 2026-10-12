"""Pure fixed50 positive-custody metadata interpretation; no IO or acquisition."""
from decimal import Decimal
from fractions import Fraction
import re
import collector as c
import metadata_reference as core

SCHEMA='geonet-train50-selected-epoch-qualification-v1'
MAX_BODY=131072
MAX_TOTAL=6553600
MAX_PRIVATE=16*1024*1024
MAX_PUBLIC=65536
CLAIMS={k:False for k in ('full_xsd_validation','full_response','physical_axes','calibration','waveform_continuity','archive_holdings','physical_absence','online_timing','sequence_independence','usable_training_cohort','accuracy_improved','novelty','published_superiority')}


def _empty(row,reason,raw=None):
    target=row['selected_target']
    return dict(slot_id='row_%03d'%row['row_index'],t0_ns=row['t0_ns'],scope={k:target[k] for k in ('network','station','location','prefix')} if target else None,
                expected_sha256=c.sha(raw) if raw is not None else None,observed_sha256=c.sha(raw) if raw is not None else None,bytes=len(raw) if raw is not None else None,
                document_state='unknown',reason=reason,source_run_complete=False,schema_version=None,node_count=None,channels=[],literal_codes=[])


def _describe(document,t0):
    for channel in document['channels']:
        descriptors={}
        for h in (1,3,5):
            descriptor=None
            if channel['horizon_support'][str(h)]=='supported':
                matches=[i for i,r in enumerate(channel['epochs']) if all(core._contains(r[f],t0-3*10**9,t0+h*10**9)=='supported' for f in ('channel_epoch','station_epoch','network_epoch'))]
                if len(matches)!=1:raise ValueError('unique epoch descriptor')
                epoch=channel['epochs'][matches[0]]
                descriptor={k:epoch[k] for k in ('sample_rate','azimuth','dip','response')};descriptor['epoch_record_index']=matches[0]
            descriptors[str(h)]=descriptor
        channel['horizon_descriptors']=descriptors


def _safe_rate(description):
    """Bound representation before any power-of-ten integer expansion.

    Keep raw metadata untouched. Exact tuple trailing-zero removal does not use
    Decimal.normalize(), which could round under the caller's Decimal context.
    """
    raw=description['exact_decimal']
    if type(raw) is not str or len(raw)>MAX_BODY or re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?',raw) is None:return None
    value=Decimal(raw)
    if not value.is_finite() or value<=0:return None
    sign,digits,exponent=value.as_tuple();digits=list(digits)
    while len(digits)>1 and digits[-1]==0:digits.pop();exponent+=1
    if max(len(digits)+max(exponent,0),1+max(-exponent,0))>1024:return None
    return Fraction(Decimal((sign,tuple(digits),exponent)))


def _candidate(document,target,family,h):
    if target is None:return None,None
    channels={r['code']:r for r in document['channels']};descriptors=[]
    for suffix in family:
        record=channels.get(target['prefix']+suffix)
        if record is None:return None,None
        d=record['horizon_descriptors'][str(h)]
        if d is None or d['sample_rate']['valid'] is not True:return None,None
        descriptors.append(dict(channel=target['prefix']+suffix,**d))
    rates=[_safe_rate(d['sample_rate']) for d in descriptors]
    return (True,descriptors) if all(r is not None for r in rates) and rates[0]==rates[1]==rates[2] else (None,None)


def qualify(plan,transport,documents):
    if type(plan) is bytes:plan=c.validate_plan(plan)
    if type(plan) is not c.Plan or c.validate_plan(plan.source_bytes)!=plan:raise ValueError('immutable plan')
    projection=c.strict_json(plan.source_bytes)
    c.fields(transport,('protocol','plan_sha256','manifest_sha256','receipt_sha256','returned_sha256','whole_complete','rows'))
    if transport['protocol']!=c.PROTOCOL or type(transport['whole_complete']) is not bool or transport['whole_complete'] is not True or c.hashtext(transport['plan_sha256'])!=plan.sha256:raise ValueError('whole independent transport gate')
    for field in ('manifest_sha256','receipt_sha256','returned_sha256'):c.hashtext(transport[field])
    if type(transport['rows']) is not list or len(transport['rows'])!=50 or type(documents) is not list or len(documents)!=50 or any(d is not None and type(d) is not bytes for d in documents):raise ValueError('fixed50 inputs')
    admitted=sum(len(d) for d in documents if d is not None and len(d)<=MAX_BODY)
    if admitted>MAX_TOTAL:raise ValueError('cumulative parser admission')
    private=[];counts=dict(events=50,TRAIN=50,DEV=0,excluded_TEST=31,event_deadlines=150,input_states={k:0 for k in ('no_target','http200','nonpositive')},valid_scope_documents=0,unknown_documents=0,nominal_families={k:0 for k in ('ENZ','12Z','unknown')},horizons={str(h):dict(ENZ_positive=0,numbered_positive=0,pick_before=0,pick_not_before=0,pick_unknown=0) for h in (1,3,5)},claims=dict(CLAIMS))
    for i,(row,evidence,raw) in enumerate(zip(projection['rows'],transport['rows'],documents)):
        c.fields(evidence,('row_index','classification','http_status','request_sha256','body_bytes','body_sha256'))
        c.integer(evidence['row_index'],i,i)
        classification=c.text(evidence['classification'],r'no_target|http200|nonpositive')
        if c.hashtext(evidence['request_sha256'])!=projection['selections'][i]['request_sha256']:raise ValueError('canonical request custody')
        no_target=row['selected_target'] is None
        if (classification=='no_target')!=no_target:raise ValueError('no-target binding')
        if no_target:
            if raw is not None or any(evidence[k] is not None for k in ('http_status','body_bytes','body_sha256')):raise ValueError('no-target null custody')
            document=_empty(row,'no_queryable_target')
        else:
            c.integer(evidence['http_status'],200,999);c.integer(evidence['body_bytes'],0,4194304);c.hashtext(evidence['body_sha256'])
            if classification=='http200':
                if evidence['http_status']!=200 or evidence['body_bytes']==0 or raw is None or len(raw)!=evidence['body_bytes'] or c.sha(raw)!=evidence['body_sha256']:raise ValueError('exact completeHTTP200 bytes')
                if len(raw)>MAX_BODY:document=_empty(row,'document_byte_cap',raw)
                else:
                    slot={k:row['selected_target'][k] for k in ('network','station','location','prefix')}
                    slot.update(slot_id='row_%03d'%i,t0_ns=row['t0_ns'],body_sha256=evidence['body_sha256'],individual_http200_complete=True,custody_verified=True)
                    document=core._document_row(raw,slot)
            else:
                if raw is not None or evidence['http_status']==200 and evidence['body_bytes']>0:raise ValueError('nonpositive disposition')
                document=_empty(row,'complete_nonpositive_transport')
        _describe(document,row['t0_ns']);horizons=[]
        for h in (1,3,5):
            target=row['selected_target'];enz,ed=_candidate(document,target,'ENZ',h);numbered,nd=_candidate(document,target,'12Z',h)
            pick=target['pick_ns']<row['t0_ns']+h*10**9 if target else None
            horizons.append(dict(horizon_s=h,left_ns=row['t0_ns']-3*10**9 if row['t0_ns'] is not None else None,right_ns=row['t0_ns']+h*10**9 if row['t0_ns'] is not None else None,
                                 catalogue_pick_before_cutoff=pick,nominal_family_candidates=dict(ENZ=enz,**{'12Z':numbered}),family_descriptors=dict(ENZ=ed,**{'12Z':nd})))
            counter=counts['horizons'][str(h)];counter['ENZ_positive']+=enz is True;counter['numbered_positive']+=numbered is True;counter['pick_unknown' if pick is None else 'pick_before' if pick else 'pick_not_before']+=1
        family=next((f for f in ('ENZ','12Z') if all(r['nominal_family_candidates'][f] is True for r in horizons)),None)
        rates={}
        if family:
            for d in horizons[2]['family_descriptors'][family]:
                value=_safe_rate(d['sample_rate']);rates[d['channel']]=[value.numerator,value.denominator]
        private.append(dict(row_index=i,global_index=65+i,partition='TRAIN',input_state=classification,document=document,horizons=horizons,nominal_family=family,nominal_rates=rates))
        counts['input_states'][classification]+=1;counts['valid_scope_documents']+=document['document_state']=='valid';counts['unknown_documents']+=document['document_state']=='unknown';counts['nominal_families'][family or 'unknown']+=1
    result=dict(schema=SCHEMA,private_rows=private,public_counts=counts)
    if len(c.encode(result))>MAX_PRIVATE or len(c.encode(counts))>MAX_PUBLIC:raise ValueError('output cap')
    return result
