"""Independent bounded documentary transport replay; no producer/IO imports."""
import re
import plans
from strict_inputs import Invalid,boolean,decode,digest,fields,integer,need,number,same,sha,text

MAX_JSON=1048576;MAX_MANIFEST=65536;MAX_SUMMARY=65536
ATTEMPT_FIELDS={'request_index','start','end','connected_at','headers_at','first_body_at','http_status','framing','declared','outcome','body','headers','framing_evidence','framing_evidence_complete','observed_bytes','overflow_probe_bytes','consumed_upper','consumption_exact','worker_group','worker_exit_code','worker_exit_confirmed','worker_group_stop_confirmed','attempt_accounting_complete','HTTP200_candidate'}
RECEIPT_FIELDS={'protocol','study_id','plan_sha256','complete','reason','fixture','limits','begin','elapsed_s','controller_exit_code','controller_group_stop_confirmed','request_groups_stop_confirmed','registered_attempts','controller_summary_sha256','result_manifest_sha256','claims'}
SUMMARY_FIELDS={'protocol','complete','reason','begin','returned_at','elapsed_s','manifest_sha256','receipt_sha256','controller_group_stop_confirmed','request_groups_stop_confirmed','registered_attempts','public_aggregate'}
OUTCOMES={'framed_complete','overflow','partial','framing_error','connection_deadline','first_body_deadline','request_deadline','processing_deadline','worker_error','worker_exit'}
REASONS={'complete','incomplete','deadline','controller_failed','group_stop_unconfirmed','finalization_failed'}
FIXED={'roster.private.json','initial.private.json','controller_summary.private.json','receipt.private.json','public_aggregate.json'}


def _claims(v,m):
    fields(v,m['claims'],'claim_keys');need(all(v[k] is False for k in m['claims']),'claims_false')


def _limits(v,m):
    fields(v,m['limits'],'limits_fields')
    for k,expected in m['limits'].items():
        if type(expected) is int:integer(v[k],'limit_integer')
        else:number(v[k],'limit_number')
        need(v[k]==expected,'limit_changed')


def _common(v,m,pin):
    text(v['protocol'],m['protocol'],'protocol');text(v['study_id'],m['study'],'study');text(v['plan_sha256'],pin,'plan_pin')
    need(v['fixture'] is False,'fixture_forbidden');_limits(v['limits'],m);_claims(v['claims'],m);number(v['begin'],'begin')


def _names(m):
    count=m['count'];get=m['profile']=='GET';journals=tuple(f'{i:03d}.selection.private.json' if get else f'{i:03d}.batch.private.json' for i in range(count));requests=tuple(f'{i:03d}.request.private' for i in range(count));bodies=tuple(f'{i:03d}.body.private' for i in range(count));headers=tuple(f'{i:03d}.headers.private.json' for i in range(count));framing=tuple(f'{i:03d}.framing.private' for i in range(count));required=FIXED|set(journals)|{requests[i] for i in range(count) if get or m['requests'][i] is not None};allowed=FIXED|set(journals)|set(requests)|set(bodies)|set(headers)|set(framing)
    return {'journals':journals,'requests':requests,'bodies':bodies,'headers':headers,'framing':framing,'required':required,'allowed':allowed}


def _cap(name,m,n):
    if name in n['bodies']:return m['limits']['body_bytes']
    if name in n['headers'] or name in n['framing']:return 131072
    if name in n['requests']:return 16384
    if name=='roster.private.json':return 131072
    if name=='initial.private.json':return 65536
    if name in n['journals'] or name in ('receipt.private.json','public_aggregate.json'):return 16384
    return MAX_JSON


def _pin(v,label,m,n,named=True):
    fields(v,('name','bytes','sha256') if named else ('bytes','sha256'),label)
    if named:need(type(v['name']) is str and v['name'] in n['allowed'],label+'_name')
    integer(v['bytes'],label+'_bytes');sha(v['sha256'],label+'_sha');return v


def _registered(v,m):
    need(type(v) is list and len(v)<=len(m['query_indices']),'registered_count');groups=[];key='selection_index' if m['profile']=='GET' else 'batch_index'
    for i,r in enumerate(v):
        fields(r,(key,'worker_group'),'registered_keys');need(integer(r[key],'registered_index',0,m['count']-1)==m['query_indices'][i],'registered_prefix');g=integer(r['worker_group'],'registered_group',1);need(g not in groups,'duplicate_group');groups.append(g)
    return groups


def _aggregate(v,m,attempts,accounting,candidates,retained,probes,upper,complete,known):
    get=m['profile']=='GET'
    common={'rows':50,'TRAIN_rows':50,'DEV_rows':0,'accounting_known':known,'whole_complete':complete,'retained_response_bytes':retained,'overflow_probe_bytes':probes,'consumption_upper':upper,'claims':dict(m['claims'])}
    if get:
        no_target=m['no_target'] if known else None
        expected={**common,'excluded_TEST':31,'event_deadlines':150,'selections':50,'no_target_rows':no_target,'attempted_selections':attempts,'unattempted_selections':50-attempts-(m['no_target'] if known else 0),'accounting_complete_selections':accounting+(m['no_target'] if known else 0),'HTTP200_candidate_documents':candidates,'qualified_documents':candidates if complete else 0}
    else:
        ann=m['annotations'];empty=ann['no_selection_batches']
        expected={**common,'metadata_unknown_rows':ann['metadata_unknown_rows'],'nominal_ENZ_rows':ann['nominal_ENZ_rows'],'nominal_12Z_rows':ann['nominal_12Z_rows'],'queryable_rows':ann['queryable_rows'],'no_target_rows':ann['no_target_rows'],'no_selection_batches':empty,'batches':13,'attempted_batches':attempts,'unattempted_batches':13-empty-attempts,'accounting_complete_batches':accounting,'HTTP200_candidate_batches':candidates,'qualified_batches':candidates if complete else 0}
    fields(v,expected,'aggregate_fields')
    for k,e in expected.items():
        if k=='claims':_claims(v[k],m)
        elif type(e) is bool:need(v[k] is e,'aggregate_boolean')
        elif e is None:need(v[k] is None,'aggregate_unknown_null')
        else:need(integer(v[k],'aggregate_integer')==e,'aggregate_disagreement')


def _header(h,r):
    fields(h,('status','framing','declared','fields','parser_limits'),'header_fields');integer(h['status'],'header_status',100,999);integer(r['http_status'],'row_http_status',100,999)
    fields(h['parser_limits'],('line_bytes','header_count','chunk_trailer_count'),'parser_limits')
    for k,e in [('line_bytes',65536),('header_count',100),('chunk_trailer_count',100)]:need(integer(h['parser_limits'][k],'parser_limit')==e,'parser_limit_changed')
    pairs=h['fields'];need(type(pairs) is list and len(pairs)<=100,'header_pairs');cl=[];te=[]
    for pair in pairs:
        need(type(pair) is list and len(pair)==2 and all(type(x) is str for x in pair),'header_pair_type')
        if pair[0].casefold()=='content-length':cl.append(pair[1])
        if pair[0].casefold()=='transfer-encoding':te.append(pair[1])
    invalid=r['http_status']<200 or len(cl)>1 or len(te)>1 or bool(cl and te)
    if cl:invalid=invalid or re.fullmatch(r'[0-9]{1,20}',cl[0]) is None
    if te:invalid=invalid or te[0].casefold()!='chunked'
    framing='unknown';declared=None
    if not invalid:
        declared=int(cl[0]) if cl else None
        framing='no_body' if r['http_status'] in (204,304) else 'fixed' if cl else 'chunked' if te else 'eof'
    need(same(h['status'],r['http_status']) and same(h['framing'],r['framing']) and same(h['declared'],r['declared']),'header_row_parity')
    need(h['framing']==framing and same(h['declared'],declared),'independent_framing')


def _closed_chunks(raw,observed):
    need(type(raw) is bytes and len(raw)<=131072,'chunk_bound');position=0;bodyposition=0
    def line():
        nonlocal position
        end=raw.find(b'\r\n',position)
        if end<0 or end+2-position>65536:return None
        s=raw[position:end];position=end+2;return s
    while True:
        s=line()
        if s is None or re.fullmatch(rb'[0-9A-Fa-f]{1,16}(?:;[\x20-\x7e]*)?',s) is None:return False
        size=int(s.split(b';',1)[0],16)
        if size:
            bodyposition+=size
            if bodyposition>observed or raw[position:position+2]!=b'\r\n':return False
            position+=2;continue
        for _ in range(100):
            t=line()
            if t is None:return False
            if t==b'':return position==len(raw) and bodyposition==observed
            if re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+:[\x09\x20-\x7e]*",t) is None:return False
        return False


def _base(m,i,request,initial=False):
    entry=m['entries'][i];get=m['profile']=='GET';key='selection_index' if get else 'batch_index'
    base={key:i,'row_indices':entry['row_indices'],'request':request}
    if not get:base['requested_row_indices']=entry['requested_row_indices']
    if initial:base['status']='unattempted' if get or m['requests'][i] is not None else 'no_selection'
    return base


def _attempt(r,i,basekeys,begin,processing,previous_start,previous_end,m,n):
    fields(r,basekeys|ATTEMPT_FIELDS,'attempt_fields');limit=m['limits'];start=number(r['start'],'attempt_start');end=number(r['end'],'attempt_end')
    need(begin<=start<begin+limit['processing_s'] and start<=end<=begin+processing,'attempt_clock')
    if previous_start is not None:need(start-previous_start>=limit['start_spacing_s'] and start>=previous_end,'attempt_spacing_overlap')
    last=start
    for k in ('connected_at','headers_at','first_body_at'):
        if r[k] is not None:last0=number(r[k],'phase');need(last<=last0<=end,'phase_order');last=last0
    if r['http_status'] is not None:need(type(r['http_status']) is int,'http_status_type')
    if r['declared'] is not None:integer(r['declared'],'declared')
    need(type(r['framing']) is str and r['framing'] in ('fixed','chunked','eof','no_body','unknown'),'framing');need(type(r['outcome']) is str and r['outcome'] in OUTCOMES,'outcome')
    observed=integer(r['observed_bytes'],'observed',0,limit['body_bytes']);probe=integer(r['overflow_probe_bytes'],'probe',0,1);upper=integer(r['consumed_upper'],'upper',observed+probe,limit['body_bytes']+1);exact=boolean(r['consumption_exact'],'consumption_exact')
    if exact:
        need(upper==observed+probe,'exact_consumption')
        if probe:need(observed==limit['body_bytes'] and r['outcome']=='overflow','probe_at_cap')
    else:need(upper==limit['body_bytes']+1,'unknown_full_charge')
    integer(r['worker_group'],'worker_group',1)
    if r['worker_exit_code'] is not None:need(type(r['worker_exit_code']) is int,'worker_exit_type')
    for k in ('worker_exit_confirmed','worker_group_stop_confirmed','attempt_accounting_complete','HTTP200_candidate','framing_evidence_complete'):boolean(r[k],'attempt_bool')
    payloads=set();body=r['body'];header=r['headers'];syntax=r['framing_evidence']
    if body is None:need(observed==0,'missing_body_count')
    else:_pin(body,'body_pin',m,n);need(body['name']==n['bodies'][i] and body['bytes']==observed,'body_binding');payloads.add(body['name'])
    if header is not None:_pin(header,'header_pin',m,n);need(header['name']==n['headers'][i] and header['bytes']<=131072,'header_binding');payloads.add(header['name'])
    else:need(r['http_status'] is None and r['framing']=='unknown' and r['declared'] is None,'pre_response_metadata')
    if r['framing']=='chunked':
        if syntax is not None:_pin(syntax,'framing_pin',m,n);need(syntax['name']==n['framing'][i] and syntax['bytes']<=131072,'framing_binding');payloads.add(syntax['name'])
        need(not r['framing_evidence_complete'] or syntax is not None,'syntax_flag_without_member')
    else:need(syntax is None and r['framing_evidence_complete'] is False,'nonchunked_syntax')
    need((header['bytes'] if header else 0)+(syntax['bytes'] if syntax else 0)<=131072,'combined_diagnostic_cap')
    if r['outcome']=='framed_complete':
        need(r['framing'] in ('fixed','chunked','eof','no_body') and body is not None and header is not None and exact and probe==0,'framed_evidence')
        if r['framing']=='fixed':need(r['declared'] is not None and observed==r['declared'],'fixed_length')
        elif r['framing']=='no_body':need(r['http_status'] in (204,304) and observed==0,'no_body')
        else:need(r['declared'] is None,'nonfixed_declared')
        if r['framing']=='chunked':need(syntax is not None and r['framing_evidence_complete'] is True,'complete_chunk_evidence')
    complete=bool(r['outcome']=='framed_complete' and exact and probe==0 and (r['framing']!='chunked' or r['framing_evidence_complete'] is True) and body is not None and header is not None and r['worker_exit_confirmed'] is True and r['worker_group_stop_confirmed'] is True and r['worker_exit_code']==0 and r['connected_at'] is not None and r['headers_at'] is not None and r['connected_at']-start<=limit['connection_s'] and r['headers_at']-start<=limit['first_body_s'] and (observed==0 or r['first_body_at'] is not None and r['first_body_at']-start<=limit['first_body_s']) and end-start<=limit['request_s'] and end-begin<=limit['processing_s'])
    candidate=complete and r['http_status']==200 and observed>0;need(r['attempt_accounting_complete'] is complete and r['HTTP200_candidate'] is candidate,'computed_attempt_flags')
    return complete,candidate,observed,probe,upper,start,end,payloads


def _result(profile):
    return {'audit_protocol':'geonet-train50-'+profile+'-independent-audit-v1','valid':False,'finalization_verified':False,'whole_complete':False,'fixed_rows':50,'logical_requests':50 if profile=='GET' else 13,'qualified_requests':0,'aggregate':None,'transport':None,'filesystem_inventory_verified':False,'original_selection_authenticated':False,'source_runtime_authenticated':False,'physical_process_stop_verified':False,'physical_clock_verified':False,'registered_setup_accounting_verified':False,'preserve_parent_artifacts':True,'issues':[]}


def run_audit(profile,plan_bytes,manifest_bytes,bounded_member_reader,*,execution_summary_bytes=None,execution_summary_pin=None):
    result=_result(profile)
    try:
        m=plans.validate(plan_bytes,profile);n=_names(m);planpin=digest(plan_bytes);get=profile=='GET';collection='selections' if get else 'batches';key='selection_index' if get else 'batch_index'
        _pin(execution_summary_pin,'execution_pin',m,n,False);need(execution_summary_pin['bytes']<=MAX_SUMMARY,'execution_pin_bound');summary=decode(execution_summary_bytes,MAX_SUMMARY,'execution')
        need(len(execution_summary_bytes)==execution_summary_pin['bytes'] and digest(execution_summary_bytes)==execution_summary_pin['sha256'],'execution_pin_parity');fields(summary,SUMMARY_FIELDS,'execution_fields');text(summary['protocol'],m['protocol'],'execution_protocol');boolean(summary['complete'],'execution_complete');need(type(summary['reason']) is str and summary['reason'] in REASONS,'execution_reason')
        begin=number(summary['begin'],'execution_begin');returned=number(summary['returned_at'],'execution_return');elapsed=number(summary['elapsed_s'],'execution_elapsed');need(returned>=begin and elapsed==returned-begin,'execution_clock')
        for k in ('controller_group_stop_confirmed','request_groups_stop_confirmed'):boolean(summary[k],'execution_stop_flag')
        registered=_registered(summary['registered_attempts'],m);aggregate=summary['public_aggregate'];need(type(aggregate) is dict,'aggregate_object');boolean(aggregate.get('accounting_known'),'accounting_known')
        if aggregate['accounting_known'] is False:
            need(summary['complete'] is False and summary['reason']!='complete' and summary['manifest_sha256'] is None and summary['receipt_sha256'] is None and manifest_bytes is None,'sparse_finalization');_aggregate(aggregate,m,len(registered),0,0,None,None,len(registered)*(m['limits']['body_bytes']+1),False,False)
            result.update(aggregate=aggregate,registered_setup_accounting_verified=True,issues=['sparse_incomplete_accounting']);return result
        need(elapsed<m['limits']['whole_s'] if get else elapsed<=m['limits']['whole_s'],'whole_deadline');sha(summary['manifest_sha256'],'manifest_sha');sha(summary['receipt_sha256'],'receipt_sha');need(type(manifest_bytes) is bytes and 0<len(manifest_bytes)<=MAX_MANIFEST and digest(manifest_bytes)==summary['manifest_sha256'],'returned_manifest')
        manifest=decode(manifest_bytes,MAX_MANIFEST,'manifest');fields(manifest,('protocol','members'),'manifest_fields');text(manifest['protocol'],m['protocol'],'manifest_protocol');need(type(manifest['members']) is list and len(n['required'])<=len(manifest['members'])<=len(n['required'])+3*m['count'],'manifest_count');pins={}
        for pin in manifest['members']:
            _pin(pin,'member_pin',m,n);name=pin['name'];need(name not in pins and pin['bytes']<=_cap(name,m,n),'member_duplicate_bound');pins[name]=pin
        need(n['required']<=pins.keys(),'required_members');need(callable(bounded_member_reader),'reader_callable');seen=set();cache={}
        def read(name,keep=True):
            if name in cache:return cache[name]
            need(name in pins and name not in seen,'member_missing_repeated')
            try:raw=bounded_member_reader(name,_cap(name,m,n))
            except Exception:raise Invalid('member_reader_failure') from None
            need(type(raw) is bytes and len(raw)<=_cap(name,m,n),'member_reader_cap');p=pins[name];need(len(raw)==p['bytes'] and digest(raw)==p['sha256'],'member_pin_parity');seen.add(name)
            if keep:cache[name]=raw
            return raw
        need(read('roster.private.json')==plan_bytes,'original_roster_bytes');initial=decode(read('initial.private.json'),MAX_JSON,'initial');controllerraw=read('controller_summary.private.json');controller=decode(controllerraw,MAX_JSON,'controller');receiptraw=read('receipt.private.json');receipt=decode(receiptraw,MAX_JSON,'receipt');savedaggregate=decode(read('public_aggregate.json'),MAX_JSON,'saved_aggregate')
        initialfields={'protocol','study_id','plan_sha256','fixture','limits','begin','claims',collection}
        if not get:initialfields.add('row_annotations')
        controllerfields=initialfields|{'processing_elapsed','attempts','retained_bytes','overflow_probe_bytes','consumption_upper','HTTP200_candidates','candidate_complete','worker_groups'}
        fields(initial,initialfields,'initial_fields');fields(controller,controllerfields,'controller_fields');fields(receipt,RECEIPT_FIELDS,'receipt_fields')
        for v in (initial,controller,receipt):_common(v,m,planpin);need(same(v['begin'],begin),'common_begin')
        if not get:need(same(initial['row_annotations'],m['annotations']) and same(controller['row_annotations'],m['annotations']),'row_annotations')
        need(type(initial[collection]) is list and len(initial[collection])==m['count'] and type(controller[collection]) is list and len(controller[collection])==m['count'],'logical_rows')
        processing=number(controller['processing_elapsed'],'processing_elapsed');final=number(receipt['elapsed_s'],'receipt_elapsed');need(0<=processing<=m['limits']['processing_s'] and processing<=final<=elapsed,'saved_elapsed');need(receipt['result_manifest_sha256'] is None,'saved_manifest_cycle');sha(receipt['controller_summary_sha256'],'controller_sha');need(receipt['controller_summary_sha256']==digest(controllerraw) and summary['receipt_sha256']==digest(receiptraw),'saved_returned_pins')
        requestpins={}
        for i in range(m['count']):
            raw=m['requests'][i]
            if get or raw is not None:need(read(n['requests'][i])==raw,'saved_canonical_request');requestpins[i]=pins[n['requests'][i]]
            else:requestpins[i]=None
            base=_base(m,i,requestpins[i],True);fields(initial[collection][i],base,'initial_logical_fields');need(same(initial[collection][i],base),'initial_logical_binding')
        attempts=accounting=candidates=retained=probes=upper=0;groups=[];payloads=set();previous_start=previous_end=None;halted=False;incomplete=False;private_rows=[]
        for i,row in enumerate(controller[collection]):
            base=_base(m,i,requestpins[i]);basekeys=set(base)|{'status'};need(type(row) is dict and all(type(k) is str for k in row),'final_row_object');need(basekeys<=row.keys(),'final_base');need(all(same(row[k],v) for k,v in base.items()),'final_logical_binding');journal=decode(read(n['journals'][i]),16384,'journal');need(same(journal,row),'journal_controller_parity');no_selection=(m['plan']['rows'][i]['selected_target'] is None) if get else m['requests'][i] is None
            if no_selection:
                fields(row,basekeys|{'reason'},'no_selection_fields');text(row['status'],'no_target' if get else 'no_selection','no_selection_status');text(row['reason'],'no_queryable_target' if get else 'no_queryable_rows','no_selection_reason')
                if get:private_rows.append({'row_index':i,'classification':'no_target','http_status':None,'request_sha256':m['entries'][i]['request_sha256'],'body_bytes':None,'body_sha256':None})
                continue
            if row['status']=='unattempted':
                fields(row,basekeys|{'reason'},'unattempted_fields');need(type(row['reason']) is str and row['reason'] in ('halted_after_incomplete','launch_cutoff','total_cap'),'unattempted_reason')
                if row['reason']=='halted_after_incomplete':need(incomplete,'halted_evidence')
                elif row['reason']=='launch_cutoff':need(processing>=m['limits']['processing_s'],'launch_cutoff_evidence')
                else:need(retained==m['limits']['total_retained_bytes'] or upper==m['limits']['total_consumption_upper'],'total_cap_evidence')
                halted=True
            elif row['status']=='attempted':
                need(not halted,'attempt_after_halt');need(integer(row.get('request_index'),'request_index',0,m['count']-1)==attempts and i==m['query_indices'][attempts],'attempt_prefix')
                comp,cand,obs,probe,charge,previous_start,previous_end,newpayload=_attempt(row,i,basekeys,begin,processing,previous_start,previous_end,m,n)
                if row['headers'] is not None:
                    name=row['headers']['name'];need(name in pins and same(pins[name],row['headers']),'header_manifest');_header(decode(read(name),131072,'headers'),row)
                if row['framing_evidence'] is not None:
                    name=row['framing_evidence']['name'];need(name in pins and same(pins[name],row['framing_evidence']),'framing_manifest');closed=_closed_chunks(read(name),obs);need(not row['framing_evidence_complete'] or closed,'chunk_not_closed')
                if row['body'] is not None:need(row['body']['name'] in pins and same(pins[row['body']['name']],row['body']),'body_manifest')
                payloads|=newpayload;g=row['worker_group'];need(g not in groups,'duplicate_worker');groups.append(g);attempts+=1;accounting+=comp;candidates+=cand;retained+=obs;probes+=probe;upper+=charge
                need(retained<=m['limits']['total_retained_bytes'] and probes<=m['count'] and upper<=m['limits']['total_consumption_upper'],'aggregate_caps');halted=not comp;incomplete=incomplete or not comp
                if get:private_rows.append({'row_index':i,'classification':'http200' if cand else 'nonpositive','http_status':row['http_status'],'request_sha256':m['entries'][i]['request_sha256'],'body_bytes':obs,'body_sha256':row['body']['sha256'] if row['body'] is not None else None})
            else:raise Invalid('row_status')
        need(set(pins)==n['required']|payloads,'closed_member_set')
        for k,e in [('attempts',attempts),('retained_bytes',retained),('overflow_probe_bytes',probes),('consumption_upper',upper),('HTTP200_candidates',candidates)]:need(integer(controller[k],'controller_total')==e,'controller_total_parity')
        need(same(controller['worker_groups'],groups) and registered==groups and same(receipt['registered_attempts'],summary['registered_attempts']),'registered_controller_parity');candidatecomplete=accounting==len(m['query_indices']);need(controller['candidate_complete'] is candidatecomplete,'controller_candidate_complete');boolean(receipt['complete'],'receipt_complete');need(type(receipt['reason']) is str and receipt['reason'] in REASONS,'receipt_reason')
        if receipt['controller_exit_code'] is not None:need(type(receipt['controller_exit_code']) is int,'controller_exit_type')
        need(receipt['controller_exit_code']==0,'known_controller_not_normal')
        for k in ('controller_group_stop_confirmed','request_groups_stop_confirmed'):boolean(receipt[k],'receipt_stop_flag');need(receipt[k] is summary[k],'stop_returned_parity')
        need(receipt['complete'] is summary['complete'] and receipt['reason']==summary['reason'],'receipt_execution_parity');complete=receipt['complete'];need((receipt['reason']=='complete') is complete,'completion_reason')
        if complete:need(candidatecomplete and receipt['controller_group_stop_confirmed'] is True and receipt['request_groups_stop_confirmed'] is True,'whole_complete_evidence')
        _aggregate(savedaggregate,m,attempts,accounting,candidates,retained,probes,upper,False,True);_aggregate(aggregate,m,attempts,accounting,candidates,retained,probes,upper,complete,True)
        promotion={'whole_complete','qualified_documents' if get else 'qualified_batches'};need(all(same(savedaggregate[k],aggregate[k]) for k in savedaggregate if k not in promotion),'provisional_boundary')
        for name in sorted(payloads&set(n['bodies'])):read(name,False)
        need(seen==set(pins),'unreplayed_member');result.update(valid=True,finalization_verified=complete,whole_complete=complete,qualified_requests=candidates if complete else 0,aggregate=aggregate,registered_setup_accounting_verified=True)
        if get and complete:result['transport']={'protocol':m['protocol'],'plan_sha256':planpin,'manifest_sha256':summary['manifest_sha256'],'receipt_sha256':summary['receipt_sha256'],'returned_sha256':digest(execution_summary_bytes),'whole_complete':True,'rows':private_rows}
    except Invalid as exc:result['issues']=[str(exc)]
    except Exception:result['issues']=['audit_input_failure']
    return result


def public_summary(result):
    need(type(result) is dict,'result_object')
    return {k:result[k] for k in ('audit_protocol','valid','finalization_verified','whole_complete','fixed_rows','logical_requests','qualified_requests','filesystem_inventory_verified','original_selection_authenticated','source_runtime_authenticated','physical_process_stop_verified','physical_clock_verified','issues')}
