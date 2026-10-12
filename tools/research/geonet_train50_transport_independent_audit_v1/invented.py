"""Independent synthetic contract fixtures; no producer/data/network imports."""
import copy
import hashlib
import json
import plans


def raw(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')
def pin(n,b):return {'name':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}


def plan(profile,no_target=()):
    missing=set(no_target);get=profile=='GET';rows=[]
    for i in range(50):
        t=946684800*10**9+i*10**9+123456789
        target={'network':'NZ','station':f'X{i:03d}','location':'','prefix':'HH','pick_ns':t,'original_target_index':0}
        if get:r={'row_index':i,'global_index':65+i,'event_id':f'INVENTED-{i}','partition':'TRAIN','t0_ns':t,'selected_target':None if i in missing else target,'selection_reason':'no original queryable target' if i in missing else None}
        else:
            r={'row_index':i,'global_ordinal':65+i,'original_event_index':494-i,'original_target_index':None if i in missing else 0,'event_id':f'INVENTED-{i}','partition':'TRAIN','network':None if i in missing else 'NZ','station':None if i in missing else f'X{i:03d}','location':None if i in missing else '', 'prefix':None if i in missing else 'HH','t0_ns':t,'pick_ns':None if i in missing else t,'metadata_status':'no_target' if i in missing else 'unknown' if i%3==0 else 'known','nominal_family':None if i in missing or i%3==0 else 'ENZ' if i%2==0 else '12Z'}
        rows.append(r)
    entries=[]
    if get:
        for i,r in enumerate(rows):
            url=plans.get_url(r);body=b'' if url is None else (url+'\n').encode('ascii')
            entries.append({'selection_index':i,'row_indices':[i],'request_url':url,'request_sha256':hashlib.sha256(body).hexdigest()})
    else:
        for i in range(13):
            ids=list(range(4*i,min(4*i+4,50)));requested=[j for j in ids if j not in missing];body=plans.post_entity([rows[j] for j in requested]);entries.append({'batch_index':i,'row_indices':ids,'requested_row_indices':requested,'request_body':None if body is None else body.decode('ascii'),'request_sha256':None if body is None else hashlib.sha256(body).hexdigest()})
    prereqs={k:hashlib.sha256(k.encode()).hexdigest() for k in plans.PREREQS+(('metadata_custody_sha256',) if not get else ())}
    return {'protocol':plans.GET_PROTOCOL if get else plans.POST_PROTOCOL,'study_id':plans.GET_STUDY if get else plans.POST_STUDY,'proposal_sha256':plans.ROOT_SHA,'rows':rows,'selections' if get else 'batches':entries,'prerequisites':prereqs}


class Bundle:
    def __init__(self,profile,no_target=(),incomplete_at=None):
        self.profile=profile;self.get=profile=='GET';self.plan=plan(profile,no_target);self.meta=plans.validate(raw(self.plan),profile);self.collection='selections' if self.get else 'batches';self.key='selection_index' if self.get else 'batch_index';self.members={};self.initialrows=[];self.finalrows=[];self.calls=[];self.complete=incomplete_at is None
        index=0;halted=False
        for i,e in enumerate(self.meta['entries']):
            req=self.meta['requests'][i];request=None
            if self.get or req is not None:
                name=f'{i:03d}.request.private';self.members[name]=req;request=pin(name,req)
            base={self.key:i,'row_indices':e['row_indices'],'request':request}
            if not self.get:base['requested_row_indices']=e['requested_row_indices']
            no_selection=(self.plan['rows'][i]['selected_target'] is None) if self.get else req is None
            self.initialrows.append({**copy.deepcopy(base),'status':'unattempted' if self.get or not no_selection else 'no_selection'})
            if no_selection:self.finalrows.append({**base,'status':'no_target' if self.get else 'no_selection','reason':'no_queryable_target' if self.get else 'no_queryable_rows'});continue
            if halted:self.finalrows.append({**base,'status':'unattempted','reason':'halted_after_incomplete'});continue
            b=b'body'+bytes([65+i]);header={'status':200,'framing':'fixed','declared':len(b),'fields':[['Content-Length',str(len(b))]],'parser_limits':{'line_bytes':65536,'header_count':100,'chunk_trailer_count':100}};bn=f'{i:03d}.body.private';hn=f'{i:03d}.headers.private.json';self.members[bn]=b;self.members[hn]=raw(header);start=101.+index*3
            row={**base,'status':'attempted','request_index':index,'start':start,'end':start+.5,'connected_at':start+.1,'headers_at':start+.2,'first_body_at':start+.3,'http_status':200,'framing':'fixed','declared':len(b),'outcome':'framed_complete','body':pin(bn,b),'headers':pin(hn,raw(header)),'framing_evidence':None,'framing_evidence_complete':False,'observed_bytes':len(b),'overflow_probe_bytes':0,'consumed_upper':len(b),'consumption_exact':True,'worker_group':1000+i,'worker_exit_code':0,'worker_exit_confirmed':True,'worker_group_stop_confirmed':True,'attempt_accounting_complete':True,'HTTP200_candidate':True}
            if incomplete_at==i:row.update(outcome='partial',attempt_accounting_complete=False,HTTP200_candidate=False);halted=True
            self.finalrows.append(row);index+=1
        self.refresh()

    def response(self,i,status=200,body=b'bodyA',framing='fixed',syntax=None):
        row=self.finalrows[i];self.members[f'{i:03d}.body.private']=body;fields=[['Content-Length',str(len(body))]] if framing=='fixed' else [['Transfer-Encoding','chunked']] if framing=='chunked' else []
        if framing=='no_body':fields=[['Content-Length','123']]
        declared=len(body) if framing=='fixed' else 123 if framing=='no_body' else None
        h={'status':status,'framing':framing,'declared':declared,'fields':fields,'parser_limits':{'line_bytes':65536,'header_count':100,'chunk_trailer_count':100}};hb=raw(h);self.members[f'{i:03d}.headers.private.json']=hb
        row.update(http_status=status,framing=framing,declared=declared,body=pin(f'{i:03d}.body.private',body),headers=pin(f'{i:03d}.headers.private.json',hb),observed_bytes=len(body),consumed_upper=len(body),first_body_at=row['start']+.3 if body else None,HTTP200_candidate=status==200 and bool(body),framing_evidence_complete=framing=='chunked')
        if syntax is not None:self.members[f'{i:03d}.framing.private']=syntax;row['framing_evidence']=pin(f'{i:03d}.framing.private',syntax)
        self.refresh()

    def refresh(self):
        m=self.meta;get=self.get;count=m['count'];base={'protocol':m['protocol'],'study_id':m['study'],'plan_sha256':hashlib.sha256(raw(self.plan)).hexdigest(),'fixture':False,'limits':copy.deepcopy(m['limits']),'begin':100.,'claims':dict(m['claims'])}
        if not get:base['row_annotations']=dict(m['annotations'])
        initial={**base,self.collection:self.initialrows};attempts=[r for r in self.finalrows if r['status']=='attempted'];processing=max([r['end']-100. for r in attempts]+[1.])+1.;ncomplete=sum(r['attempt_accounting_complete'] for r in attempts);npositive=sum(r['HTTP200_candidate'] for r in attempts);retained=sum(r['observed_bytes'] for r in attempts);probes=sum(r['overflow_probe_bytes'] for r in attempts);upper=sum(r['consumed_upper'] for r in attempts);registered=[{self.key:r[self.key],'worker_group':r['worker_group']} for r in attempts];controller={**base,self.collection:self.finalrows,'processing_elapsed':processing,'attempts':len(attempts),'retained_bytes':retained,'overflow_probe_bytes':probes,'consumption_upper':upper,'HTTP200_candidates':npositive,'candidate_complete':ncomplete==len(m['query_indices']),'worker_groups':[r['worker_group'] for r in attempts]}
        common={'rows':50,'TRAIN_rows':50,'DEV_rows':0,'accounting_known':True,'whole_complete':self.complete,'retained_response_bytes':retained,'overflow_probe_bytes':probes,'consumption_upper':upper,'claims':dict(m['claims'])}
        if get:aggregate={**common,'excluded_TEST':31,'event_deadlines':150,'selections':50,'no_target_rows':m['no_target'],'attempted_selections':len(attempts),'unattempted_selections':50-len(attempts)-m['no_target'],'accounting_complete_selections':ncomplete+m['no_target'],'HTTP200_candidate_documents':npositive,'qualified_documents':npositive if self.complete else 0}
        else:
            a=m['annotations'];aggregate={**common,'metadata_unknown_rows':a['metadata_unknown_rows'],'nominal_ENZ_rows':a['nominal_ENZ_rows'],'nominal_12Z_rows':a['nominal_12Z_rows'],'queryable_rows':a['queryable_rows'],'no_target_rows':a['no_target_rows'],'no_selection_batches':a['no_selection_batches'],'batches':13,'attempted_batches':len(attempts),'unattempted_batches':13-a['no_selection_batches']-len(attempts),'accounting_complete_batches':ncomplete,'HTTP200_candidate_batches':npositive,'qualified_batches':npositive if self.complete else 0}
        saved=copy.deepcopy(aggregate);saved['whole_complete']=False;saved['qualified_documents' if get else 'qualified_batches']=0
        self.members['roster.private.json']=raw(self.plan);self.members['initial.private.json']=raw(initial);self.members['controller_summary.private.json']=raw(controller);self.members['public_aggregate.json']=raw(saved)
        for i,r in enumerate(self.finalrows):self.members[f'{i:03d}.selection.private.json' if get else f'{i:03d}.batch.private.json']=raw(r)
        receipt={**base,'complete':self.complete,'reason':'complete' if self.complete else 'incomplete','elapsed_s':processing+.25,'controller_exit_code':0,'controller_group_stop_confirmed':True,'request_groups_stop_confirmed':True,'registered_attempts':registered,'controller_summary_sha256':hashlib.sha256(raw(controller)).hexdigest(),'result_manifest_sha256':None}
        receipt.pop('row_annotations',None)
        self.members['receipt.private.json']=raw(receipt);manifest={'protocol':m['protocol'],'members':[pin(n,b) for n,b in sorted(self.members.items())]};self.manifest=raw(manifest)
        summary={'protocol':m['protocol'],'complete':self.complete,'reason':'complete' if self.complete else 'incomplete','begin':100.,'returned_at':100.+processing+.5,'elapsed_s':processing+.5,'manifest_sha256':hashlib.sha256(self.manifest).hexdigest(),'receipt_sha256':hashlib.sha256(raw(receipt)).hexdigest(),'controller_group_stop_confirmed':True,'request_groups_stop_confirmed':True,'registered_attempts':registered,'public_aggregate':aggregate}
        self.summary=raw(summary);self.summarypin={'bytes':len(self.summary),'sha256':hashlib.sha256(self.summary).hexdigest()};self.planbytes=raw(self.plan)

    def repin_manifest(self):
        self.manifest=raw({'protocol':self.meta['protocol'],'members':[pin(n,b) for n,b in sorted(self.members.items())]});s=json.loads(self.summary);s['manifest_sha256']=hashlib.sha256(self.manifest).hexdigest();self.summary=raw(s);self.summarypin={'bytes':len(self.summary),'sha256':hashlib.sha256(self.summary).hexdigest()}

    def read(self,name,cap):
        self.calls.append(name);b=self.members[name]
        if len(b)>cap:raise ValueError('invented_read_cap')
        return b

    def audit(self):
        import get_audit,post_audit
        mod=get_audit if self.get else post_audit
        return mod.audit(self.planbytes,self.manifest,self.read,execution_summary_bytes=self.summary,execution_summary_pin=self.summarypin)
