"""Invented complete custody chains; no actual source inputs or model fits."""
import copy
import time
import unittest
from dataclasses import replace
import adapter as a

H='1'*64
P=dict(bytes=1,sha256=H)

def fixture(stage=0):
    data={};serial=[0]
    def put(v):
        raw=v if type(v)is bytes else a.plain(v);serial[0]+=1;path='/invented/%d'%serial[0];data[path]=raw;return dict(path=path,pin=a.pin(raw),mode=0o400)
    source={k:dict(P)for k in a.SOURCES};gate=dict(study=a.STUDY,source_pins=dict(operator=P,native=P,reference=P,processor=P,protocol=P),input_pins={})
    schema=dict(dev=list(range(22)));models={};initials=[]
    for seed,arm in a.PAIRS:
        parameters=dict(weight=[1.,2.]);order=[[j%65 for j in range(8)]for _ in range(300)]
        initial=dict(status='initial',study=a.STUDY,seed=seed,arm=arm,update=0,parameters=parameters,schema_sha256=a.sha(a.plain(schema)),packet_sha256=H,source_pins=source,prior_sha256=H)
        models[str(seed)+':'+arm]=dict(initial=parameters,initial_receipt=dict(status='durable',sha256=a.sha(a.plain(initial))),prior_sha256=H,probe={'masks':[1]},order=order);initials.append(initial)
    admission=dict(status='admitted',study=a.STUDY,packet_sha256=H,source_pins=source,schema=schema,models=models,order=[list(p)for p in a.PAIRS])
    adsha=a.sha(a.plain(admission));values=[admission];extras=[{'initial_%02d.json'%j:v for j,v in enumerate(initials)}]
    for index,(seed,arm)in enumerate(a.PAIRS):
        entry=models[str(seed)+':'+arm];history=[dict(update=j+1,loss=.5,gradient_norm=.1,ordinals=entry['order'][j])for j in range(300)]
        cp=dict(status='final',study=a.STUDY,seed=seed,arm=arm,update=300,history=history,admission_sha256=adsha,packet_sha256=H,source_pins=source,prior_sha256=H,initial_sha256=a.sha(a.plain(entry['initial'])),order_sha256=a.sha(a.plain(entry['order'])),parameters={'weight':[3.,4.]},optimizer={'state':[1.]},current={'update':300},final_probe={'masks':[1]})
        begin=dict(cp,status='initial',update=0,history=[],optimizer={},parameters=entry['initial']);begin.pop('final_probe');latest=dict(cp,status='partial');latest.pop('final_probe')
        fitextra={'begin_fit.json':begin,'latest_update.json':latest}
        for j in range(300):fitextra['update_%03d.json'%(j+1)]=dict(update=j+1,checkpoint_pin=a.pin(a.plain(latest))if j==299 else dict(P),history_last=history[j])
        preds=[dict(seed=seed,arm=arm,status='complete',ordinal=j//3,horizon=(1,3,5)[j%3],value=j)for j in range(66)]
        score=dict(status='complete',study=a.STUDY,seed=seed,arm=arm,predictions=preds,admission_sha256=adsha,packet_sha256=H,checkpoint_sha256=a.sha(a.plain(cp)),source_pins=source,no_optimizer=True)
        values.extend([cp,score]);extras.extend([fitextra,{'forecast_%02d.json'%j:v for j,v in enumerate(preds)}])
    values.append(dict(status='complete',pass_all=False));extras.append({})
    old=dict(schema='root-original-strong-comparison-input-v1',original_packet_pins=dict(archive=P,manifest=P),original_packet_sha256='2'*64,roster=[],fits=[])
    for seed in (20261012,20261013):
        for arm in ('B','F','H','T'):old['fits'].append(dict(seed=seed,arm=arm,predictions=[dict(ordinal=j,value=j)for j in range(66)],checkpoint_sha256=H,result_pin=P,independent_closure=dict(source_sha256=H,proof_pin=P)))
    native={k:put(b'fixture' if k=='feature_archive' else {})for k in ('feature_archive','feature_manifest','feature_authority')};stronger=dict(strong_results=put(old),strong_authority=put({}))
    gate['input_pins']={k:s['pin']for k,s in dict(native,**stronger).items()}
    def spec(g,i):return dict(index=i,unit='invented-%02d.service'%i)
    stages=[]
    for i,(value,extra)in enumerate(zip(values,extras)):
        files={name:put(v)for name,v in extra.items()};files['result.json']=put(value);s=spec(gate,i)
        req=dict(schema='marked-sixfit-stage-request-v1',gate=gate,gate_sha256=a.sha(a.plain(gate)),stage=s,authority={},previous={str(j):dict(name='stage_%02d/result.json'%j,pin=stages[j]['result.json']['pin'])for j in range(i)},dispatch_begin=0.)
        files['claim.json']=put(req);callbacks=[]
        if i==0:callbacks=[a.callback('initial','initial_%02d.json'%j,files['initial_%02d.json'%j]['pin'])for j in range(6)]+[a.callback('admission','result.json',files['result.json']['pin'])]
        elif i<13 and i%2:callbacks=[a.callback('begin_fit','begin_fit.json',files['begin_fit.json']['pin'])]+[a.callback('step','latest_update.json',extra['update_%03d.json'%j]['checkpoint_pin'])for j in range(1,301)]+[a.callback('final','result.json',files['result.json']['pin'])]
        elif i<13:callbacks=[a.callback('forecast','forecast_%02d.json'%j,files['forecast_%02d.json'%j]['pin'])for j in range(66)]+[a.callback('score_final','result.json',files['result.json']['pin'])]
        child=dict(schema='marked-sixfit-child-report-v1',index=i,gate_sha256=req['gate_sha256'],request_pin=files['claim.json']['pin'],status='complete',result_pin=files['result.json']['pin'],within_source=True,within_experiment=True,callbacks=callbacks,failure=None,exception_evidence_pin=None)
        files['child_report.json']=put(child);clip=dict(retained_hex='',original_pin=a.pin(b''),truncated=False)
        files['manager_return.json']=put(dict(code=0,timeout=False,streams_complete=True,stdout=clip,stderr=clip,exception=None));files['post.json']=put(dict(unit=s['unit'],result='success',active_state='inactive',control_group=''))
        closed=dict(schema='marked-sixfit-parent-return-v1',status='complete',index=i,unit=s['unit'],gate_sha256=req['gate_sha256'],cleanup_verified=True,report_pin=files['child_report.json']['pin'],result_pin=files['result.json']['pin'],errors=[],no_retry=True,scientific_pass=False if i==13 else None)
        files['closed.json']=put(closed);stages.append(files)
    def project(packet,envelope,p,packetsha):
        fits=[];origins=[]
        for f in envelope['fits']:
            c=f['independent_closure'];origin=dict(schema='old-model-new-comparison-join-v1',packet_sha256_semantics='comparison_population_only',old_model_reexecuted=False,original_packet_sha256=envelope['original_packet_sha256'],original_packet_pins=envelope['original_packet_pins'],original_result_pin=f['result_pin'],original_checkpoint_sha256=f['checkpoint_sha256'],original_source_sha256=c['source_sha256'],original_closure_proof_pin=c['proof_pin'],comparison_join_proof_pin=p)
            fits.append(dict(seed=f['seed'],arm=f['arm'],predictions=f['predictions'],closure=dict(verified=True,no_optimizer=True,checkpoint_sha256=f['checkpoint_sha256'],source_sha256=c['source_sha256'],packet_sha256=packetsha,independent_audit_sha256=c['proof_pin']['sha256'])));origins.append(origin)
        return dict(fits=fits,origins=origins)
    calls=[]
    def auth(scope,ctx,**kw):calls.append(scope);return dict(schema='root-marked-audit-input-authentication-v1',scope=scope,decision='authorized',proofs={k:dict(known_verified=True,sha256=H)for k in ('source','runtime','native','stronger','history_gradient','resources')})
    deps=a.Bindings(lambda s:data[s['path']],lambda raw,h:a.parse(raw),a.plain,lambda *args,**kw:{'fixture':True},lambda p:H,project,auth,spec,H)
    bundle=dict(schema='root-marked-audit-input-bundle-v1',binding_sha256=H,wrapper_binding_sha256=H,native=native,stronger=stronger,stages=stages,previous_audits=[],root_context={})
    if stage:
        base=a.prepare_inputs(0,bundle,deps,processing_begin=time.monotonic());common={k:base['inputs']['authority'][k]for k in ('packet_sha256','admission_sha256','source_pins','stronger_closure_sha256')}
        for j in range(stage):
            seed,arm=a.PAIRS[j];cp=values[2*j+1];score=values[2*j+2];authority=dict(schema='root-marked-sixfit-independent-authority-v1',verified=True,native_verified=True,optimizer_history_verified=True,gradient_probes_verified=True,stronger_verified=True,checkpoint_sha256=a.sha(a.plain(cp)),score_sha256=a.sha(a.plain(score)),**common)
            inputs=dict(packet={'fixture':True},admission=admission,checkpoint=cp,score=score,authority=authority);ish=a.sha(a.plain(inputs));claim=dict(schema='marked-sixfit-audit-wrapper-claim-v1',study=a.STUDY,stage=j,seed=seed,arm=arm,inputs_sha256=ish,binding_sha256=H,whole_begin=0.)
            report=dict(status='pass',checked=66,seed=seed,arm=arm,authority_sha256=a.sha(a.plain(authority)));cs=put(claim);rs=put(report)
            ret=dict(schema='marked-sixfit-audit-wrapper-return-v1',status='complete',stage=j,seed=seed,arm=arm,report_pin=rs['pin'],claim_sha256=cs['pin']['sha256'],input_sha256=ish,binding_sha256=H)
            bundle['previous_audits'].append({'claim':cs,'report':rs,'return':put(ret),'closed':put({'external_fixture_closure':True})})
    calls.clear();return bundle,deps,data,put,calls

class Tests(unittest.TestCase):
    def runfixture(self,stage=0):
        b,d,_,_,calls=fixture(stage);r=a.prepare_inputs(stage,b,d,processing_begin=time.monotonic());self.assertEqual(len(calls),1);return r
    def change(self,b,data,put,i,name,fn):
        v=a.parse(data[b['stages'][i][name]['path']]);fn(v);b['stages'][i][name]=put(v)
    def reject(self,i,name,fn,reason=None):
        b,d,data,put,calls=fixture();self.change(b,data,put,i,name,fn)
        with self.assertRaises(a.BindingError)as caught:a.prepare_inputs(0,b,d,processing_begin=time.monotonic())
        if reason:self.assertIn(reason,str(caught.exception))
        self.assertEqual(calls,[])
    def test_complete_fit(self):self.assertEqual(self.runfixture()['inputs']['score']['arm'],'S')
    def test_complete_aggregate(self):self.assertEqual(len(self.runfixture(6)['inputs']['fit_audits']),6)
    def test_prior_audits_fit_stage(self):self.assertEqual(len(self.runfixture(5)['previous']),5)
    def test_history_receipt(self):self.reject(1,'update_023.json',lambda v:v['history_last'].update(loss=.9),'history_receipt')
    def test_update_bool(self):self.reject(1,'update_001.json',lambda v:v.update(update=True),'integer')
    def test_forecast_substitution(self):self.reject(2,'forecast_23.json',lambda v:v.update(value=-1),'forecast_bytes')
    def test_truncated_manager(self):self.reject(3,'manager_return.json',lambda v:v['stdout'].update(truncated=True),'manager_stream')
    def test_manager_timeout(self):self.reject(3,'manager_return.json',lambda v:v.update(timeout=True),'manager_incomplete')
    def test_manager_false_code(self):self.reject(3,'manager_return.json',lambda v:v.update(code=False),'integer')
    def test_manager_stream_hash(self):self.reject(3,'manager_return.json',lambda v:v['stderr'].update(retained_hex='01'),'manager_stream_pin')
    def test_cleanup(self):self.reject(4,'post.json',lambda v:v.update(control_group='/invented'),'owned_cleanup')
    def test_failure_return(self):self.reject(4,'closed.json',lambda v:v.update(status='incomplete'),'closed_stage')
    def test_no_retry(self):self.reject(4,'closed.json',lambda v:v.update(no_retry=False),'closed_stage')
    def test_closed_pin(self):self.reject(4,'closed.json',lambda v:v.update(result_pin=P),'closed_pins')
    def test_unknown_member(self):
        b,d,data,put,calls=fixture();b['stages'][0]['late_or_failed.json']=put({})
        with self.assertRaises(a.BindingError):a.prepare_inputs(0,b,d,processing_begin=time.monotonic())
    def test_missing_history_member(self):
        b,d,*_=fixture();del b['stages'][1]['update_300.json']
        with self.assertRaises(a.BindingError):a.prepare_inputs(0,b,d,processing_begin=time.monotonic())
    def test_changed_bytes(self):
        b,d,data,*_=fixture();data[b['stages'][0]['initial_00.json']['path']]=b'{}'
        with self.assertRaisesRegex(a.BindingError,'read_pin'):a.prepare_inputs(0,b,d,processing_begin=time.monotonic())
    def test_writable_mode(self):
        b,d,*_=fixture();b['native']['feature_archive']['mode']=0o600
        with self.assertRaisesRegex(a.BindingError,'readonly_spec'):a.prepare_inputs(0,b,d,processing_begin=time.monotonic())
    def test_expired_source(self):
        b,d,*_=fixture()
        with self.assertRaisesRegex(a.BindingError,'source_deadline'):a.prepare_inputs(0,b,d,processing_begin=time.monotonic()-901)
    def test_boolean_stage(self):
        b,d,*_=fixture()
        with self.assertRaises(a.BindingError):a.prepare_inputs(True,b,d,processing_begin=time.monotonic())
    def test_external_rejection(self):
        b,d,*_=fixture();d=replace(d,authenticate=lambda *args,**kw:dict(schema='root-marked-audit-input-authentication-v1',scope=args[0],decision='denied',proofs={}))
        with self.assertRaisesRegex(a.BindingError,'external_authentication'):a.prepare_inputs(0,b,d,processing_begin=time.monotonic())
    def test_self_asserted_proof_rejected(self):
        b,d,*_=fixture();original=d.authenticate
        def auth(*args,**kw):
            r=original(*args,**kw);r['proofs']['history_gradient']['known_verified']=False;return r
        with self.assertRaisesRegex(a.BindingError,'known_root_proof'):a.prepare_inputs(0,b,replace(d,authenticate=auth),processing_begin=time.monotonic())
    def test_projection_cannot_change_predictions(self):
        b,d,*_=fixture();original=d.project_stronger
        def project(*args):r=original(*args);r=copy.deepcopy(r);r['fits'][0]['predictions'][0]['value']=-1;return r
        with self.assertRaisesRegex(a.BindingError,'strong_predictions_changed'):a.prepare_inputs(0,b,replace(d,project_stronger=project),processing_begin=time.monotonic())
    def test_full_report_not_join_proof(self):
        b,d,*_=fixture();original=d.project_stronger
        def project(*args):r=original(*args);r['fits'][0]['closure']['independent_audit_sha256']='3'*64;return r
        with self.assertRaisesRegex(a.BindingError,'strong_report_origin'):a.prepare_inputs(0,b,replace(d,project_stronger=project),processing_begin=time.monotonic())
    def test_latest_parameter_substitution(self):
        b,d,data,put,calls=fixture();files=b['stages'][1];v=a.parse(data[files['latest_update.json']['path']]);v['parameters']['weight'][0]=999.;files['latest_update.json']=put(v)
        u=a.parse(data[files['update_300.json']['path']]);u['checkpoint_pin']=files['latest_update.json']['pin'];files['update_300.json']=put(u)
        child=a.parse(data[files['child_report.json']['path']]);child['callbacks'][-2]['pin']=files['latest_update.json']['pin'];files['child_report.json']=put(child)
        closed=a.parse(data[files['closed.json']['path']]);closed['report_pin']=files['child_report.json']['pin'];files['closed.json']=put(closed)
        with self.assertRaisesRegex(a.BindingError,'latest_final_parameters'):a.prepare_inputs(0,b,d,processing_begin=time.monotonic())
    def test_previous_binding_substitution(self):
        b,d,data,put,calls=fixture(1);files=b['previous_audits'][0];r=a.parse(data[files['return']['path']]);r['binding_sha256']='3'*64;files['return']=put(r)
        with self.assertRaisesRegex(a.BindingError,'previous_audit_return'):a.prepare_inputs(1,b,d,processing_begin=time.monotonic())
    def test_previous_authority_substitution(self):
        b,d,data,put,calls=fixture(1);files=b['previous_audits'][0];v=a.parse(data[files['report']['path']]);v['authority_sha256']='3'*64;files['report']=put(v)
        r=a.parse(data[files['return']['path']]);r['report_pin']=files['report']['pin'];files['return']=put(r)
        with self.assertRaisesRegex(a.BindingError,'previous_authority_inputs_binding'):a.prepare_inputs(1,b,d,processing_begin=time.monotonic())
    def test_wrong_native_packet(self):
        b,d,*_=fixture()
        with self.assertRaisesRegex(a.BindingError,'native_packet_binding'):a.prepare_inputs(0,b,replace(d,packet_sha=lambda p:'3'*64),processing_begin=time.monotonic())
    def test_manager_exception(self):self.reject(3,'manager_return.json',lambda v:v.update(exception='transport_uncertain'),'manager_incomplete')
    def test_duplicate_json(self):
        with self.assertRaisesRegex(a.BindingError,'duplicate_key'):a.parse(b'{"a":1,"a":2}')
    def test_nonfinite_json(self):
        with self.assertRaises(a.BindingError):a.parse(b'{"a":NaN}')
    def test_noncanonical_json(self):
        with self.assertRaisesRegex(a.BindingError,'canonical_json'):a.parse(b'{"a": 1}')

if __name__=='__main__':unittest.main()
