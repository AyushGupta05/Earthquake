"""Invented records/clock/authority only; no actual data or provider requests."""
import copy,importlib.util,io,json,math,sys,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import numpy as np
import obspy
from obspy import Stream,Trace,UTCDateTime
ROOT=Path(__file__).resolve().parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
q=load('qualification');c=load('core');h=load('child_harness');s=load('supervisor');v2=load('qualification_v2_reference');v4=load('qualification_v4_reference')
T0=UTCDateTime('2020-01-02T00:00:00Z')

def flat(index=3,k='Z'):
    return {'slot_index':index,'body_path':'/invented/body'+str(index)+k,'body_sha256':'1'*64,'body_bytes':4096,
            'expected_nslc':{'network':'NZ','station':'AAA','location':'10','channel':'HH'+k},
            'transport_status':'prior_vertical_qualified' if k=='Z' else 'unqualified_http404' if k in q.PRIOR_COMPONENTS else 'qualified_http200',
            't0_ns':T0.ns,'pick_ns':T0.ns,'filename_year':2020,'filename_doy':2}

def parent_slot(index=3):
    p={k:flat(index)[k] for k in ('slot_index','t0_ns','pick_ns','filename_year','filename_doy')}
    for group,keys in (('components',q.COMPONENTS),('prior_failures',q.PRIOR_COMPONENTS)):
        p[group]={k:{f:flat(index,k)[f] for f in ('body_path','body_sha256','body_bytes','expected_nslc','transport_status')} for k in keys}
    return p

def prior_failures(index=3):return {k:q.failed(index,'transport_unqualified','unqualified_http404') for k in q.PRIOR_COMPONENTS}
def trace(k='Z',start=-3,n=801,rate=100.,**changes):
    header={'network':'NZ','station':'AAA','location':'10','channel':'HH'+k,'starttime':T0+start,'sampling_rate':rate};header.update(changes)
    return Trace(np.arange(n,dtype=np.int32),header)
def encoded(traces,encoding='INT32'):
    body=io.BytesIO();Stream(traces).write(body,format='MSEED',encoding=encoding,reclen=512);return body.getvalue()
def component(k,stream=None,index=3):
    st=Stream([trace(k)]) if stream is None else stream;row=q.analyze(st,flat(index,k),c)
    row.update(advertised_samples=sum(t.stats.npts for t in st),decode_warning_count=0);return row
def analyzed_slot(index=3,streams=None):return q.make_slot(parent_slot(index),{k:component(k,(streams or {}).get(k),index) for k in q.COMPONENTS},c,prior_failures(index))
def prereqs():return {**h.PREREQUISITE_IDS,**{k:'3'*64 for k in h.PREREQUISITE_PINS},'terminal_accounting':dict(h.TERMINAL_ACCOUNTING)}
def envelope(row):
    sources={n:h.digest((ROOT/n).read_bytes()) for n in h.SOURCE_NAMES};index=row['slot_index']
    masks=[{'slot_index':index,'components':{k:row['components'][k]['transport_status'] for k in q.COMPONENTS},'prior_failures':{k:row['prior_failures'][k]['transport_status'] for k in q.PRIOR_COMPONENTS}}]
    mask=h.digest(json.dumps(masks,sort_keys=True,separators=(',',':')).encode())
    result={'protocol_id':h.PROTOCOL,'private':{'slots':[copy.deepcopy(row)],'provenance':{'plan_sha256':'1'*64,'authorization_sha256':'2'*64,'source_files':sources,'pushed_source_commit':'a'*40,'original_slot_index':index,'validated_body_count':5,'advertised_samples_decoded':sum(o.get('advertised_samples',0) for o in row['components'].values()),'precontext_s':3,'prerequisites':prereqs(),'transport_statuses_sha256':mask}},'public_aggregate':q.aggregate([row])}
    receipt={'plan_sha256':'1'*64,'authorization_sha256':'2'*64,'adapter_sha256':sources['child_harness.py'],'supervisor_sha256':sources['supervisor.py'],'transport_statuses_sha256':mask};return result,receipt

class GridTests(unittest.TestCase):
    def test_fixed_cells_preserve_all_four_possible_original_indices(self):
        for index in range(4):
            row=analyzed_slot(index);s.validate_result(*envelope(row));self.assertEqual(row['slot_index'],index)
            self.assertEqual(sum(len(o['windows']) for o in row['components'].values()),9);self.assertEqual(len(row['joint_windows']),3);self.assertEqual(sum(len(o['windows']) for o in row['prior_failures'].values()),6)
            for k in q.COMPONENTS:self.assertEqual([row['components'][k]['windows'][str(v)]['core']['samples'] for v in q.HORIZONS],[400,600,800])
            for group in q.aggregate([row])['prior_failure_window_states'].values():
                for v in group.values():self.assertEqual(v,{'denominator':1,'available':0,'incomplete':0,'unknown':1,'complete_and_catalogue_pick_before_deadline':0})
    def test_z_parity_both_frozen_references_with_real_records(self):
        poison=trace();poison.data=poison.data.astype(float);poison.data[450]=np.nan
        cases=[Stream([trace()]),Stream([trace(start=-2.99)]),Stream([trace(n=799)]),Stream([poison]),Stream(),Stream([trace(),trace(k='E')]),Stream([trace(n=300),trace(start=0,n=1001,rate=200)])]
        cases += [Stream([trace(n=300),trace(start=x,n=501)]) for x in (.01,-.01,.005)]
        for k in q.COMPONENTS:
            st,n,_=q.decode(encoded([trace(k)]),obspy.read,q.TOTAL_SAMPLE_CAP);self.assertEqual(n,801);self.assertEqual(st[0].stats.channel,'HH'+k)
            if k=='Z':cases.append(st)
        for st in cases:
            new=q.analyze(st,flat(),c);self.assertEqual(json.dumps(new,sort_keys=True),json.dumps(v4.analyze(st,flat(),c),sort_keys=True))
            old=v2.analyze(st,flat(),c)['precontext_windows']['3']
            if not new['literal_identity_matches'] or not new['observed_rate_consistent']:
                for w in old.values():w['core']['available']=None
            self.assertEqual(json.dumps(old,sort_keys=True),json.dumps(new['windows'],sort_keys=True))
    def test_cross_rate_phase_gap_overlap_edge_and_rational_geometry(self):
        for tr,reason in ((trace('1',n=1601,rate=200),'mixed_component_rates'),(trace('1',start=-2.995),'common_lattice_mismatch')):
            row=analyzed_slot(streams={'1':Stream([tr])});self.assertEqual(row['joint_windows']['5']['reason'],reason);s.validate_result(*envelope(row))
        row=analyzed_slot(streams={k:Stream([trace(k,n=961,rate=120)]) for k in q.COMPONENTS});self.assertTrue(row['joint_windows']['5']['available']);s.validate_result(*envelope(row))
        for st in [Stream([trace('2',n=300),trace('2',start=x,n=501)]) for x in (.01,-.01,.005)]+[Stream([trace('2',start=-2.99)]),Stream([trace('2',n=799)])]:
            row=analyzed_slot(streams={'2':st});self.assertFalse(row['joint_windows']['5']['available']);s.validate_result(*envelope(row))
    def test_wrong_literal_identity_mixed_rates_no_cardinal_rename(self):
        for field,value in (('network','XX'),('station','BBB'),('location',''),('channel','HHE'),('channel','HHN')):
            row=analyzed_slot(streams={'1':Stream([trace('1',**{field:value})])});self.assertTrue(all(w['available'] is None for w in row['joint_windows'].values()));s.validate_result(*envelope(row))
        row=analyzed_slot(streams={'1':Stream([trace('1',n=300),trace('1',start=0,n=1001,rate=200)])});self.assertEqual(row['joint_windows']['5']['reason'],'component_unknown');s.validate_result(*envelope(row))
    def test_future_amplitude_poison_at_each_exact_half_open_deadline(self):
        for horizon in q.HORIZONS:
            clean=analyzed_slot();changes={}
            for k in q.COMPONENTS:
                tr=trace(k,n=1001);tr.data=tr.data.astype(float);tr.data[(3+horizon)*100:]=np.nan;changes[k]=Stream([tr])
            changed=analyzed_slot(streams=changes)
            for k in q.COMPONENTS:self.assertEqual(clean['components'][k]['windows'][str(horizon)],changed['components'][k]['windows'][str(horizon)])
            self.assertEqual(clean['joint_windows'][str(horizon)],changed['joint_windows'][str(horizon)])
    def test_known_false_precedence_but_no_pair_rate_inference_with_unknown(self):
        p=parent_slot();comps={k:component(k) for k in q.COMPONENTS};comps['1']=q.failed(3,'decode_or_grid_unsupported','qualified_http200');comps['2']=component('2',Stream([trace('2',n=1601,rate=200)]))
        row=q.make_slot(p,comps,c,prior_failures());self.assertTrue(all(w['available'] is None for w in row['joint_windows'].values()));s.validate_result(*envelope(row))
        comps['2']=component('2',Stream([trace('2',start=-2)]));row=q.make_slot(p,comps,c,prior_failures());self.assertTrue(all(w['available'] is False for w in row['joint_windows'].values()));s.validate_result(*envelope(row))
    def test_signed_pick_offsets_strict_equality_and_clock_ranges(self):
        for offset in (-1,1,5):
            p=parent_slot();p['pick_ns']=p['t0_ns']+offset*c.NS;comps={k:q.failed(3,'decode_or_grid_unsupported','prior_vertical_qualified' if k=='Z' else 'qualified_http200') for k in q.COMPONENTS};row=q.make_slot(p,comps,c,prior_failures());self.assertEqual(row['catalogue_pick_before_deadline'],{str(v):offset<v for v in q.HORIZONS});s.validate_result(*envelope(row))
        for stamp in (0,-2**63+10**10,2**63-10**10-1,-2**63,2**63):
            p=parent_slot();p.update(t0_ns=stamp,pick_ns=stamp);row=q.make_slot(p,comps,c,prior_failures())
            if stamp in (-2**63,2**63):
                with self.assertRaises(ValueError):s.validate_result(*envelope(row))
            else:s.validate_result(*envelope(row))
    def test_flat_extreme_day_crossing_and_public_privacy_no_physical_claim(self):
        changes={k:Stream([trace(k)]) for k in q.COMPONENTS}
        for st in changes.values():st[0].data[:]=2
        row=analyzed_slot(streams=changes);self.assertTrue(row['joint_windows']['5']['available']);self.assertTrue(row['components']['Z']['windows']['5']['core']['clipping_candidate']);s.validate_result(*envelope(row))
        row['private_sentinel']='PRIVATE_SENTINEL';agg=q.aggregate([row]);self.assertTrue(all(v is False for k,v in agg.items() if k.endswith('_verified')))
        for token in ('PRIVATE_SENTINEL','AAA','HHZ','slot_index','t0_ns','body_path','157'):self.assertNotIn(token,json.dumps(agg))
    def test_selected_crop_trace_counter_and_joint_tampering(self):
        result,receipt=envelope(analyzed_slot())
        for k in q.COMPONENTS:
            for hor in ('1','3','5'):
                for field,value in (('left_ns',0),('deadline_ns',True),('target_pick_strictly_before_deadline',1)):
                    bad=copy.deepcopy(result);bad['private']['slots'][0]['components'][k]['windows'][hor][field]=value
                    with self.assertRaises(ValueError):s.validate_result(bad,receipt)
                for field,value in (('samples',1),('finite',False),('first_sample_ns_denominator',2),('gaps',1)):
                    bad=copy.deepcopy(result);bad['private']['slots'][0]['components'][k]['windows'][hor]['core'][field]=value
                    with self.assertRaises(ValueError):s.validate_result(bad,receipt)
        for mutate in (lambda o:o['decoded_traces'][0].update(npts=800),lambda o:o['decoded_traces'][0].update(last_sample_ns=None),lambda o:o['decoded_traces'][0]['nslc'].__setitem__(3,'HHN'),lambda o:o['observed_nslc'][0].update(decoded_trace_count=1.0),lambda o:o.update(decoded_sample_grid={})):
            bad=copy.deepcopy(result);mutate(bad['private']['slots'][0]['components']['1'])
            with self.assertRaises(ValueError):s.validate_result(bad,receipt)
        for field,value in (('mask','unknown'),('available',1),('common_observed_rate',{'numerator':200,'denominator':2}),('lattices_compatible',None)):
            bad=copy.deepcopy(result);bad['private']['slots'][0]['joint_windows']['1'][field]=value
            with self.assertRaises(ValueError):s.validate_result(bad,receipt)
    def test_prior_unknown_cells_cannot_be_decoded_repaired_or_removed(self):
        result,receipt=envelope(analyzed_slot())
        for k in q.PRIOR_COMPONENTS:
            for change in (lambda o:o.update(status='decoded'),lambda o:o.update(reason='decode_or_grid_unsupported'),lambda o:o.update(transport_status='qualified_http200'),lambda o:o['windows']['1']['core'].update(available=False),lambda o:o['windows'].pop('3'),lambda o:o.update(slot_index=0)):
                bad=copy.deepcopy(result);change(bad['private']['slots'][0]['prior_failures'][k])
                with self.assertRaises(ValueError):s.validate_result(bad,receipt)
    def test_provenance_index_mask_counts_and_public_forgery(self):
        result,receipt=envelope(analyzed_slot())
        mutations=[lambda r:r['private']['slots'][0].update(slot_index=True),lambda r:r['private']['provenance'].update(original_slot_index=0),lambda r:r['private']['provenance'].update(validated_body_count=5.0),lambda r:r['private']['provenance'].update(advertised_samples_decoded=0),lambda r:r['public_aggregate'].update(novelty_verified=True),lambda r:r['public_aggregate'].update(PRIVATE_SENTINEL='AAA'),lambda r:r['public_aggregate']['prior_failure_window_states']['E']['1'].update(unknown=True)]
        for change in mutations:
            bad=copy.deepcopy(result);change(bad)
            with self.assertRaises(ValueError):s.validate_result(bad,receipt)
        bad=copy.deepcopy(result);row=bad['private']['slots'][0];row['slot_index']=0
        for o in list(row['components'].values())+list(row['prior_failures'].values()):o['slot_index']=0
        bad['private']['provenance']['original_slot_index']=0
        with self.assertRaisesRegex(ValueError,'transport mask'):s.validate_result(bad,receipt)

class DecodeTests(unittest.TestCase):
    def test_real_float_nan_deadline_and_record_coalescence(self):
        tr=trace();tr.data=tr.data.astype(np.float64);tr.data[400]=np.nan;st,_,_=q.decode(encoded([tr],'FLOAT64'),obspy.read,q.TOTAL_SAMPLE_CAP);row=q.analyze(st,flat(),c);self.assertTrue(row['windows']['1']['core']['available']);self.assertFalse(row['windows']['3']['core']['available'])
        st,n,_=q.decode(encoded([trace(n=300)])+encoded([trace(start=.005,n=500)]),obspy.read,q.TOTAL_SAMPLE_CAP);self.assertEqual((len(st),n),(1,800));self.assertTrue(q.analyze(st,flat(),c)['windows']['5']['core']['available']);self.assertFalse(q.analyze(Stream([trace(n=300),trace(start=.005,n=500)]),flat(),c)['windows']['5']['core']['available'])
    def test_advertised_caps_stop_before_full_decode(self):
        for count in (-1,True,1.0,math.nan,q.OBJECT_SAMPLE_CAP+1):
            calls=[]
            def reader(*a,**kw):calls.append(kw);return [types.SimpleNamespace(stats=types.SimpleNamespace(npts=count))]
            with self.assertRaises(ValueError):q.decode(b'invented',reader,q.TOTAL_SAMPLE_CAP)
            self.assertEqual(len(calls),1)
        self.assertEqual(q.TOTAL_SAMPLE_CAP,48_000_000)
        with self.assertRaises(ValueError):q.decode(encoded([trace()]),obspy.read,800)
    def test_header_full_dtype_signature_and_warning_privacy(self):
        headers=Stream([trace()]);full=headers.copy();full[0].data=full[0].data[:-1]
        with self.assertRaises(ValueError):q.decode(b'invented',lambda *a,**kw:headers if kw.get('headonly') else full,1000)
        for field,value in (('sampling_rate',200.),('station','BBB'),('starttime',T0)):
            full=headers.copy();setattr(full[0].stats,field,value)
            with self.assertRaises(ValueError):q.decode(b'invented',lambda *a,**kw:headers if kw.get('headonly') else full,1000)
        full=headers.copy();full[0].data=full[0].data.astype(np.uint32)
        with self.assertRaises(ValueError):q.decode(b'invented',lambda *a,**kw:headers if kw.get('headonly') else full,1000)
        import warnings
        def reader(*a,**kw):warnings.warn('PRIVATE_SENTINEL');return headers
        self.assertEqual(q.decode(b'invented',reader,1000)[2],2)

class GateTests(unittest.TestCase):
    def fixture(self,directory,index=3):
        root=Path(directory).resolve();sources={n:h.digest((ROOT/n).read_bytes()) for n in h.SOURCE_NAMES};p=parent_slot(index)
        for group,keys in (('components',q.COMPONENTS),('prior_failures',q.PRIOR_COMPONENTS)):
            for k in keys:
                body=b'HTTP404_PRIVATE_SENTINEL'+k.encode() if k in q.PRIOR_COMPONENTS else encoded([trace(k)]);path=root/('invented'+str(index)+k+'.body');path.write_bytes(body);p[group][k].update(body_path=str(path),body_sha256=h.digest(body),body_bytes=len(body))
        plan={'protocol_id':h.PROTOCOL,'precontext_s':3,'prerequisites':prereqs(),'transport_statuses_sha256':h.status_digest([p]),'limits':h.LIMITS,'source_files':sources,'slots':[p]};pp=root/'invented_plan.json';pp.write_text(json.dumps(plan));ph=h.digest(pp.read_bytes())
        auth={'protocol_id':h.PROTOCOL,'precontext_s':3,'prerequisites':prereqs(),'limits':h.LIMITS,'source_files':sources,'plan_sha256':ph,'offline_decode_authorized':True,'code_only_review_clean':True,'focused_tests_passed':True,**{k:True for k in h.AUTH_ASSERTIONS},'transport_statuses_sha256':h.status_digest([p]),'pushed_source_commit':'a'*40,'source_manifest_sha256':'1'*64,'review_receipt_sha256':'2'*64,'test_receipt_sha256':'3'*64};ap=root/'invented_auth.json';ap.write_text(json.dumps(auth));runtime=str(Path(sys.executable).absolute())
        return types.SimpleNamespace(plan=str(pp),authorization=str(ap),plan_sha256=ph,authorization_sha256=h.digest(ap.read_bytes()),adapter_sha256=sources['child_harness.py'],supervisor_sha256=sources['supervisor.py'],runtime_path=runtime,runtime_sha256=h.digest(Path(runtime).resolve().read_bytes()),transport_statuses_sha256=h.status_digest([p]),deadline=time.monotonic()+120)
    def update(self,args,plan=None,auth=None):
        if plan is not None:
            Path(args.plan).write_text(json.dumps(plan));args.plan_sha256=h.digest(Path(args.plan).read_bytes())
            if auth is None:auth=json.loads(Path(args.authorization).read_bytes())
            auth['plan_sha256']=args.plan_sha256
        if auth is not None:Path(args.authorization).write_text(json.dumps(auth));args.authorization_sha256=h.digest(Path(args.authorization).read_bytes())
    def receipt(self,args):return {'plan_sha256':args.plan_sha256,'authorization_sha256':args.authorization_sha256,'adapter_sha256':args.adapter_sha256,'supervisor_sha256':args.supervisor_sha256,'transport_statuses_sha256':args.transport_statuses_sha256}
    def test_real_source_invented_five_body_supervised_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);r=s.supervise(runtime=args.runtime_path,runtime_sha256=args.runtime_sha256,child=str(ROOT/'child_harness.py'),child_sha256=args.adapter_sha256,supervisor_sha256=args.supervisor_sha256,plan=args.plan,plan_sha256=args.plan_sha256,authorization=args.authorization,authorization_sha256=args.authorization_sha256,transport_statuses_sha256=args.transport_statuses_sha256,out_dir=str(Path(directory).resolve()/'exclusive_output'));self.assertTrue(r['complete'],r)
            result=json.loads((Path(directory)/'exclusive_output/private_result.json').read_bytes());self.assertEqual(result['private']['provenance']['validated_body_count'],5);self.assertEqual(result['private']['provenance']['original_slot_index'],3)
    def test_five_hashes_before_decoder_error_sentinels_never_decoded(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);p=json.loads(Path(args.plan).read_bytes());paths={o['body_path'] for group in ('components','prior_failures') for o in p['slots'][0][group].values()};checked=set();seen=[];original=h.bounded_read
            def bounded(path,*a):
                b=original(path,*a)
                if path in paths:checked.add(path)
                return b
            def reader(*a,**kw):self.assertEqual(checked,paths);self.assertNotIn(b'HTTP404_PRIVATE_SENTINEL',a[0].getvalue());seen.append(kw.get('headonly',False));return obspy.read(*a,**kw)
            with patch.object(h,'bounded_read',side_effect=bounded),patch.object(h,'verify_runtime',return_value=reader):result=h.run(args)
            self.assertEqual((len(seen),sum(seen)),(6,3));s.validate_result(result,self.receipt(args))
    def test_corrupt_last_error_and_between_pass_eligible_cause_zero_decodes(self):
        for mode in ('error','eligible'):
            with tempfile.TemporaryDirectory() as directory:
                args=self.fixture(directory);p=json.loads(Path(args.plan).read_bytes());reader=Mock();original=h.bounded_read
                if mode=='error':Path(p['slots'][0]['prior_failures']['N']['body_path']).write_bytes(b'changed error')
                target=p['slots'][0]['components']['1']['body_path'];counts={}
                def bounded(path,*a):
                    counts[path]=counts.get(path,0)+1
                    if mode=='eligible' and path==target and counts[path]==2:Path(path).write_bytes(b'changed eligible')
                    return original(path,*a)
                with patch.object(h,'bounded_read',side_effect=bounded),patch.object(h,'verify_runtime',return_value=reader),self.assertRaises(ValueError):h.run(args)
                reader.assert_not_called()
    def test_unsupported_selected_retains_unknown_cells_and_all_prior_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);p=json.loads(Path(args.plan).read_bytes());o=p['slots'][0]['components']['1'];body=b'invented bad mseed';Path(o['body_path']).write_bytes(body);o.update(body_sha256=h.digest(body),body_bytes=len(body));self.update(args,plan=p)
            with patch.object(h,'verify_runtime',return_value=obspy.read):result=h.run(args)
            self.assertEqual(result['public_aggregate']['failed_objects'],3);self.assertEqual(result['public_aggregate']['joint_window_states']['1']['unknown'],1);s.validate_result(result,self.receipt(args))
    def test_paths_index_nslc_dates_duplicates_and_caps_precede_runtime(self):
        changes=[lambda p:p['slots'][0].update(slot_index=True),lambda p:p['slots'][0].update(slot_index=4),lambda p:p['slots'][0].update(t0_ns=None),lambda p:p['slots'][0].update(filename_year=2021,filename_doy=366),lambda p:p['slots'][0]['prior_failures']['N'].update(body_path='relative'),lambda p:p['slots'][0]['components']['1']['expected_nslc'].update(channel='HHE'),lambda p:p['slots'][0]['components']['2']['expected_nslc'].update(station='BBB'),lambda p:p['slots'][0]['components']['1'].update(body_bytes=h.BODY_CAP+1),lambda p:p['slots'][0]['prior_failures']['N'].update(body_path=p['slots'][0]['prior_failures']['E']['body_path'])]
        for change in changes:
            with tempfile.TemporaryDirectory() as directory:
                args=self.fixture(directory);p=json.loads(Path(args.plan).read_bytes());change(p);self.update(args,plan=p)
                with patch.object(h,'verify_runtime',side_effect=AssertionError('no science before validation')),self.assertRaises(ValueError):h.run(args)
    def test_trusted_index_status_digest_stops_equal_count_relabel(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);p=json.loads(Path(args.plan).read_bytes());p['slots'][0]['slot_index']=0;p['transport_statuses_sha256']=h.status_digest(p['slots']);a=json.loads(Path(args.authorization).read_bytes());a['transport_statuses_sha256']=p['transport_statuses_sha256'];self.update(args,plan=p,auth=a)
            with patch.object(h,'verify_runtime',side_effect=AssertionError('no science')),self.assertRaises(ValueError):h.run(args)
    def test_every_plan_auth_limit_and_prerequisite_counter_rejects_float(self):
        for subject in ('plan','authorization'):
            for group,values in (('limits',h.LIMITS),('terminal_accounting',h.TERMINAL_ACCOUNTING)):
                for key,value in values.items():
                    with tempfile.TemporaryDirectory() as directory:
                        args=self.fixture(directory);o=json.loads(Path(getattr(args,subject)).read_bytes());target=o['limits'] if group=='limits' else o['prerequisites']['terminal_accounting'];target[key]=float(value);self.update(args,**{subject if subject=='plan' else 'auth':o})
                        with self.assertRaises(ValueError):h.validate_gate(args)
    def test_parent_assertions_prerequisite_pins_and_context_types_strict(self):
        for key in h.AUTH_ASSERTIONS+('offline_decode_authorized','code_only_review_clean','focused_tests_passed'):
            for bad in (False,1):
                with tempfile.TemporaryDirectory() as directory:
                    args=self.fixture(directory);a=json.loads(Path(args.authorization).read_bytes());a[key]=bad;self.update(args,auth=a)
                    with self.assertRaises(ValueError):h.validate_gate(args)
        for key in h.PREREQUISITE_PINS:
            p=prereqs();p[key]='bad'
            with self.assertRaises(ValueError):h.validate_prerequisites(p)
        for value in (True,3.0,5):
            with tempfile.TemporaryDirectory() as directory:
                args=self.fixture(directory);p=json.loads(Path(args.plan).read_bytes());p['precontext_s']=value;self.update(args,plan=p)
                with self.assertRaises(ValueError):h.validate_gate(args)
    def test_exact_statuses_and_core_source_gate(self):
        for group,k,status in (('components','1','unqualified_http404'),('components','Z','qualified_http200'),('prior_failures','E','qualified_http200')):
            with tempfile.TemporaryDirectory() as directory:
                args=self.fixture(directory);p=json.loads(Path(args.plan).read_bytes());p['slots'][0][group][k]['transport_status']=status;self.update(args,plan=p)
                with self.assertRaises(ValueError):h.validate_gate(args)
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);p=json.loads(Path(args.plan).read_bytes());p['source_files']['core.py']='0'*64;a=json.loads(Path(args.authorization).read_bytes());a['source_files']=p['source_files'];self.update(args,plan=p,auth=a)
            with self.assertRaises(ValueError):h.validate_gate(args)
    def test_memory_timeout_body_and_output_control_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory)
            for error in (MemoryError('invented'),TimeoutError('invented')):
                with patch.object(h,'verify_runtime',return_value=obspy.read),patch.object(q,'decode',side_effect=error),patch.object(h,'load_verified',side_effect=lambda name,body:q if name=='qualification' else c),self.assertRaises(type(error)):h.run(args)
        with self.assertRaises(TimeoutError):h.bounded_read('/invented/no_read',64,time.monotonic()-1)
        with self.assertRaises(ValueError):h.bounded_result({'invented':'x'*h.OUTPUT_CAP})
if __name__=='__main__':unittest.main()
