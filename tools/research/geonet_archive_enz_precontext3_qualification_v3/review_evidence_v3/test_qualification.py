"""Invented stream/miniSEED/plan fixtures only, never cached earthquake objects."""
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import numpy as np
import obspy
from obspy import Stream,Trace,UTCDateTime

ROOT=Path(__file__).resolve().parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
q=load('qualification');c=load('core');h=load('child_harness');s=load('supervisor');v2=load('qualification_v2_reference')
T0=UTCDateTime('2020-01-02T00:00:00Z')

def flat_slot(index=0,suffix='Z'):
    return {'slot_index':index,'body_path':'/invented/body'+str(index)+suffix,'body_sha256':'1'*64,'body_bytes':4096,
        'expected_nslc':{'network':'NZ','station':'AAA','location':'10','channel':'HH'+suffix},
        't0_ns':T0.ns,'pick_ns':T0.ns,'filename_year':2020,'filename_doy':2}

def parent_slot(index=0):
    p={k:flat_slot(index)[k] for k in ('slot_index','t0_ns','pick_ns','filename_year','filename_doy')}
    p['components']={k:{f:flat_slot(index,k)[f] for f in ('body_path','body_sha256','body_bytes','expected_nslc')} for k in q.COMPONENTS}
    return p

def trace(start=-3,n=801,rate=100.,suffix='Z',**changes):
    header={'network':'NZ','station':'AAA','location':'10','channel':'HH'+suffix,'starttime':T0+start,'sampling_rate':rate}
    header.update(changes);return Trace(data=np.arange(n,dtype=np.int32),header=header)

def encoded(traces):
    b=io.BytesIO();Stream(traces).write(b,format='MSEED',encoding='INT32',reclen=512);return b.getvalue()

def analyzed_component(index,suffix,stream=None):
    row=q.analyze(Stream([trace(suffix=suffix)]) if stream is None else stream,flat_slot(index,suffix),c)
    row.update(advertised_samples=sum(t.stats.npts for t in (Stream([trace(suffix=suffix)]) if stream is None else stream)),decode_warning_count=0)
    return row

def analyzed_slot(index=0,**streams):
    components={k:analyzed_component(index,k,streams.get(k)) for k in q.COMPONENTS}
    return q.make_slot(parent_slot(index),components,c)

def prereqs():
    return {**h.PREREQUISITE_IDS,**{k:'3'*64 for k in h.PREREQUISITE_PINS}}

def envelope(rows):
    sources={name:h.digest((ROOT/name).read_bytes()) for name in h.SOURCE_NAMES}
    result={'protocol_id':h.PROTOCOL,'private':{'slots':rows,'provenance':{
        'plan_sha256':'1'*64,'authorization_sha256':'2'*64,'source_files':sources,'pushed_source_commit':'a'*40,
        'validated_body_count':12,'advertised_samples_decoded':sum(o.get('advertised_samples',0) for r in rows for o in r['components'].values()),
        'precontext_s':3,'prerequisites':prereqs()}},'public_aggregate':q.aggregate(rows)}
    receipt={'plan_sha256':'1'*64,'authorization_sha256':'2'*64,'adapter_sha256':sources['child_harness.py'],'supervisor_sha256':sources['supervisor.py']}
    return result,receipt

class GridTests(unittest.TestCase):
    def test_36_component_12_joint_cells_all_denominators(self):
        rows=[analyzed_slot(i) for i in range(4)];result,receipt=envelope(rows);s.validate_result(result,receipt)
        self.assertEqual(sum(len(o['windows']) for r in rows for o in r['components'].values()),36)
        self.assertEqual(sum(len(r['joint_windows']) for r in rows),12)
        for row in rows:
            for k in q.COMPONENTS:
                self.assertEqual([row['components'][k]['windows'][str(h)]['core']['samples'] for h in q.HORIZONS],[400,600,800])
            for h in q.HORIZONS:self.assertTrue(row['joint_windows'][str(h)]['available'])
        for counts in result['public_aggregate']['joint_window_states'].values():
            self.assertEqual(counts,{'denominator':4,'available':4,'incomplete':0,'unknown':0,'complete_and_catalogue_pick_before_deadline':4})

    def test_z_context3_canonical_v2_parity(self):
        self.assertEqual(h.digest((ROOT/'core.py').read_bytes()),h.CORE_SHA256)
        self.assertEqual(h.digest((ROOT/'qualification_v2_reference.py').read_bytes()),'92efdc4d8205fd4124522f4d72147e9e424d50648a819c83537206aa40f33a8f')
        poison=trace();poison.data=poison.data.astype(float);poison.data[450]=np.nan
        cases=[Stream([trace()]),Stream([trace(start=-2.99)]),Stream([trace(n=799)]),Stream([poison]),
            Stream([trace(n=300),trace(start=.01,n=501)]),Stream([trace(n=300),trace(start=-.01,n=501)]),
            Stream([trace(n=300),trace(start=.005,n=501)]),Stream([trace(),trace(suffix='E')]),
            Stream([trace(n=300),trace(start=0,n=1001,rate=200)]),Stream()]
        for st in cases:
            old=v2.analyze(st,flat_slot(),c);old['windows']=old['precontext_windows']['3']
            old={k:v for k,v in old.items() if k not in ('precontext_windows','precontext_masks')}
            new=q.analyze(st,flat_slot(),c);new={k:v for k,v in new.items() if k!='observed_sample_rate'}
            self.assertEqual(json.dumps(old,sort_keys=True),json.dumps(new,sort_keys=True))
        self.assertEqual(v2.failed(0,'invented')['precontext_windows']['3'],q.failed(0,'invented')['windows'])

    def test_half_period_phase_mismatch_despite_individually_complete(self):
        row=analyzed_slot(N=Stream([trace(start=-2.995,suffix='N')]))
        for o in row['components'].values():self.assertTrue(o['windows']['1']['core']['available'])
        for w in row['joint_windows'].values():
            self.assertFalse(w['available']);self.assertEqual(w['reason'],'common_lattice_mismatch')
        result,receipt=envelope([row]+[analyzed_slot(i) for i in (1,2,3)]);s.validate_result(result,receipt)

    def test_rational_noninteger_period_common_and_misaligned(self):
        row=analyzed_slot(**{k:Stream([trace(n=961,rate=120,suffix=k)]) for k in q.COMPONENTS})
        self.assertTrue(all(w['available'] for w in row['joint_windows'].values()))
        self.assertEqual(row['joint_windows']['1']['common_observed_rate'],{'numerator':120,'denominator':1})
        self.assertEqual(row['components']['Z']['decoded_traces'][0]['last_sample_ns']['denominator'],1)
        shifted=Stream([trace(start=-2.999,rate=120,n=961,suffix='E')]);row=analyzed_slot(E=shifted,N=Stream([trace(n=961,rate=120,suffix='N')]),Z=Stream([trace(n=961,rate=120)]))
        self.assertTrue(row['components']['E']['windows']['1']['core']['available']);self.assertFalse(row['joint_windows']['1']['available'])

    def test_mixed_component_and_within_object_rates(self):
        row=analyzed_slot(E=Stream([trace(n=1601,rate=200,suffix='E')]))
        self.assertTrue(all(o['windows']['5']['core']['available'] for o in row['components'].values()))
        self.assertEqual(row['joint_windows']['5']['reason'],'mixed_component_rates')
        row=analyzed_slot(E=Stream([trace(n=300,suffix='E'),trace(start=0,n=1001,rate=200,suffix='E')]))
        self.assertFalse(row['components']['E']['observed_rate_consistent'])
        self.assertEqual(row['joint_windows']['5']['reason'],'component_incomplete')

    def test_gap_overlap_misaligned_and_missing_edge_retained(self):
        for st in (Stream([trace(n=300,suffix='N'),trace(start=.01,n=501,suffix='N')]),
                   Stream([trace(n=300,suffix='N'),trace(start=-.01,n=501,suffix='N')]),
                   Stream([trace(n=300,suffix='N'),trace(start=.005,n=501,suffix='N')]),
                   Stream([trace(start=-2.99,suffix='N')]),Stream([trace(n=799,suffix='N')])):
            row=analyzed_slot(N=st);self.assertFalse(row['joint_windows']['5']['available']);self.assertEqual(len(row['components']),3)
        row=analyzed_slot(E=Stream([trace(n=500,suffix='E'),trace(start=3,n=201,suffix='E')]))
        self.assertTrue(row['joint_windows']['1']['available']);self.assertFalse(row['joint_windows']['3']['available'])

    def test_wrong_literal_extra_nslc_no_alternate_axes(self):
        for field,value in (('network','XX'),('station','BBB'),('location',''),('channel','HH1')):
            st=Stream([trace(suffix='E'),trace(suffix='E',**{field:value})])
            row=analyzed_slot(E=st);self.assertFalse(row['components']['E']['literal_identity_matches'])
            self.assertTrue(all(w['available'] is False for w in row['joint_windows'].values()))

    def test_future_amplitude_poison_half_open_each_horizon(self):
        for horizon in q.HORIZONS:
            row=analyzed_slot();changes={}
            for k in q.COMPONENTS:
                tr=trace(n=1001,suffix=k);tr.data=tr.data.astype(float);tr.data[(3+horizon)*100:]=np.nan;changes[k]=Stream([tr])
            changed=analyzed_slot(**changes)
            for k in q.COMPONENTS:self.assertEqual(row['components'][k]['windows'][str(horizon)],changed['components'][k]['windows'][str(horizon)])
            self.assertEqual(row['joint_windows'][str(horizon)],changed['joint_windows'][str(horizon)])
        tr=trace(suffix='N');tr.data=tr.data.astype(float);tr.data[350]=np.nan
        self.assertFalse(analyzed_slot(N=Stream([tr]))['joint_windows']['1']['available'])

    def test_unknown_vs_known_incomplete_and_pick_separate(self):
        comps={k:analyzed_component(0,k) for k in q.COMPONENTS};comps['E']=q.failed(0,'decode_or_grid_unsupported')
        p=parent_slot();p['pick_ns']=p['t0_ns']+c.NS
        for o in comps.values():
            if o['status']=='decoded':
                o.update(metadata_pick_ns=p['pick_ns'],pick_minus_t0_ns=c.NS)
                for h in q.HORIZONS:o['windows'][str(h)]['target_pick_strictly_before_deadline']=p['pick_ns'] < p['t0_ns']+h*c.NS
        row=q.make_slot(p,comps,c);self.assertIsNone(row['joint_windows']['1']['available'])
        self.assertFalse(row['catalogue_pick_before_deadline']['1']);self.assertTrue(row['catalogue_pick_before_deadline']['3'])
        comps['N']=analyzed_component(0,'N',Stream([trace(start=-2,suffix='N')]))
        row=q.make_slot(p,comps,c);self.assertFalse(row['joint_windows']['1']['available'])
        self.assertIsNone(row['components']['E']['windows']['1']['core']['available'])
        p['pick_ns']=p['t0_ns']-c.NS;row=q.make_slot(p,comps,c);self.assertEqual(row['pick_minus_t0_ns'],-c.NS)

    def test_flat_extreme_and_day_crossing_no_physical_claim(self):
        streams={k:Stream([trace(suffix=k)]) for k in q.COMPONENTS}
        for st in streams.values():st[0].data[:]=2
        row=analyzed_slot(**streams)
        self.assertTrue(row['joint_windows']['5']['available']);self.assertTrue(row['components']['Z']['windows']['5']['core']['clipping_candidate'])
        self.assertEqual(row['components']['Z']['filename_day_boundary_crossing_count'],1)
        agg=q.aggregate([row]+[analyzed_slot(i) for i in (1,2,3)])
        self.assertTrue(all(v is False for k,v in agg.items() if k.endswith('_verified')))

    def test_aggregate_privacy_and_strict_catalogue_intersection(self):
        rows=[analyzed_slot(i) for i in range(4)];rows[0]['private_sentinel']='PRIVATE_SENTINEL'
        rows[0]['catalogue_pick_before_deadline']['1']=False
        agg=q.aggregate(rows);body=json.dumps(agg)
        for token in ('PRIVATE_SENTINEL','AAA','HHZ','t0_ns','body_path','157'):self.assertNotIn(token,body)
        self.assertEqual(agg['joint_window_states']['1']['available'],4)
        self.assertEqual(agg['joint_window_states']['1']['complete_and_catalogue_pick_before_deadline'],3)

    def test_supervisor_validates_every_cell_joint_rational_and_bounds(self):
        result,receipt=envelope([analyzed_slot(i) for i in range(4)]);s.validate_result(result,receipt)
        for k in q.COMPONENTS:
            for horizon in ('1','3','5'):
                for field,value in (('left_ns',0),('deadline_ns',True),('target_pick_strictly_before_deadline',1)):
                    bad=copy.deepcopy(result);bad['private']['slots'][0]['components'][k]['windows'][horizon][field]=value
                    with self.assertRaises(ValueError):s.validate_result(bad,receipt)
                bad=copy.deepcopy(result);bad['private']['slots'][0]['components'][k]['windows'][horizon]['core']['finite']=False
                with self.assertRaises(ValueError):s.validate_result(bad,receipt)
        bad=copy.deepcopy(result);bad['private']['provenance']['advertised_samples_decoded']=0
        with self.assertRaises(ValueError):s.validate_result(bad,receipt)
        for field,value in (('mask','unknown'),('lattices_compatible',None),('common_observed_rate',{'numerator':200,'denominator':2}),('available',1)):
            bad=copy.deepcopy(result);bad['private']['slots'][0]['joint_windows']['1'][field]=value
            with self.assertRaises(ValueError):s.validate_result(bad,receipt)

    def test_retained_trace_identity_and_observed_counter_consistency(self):
        result,receipt=envelope([analyzed_slot(i) for i in range(4)])
        changes=[('decoded_traces',lambda o:o['decoded_traces'][0]['nslc'].__setitem__(3,'HH1')),
            ('observed_nslc',lambda o:o['observed_nslc'][0].__setitem__('decoded_trace_count',2)),
            ('observed_count_type',lambda o:o['observed_nslc'][0].__setitem__('decoded_trace_count',1.0)),
            ('both',lambda o:[o['decoded_traces'][0]['nslc'].__setitem__(3,'HH1'),o['observed_nslc'][0]['nslc'].__setitem__(3,'HH1')])]
        for label,change in changes:
            bad=copy.deepcopy(result);change(bad['private']['slots'][0]['components']['Z'])
            with self.subTest(label=label),self.assertRaises(ValueError):s.validate_result(bad,receipt)

    def test_incomplete_diagnostic_schema_and_primitives_fail_closed(self):
        flat_gap=Stream([trace(n=300,suffix='E'),trace(start=.01,n=501,suffix='E')])
        for tr in flat_gap:tr.data[:]=1
        cases=[flat_gap,Stream([trace(n=300,suffix='E'),trace(start=.01,n=501,suffix='E')]),
            Stream([trace(start=6,suffix='E')]),Stream([trace(suffix='E'),trace(suffix='N')]),
            Stream([trace(n=300,suffix='E'),trace(start=0,n=1001,rate=200,suffix='E')]),Stream()]
        for stream in cases:
            rows=[analyzed_slot(E=stream)]+[analyzed_slot(i) for i in (1,2,3)]
            result,receipt=envelope(rows);s.validate_result(result,receipt)
            obj=result['private']['slots'][0]['components']['E']
            self.assertFalse(obj['windows']['1']['core']['available'])
            for field,value in (('samples',-1),('available',None),('EXTRA','invalid')):
                bad=copy.deepcopy(result);bad['private']['slots'][0]['components']['E']['windows']['1']['core'][field]=value
                with self.subTest(case=stream,field=field),self.assertRaises(ValueError):s.validate_result(bad,receipt)
            for field,value in (('decoded_traces','invalid'),('EXTRA','invalid'),('decoded_sample_grid',{})):
                bad=copy.deepcopy(result);bad['private']['slots'][0]['components']['E'][field]=value
                with self.subTest(case=stream,field=field),self.assertRaises(ValueError):s.validate_result(bad,receipt)
            if 'finite' in obj['windows']['1']['core']:
                for field,value in (('finite','invalid'),('gaps',-1),('longest_prefix_extreme_run',-1),
                    ('timing_quality_values',['None','None']),('clipping_candidate','invalid')):
                    bad=copy.deepcopy(result);bad['private']['slots'][0]['components']['E']['windows']['1']['core'][field]=value
                    with self.subTest(field=field),self.assertRaises(ValueError):s.validate_result(bad,receipt)

    def test_qualified_first_counts_and_trace_bounds_replayed(self):
        result,receipt=envelope([analyzed_slot(i) for i in range(4)])
        bad=copy.deepcopy(result)
        for k in q.COMPONENTS:
            w=bad['private']['slots'][0]['components'][k]['windows']['1']
            w['core']['first_sample_ns_numerator']=w['left_ns']+c.NS
            w['core']['first_sample_ns_denominator']=1
        # All three forged first times still agree in phase, but contradict the
        # retained trace crop and first-edge contract. They cannot be published.
        with self.assertRaises(ValueError):s.validate_result(bad,receipt)
        for field,value in (('samples',1),('first_sample_ns_denominator',2)):
            bad=copy.deepcopy(result);bad['private']['slots'][0]['components']['E']['windows']['1']['core'][field]=value
            with self.assertRaises(ValueError):s.validate_result(bad,receipt)
        for field,value in (('npts',800),('last_sample_ns',None),('start_ns',T0.ns)):
            bad=copy.deepcopy(result);bad['private']['slots'][0]['components']['N']['decoded_traces'][0][field]=value
            with self.assertRaises(ValueError):s.validate_result(bad,receipt)
        st=Stream([trace(n=300,suffix='N'),trace(start=.0000005,n=501,suffix='N')])
        rows=[analyzed_slot(N=st)]+[analyzed_slot(i) for i in (1,2,3)]
        result,receipt=envelope(rows);s.validate_result(result,receipt)

class DecodeTests(unittest.TestCase):
    def test_real_float64_nan_at_exact_deadline_excluded_then_observed(self):
        tr=trace();tr.data=tr.data.astype(np.float64);tr.data[400]=np.nan
        buffer=io.BytesIO();Stream([tr]).write(buffer,format='MSEED',encoding='FLOAT64',reclen=512)
        st,count,_=q.decode(buffer.getvalue(),obspy.read,q.TOTAL_SAMPLE_CAP)
        self.assertEqual(count,801);self.assertEqual(st[0].data.dtype.kind,'f')
        row=q.analyze(st,flat_slot(),c)
        self.assertTrue(row['windows']['1']['core']['available'])
        self.assertFalse(row['windows']['3']['core']['available'])

    def test_real_invented_miniseed_en_z_roundtrip_and_adjacent_records(self):
        for k in q.COMPONENTS:
            body=encoded([trace(n=300,suffix=k)])+encoded([trace(start=0,n=500,suffix=k)])
            st,count,_=q.decode(body,obspy.read,q.TOTAL_SAMPLE_CAP)
            self.assertEqual(count,800);self.assertTrue(q.analyze(st,flat_slot(suffix=k),c)['windows']['5']['core']['available'])
        for shift in (.01,-.01):
            body=encoded([trace(n=300)])+encoded([trace(start=shift,n=500)])
            st,count,_=q.decode(body,obspy.read,q.TOTAL_SAMPLE_CAP)
            self.assertFalse(q.analyze(st,flat_slot(),c)['windows']['5']['core']['available'])

    def test_decoder_coalescing_can_hide_raw_record_half_sample_offset(self):
        # ObsPy's API can coalesce a .005s offset at100Hz. Preserve that returned
        # trace, but do not mistake its grid for a raw-record segmentation proof.
        body=encoded([trace(n=300)])+encoded([trace(start=.005,n=500)])
        st,count,_=q.decode(body,obspy.read,q.TOTAL_SAMPLE_CAP)
        self.assertEqual((len(st),count),(1,800))
        self.assertTrue(q.analyze(st,flat_slot(),c)['windows']['5']['core']['available'])
        rawpieces=Stream([trace(n=300),trace(start=.005,n=500)])
        self.assertFalse(q.analyze(rawpieces,flat_slot(),c)['windows']['5']['core']['available'])

    def test_advertised_caps_stop_before_full_decode(self):
        for count in (-1,True,1.0,float('nan'),q.OBJECT_SAMPLE_CAP+1):
            calls=[]
            def reader(*a,**kw):calls.append(kw);return [types.SimpleNamespace(stats=types.SimpleNamespace(npts=count))]
            with self.assertRaises(ValueError):q.decode(b'invented',reader,q.TOTAL_SAMPLE_CAP)
            self.assertEqual(len(calls),1)
        with self.assertRaises(ValueError):q.decode(encoded([trace()]),obspy.read,800)
        self.assertEqual(q.TOTAL_SAMPLE_CAP,192_000_000)

    def test_header_full_disagreement_dtype_shape_and_warning_privacy(self):
        header=Stream([trace()]);full=header.copy();full[0].data=full[0].data[:-1]
        with self.assertRaises(ValueError):q.decode(b'invented',lambda *a,**kw:header if kw.get('headonly') else full,1000)
        for field,value in (('sampling_rate',200.),('station','BBB'),('starttime',T0)):
            full=header.copy();setattr(full[0].stats,field,value)
            with self.assertRaises(ValueError):q.decode(b'invented',lambda *a,**kw:header if kw.get('headonly') else full,1000)
        full=header.copy();full[0].data=full[0].data.astype(np.uint32)
        with self.assertRaises(ValueError):q.decode(b'invented',lambda *a,**kw:header if kw.get('headonly') else full,1000)
        import warnings
        def reader(*a,**kw):warnings.warn('PRIVATE_SENTINEL');return header
        self.assertEqual(q.decode(b'invented',reader,1000)[2],2)
        for rate in (0,math.nan,math.inf):
            with self.assertRaises(ValueError):q.trace_signature(types.SimpleNamespace(stats=types.SimpleNamespace(sampling_rate=rate)))

class GateTests(unittest.TestCase):
    def fixture(self,directory):
        root=Path(directory).resolve();sources={n:h.digest((ROOT/n).read_bytes()) for n in h.SOURCE_NAMES};slots=[]
        for i in range(4):
            p=parent_slot(i)
            for k in q.COMPONENTS:
                body=encoded([trace(suffix=k)]);path=root/('invented'+str(i)+k+'.mseed');path.write_bytes(body)
                p['components'][k].update(body_path=str(path),body_sha256=h.digest(body),body_bytes=len(body))
            slots.append(p)
        plan={'protocol_id':h.PROTOCOL,'precontext_s':3,'prerequisites':prereqs(),'limits':h.LIMITS,'source_files':sources,'slots':slots}
        planpath=root/'invented_plan.json';planpath.write_text(json.dumps(plan));ph=h.digest(planpath.read_bytes())
        auth={'protocol_id':h.PROTOCOL,'precontext_s':3,'prerequisites':prereqs(),'limits':h.LIMITS,'source_files':sources,
            'plan_sha256':ph,'offline_decode_authorized':True,'code_only_review_clean':True,'focused_tests_passed':True,
            'v5_transfer_all_eight_complete':True,'independent_v4_all_eight_passed':True,'parent_fixed_bindings_verified':True,
            'pushed_source_commit':'a'*40,'source_manifest_sha256':'1'*64,'review_receipt_sha256':'2'*64,'test_receipt_sha256':'3'*64}
        authpath=root/'invented_auth.json';authpath.write_text(json.dumps(auth));runtime=str(Path(sys.executable).absolute())
        return types.SimpleNamespace(plan=str(planpath),authorization=str(authpath),plan_sha256=ph,authorization_sha256=h.digest(authpath.read_bytes()),
            adapter_sha256=sources['child_harness.py'],supervisor_sha256=sources['supervisor.py'],runtime_path=runtime,
            runtime_sha256=h.digest(Path(runtime).resolve().read_bytes()),deadline=time.monotonic()+120)

    def update(self,args,plan=None,auth=None):
        if plan is not None:
            Path(args.plan).write_text(json.dumps(plan));args.plan_sha256=h.digest(Path(args.plan).read_bytes())
            if auth is None:auth=json.loads(Path(args.authorization).read_bytes())
            auth['plan_sha256']=args.plan_sha256
        if auth is not None:
            Path(args.authorization).write_text(json.dumps(auth));args.authorization_sha256=h.digest(Path(args.authorization).read_bytes())

    def test_actual_source_invented_twelve_body_supervised_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory)
            receipt=s.supervise(runtime=args.runtime_path,runtime_sha256=args.runtime_sha256,child=str(ROOT/'child_harness.py'),
                child_sha256=args.adapter_sha256,supervisor_sha256=args.supervisor_sha256,plan=args.plan,plan_sha256=args.plan_sha256,
                authorization=args.authorization,authorization_sha256=args.authorization_sha256,out_dir=str(Path(directory).resolve()/'exclusive_output'))
            self.assertTrue(receipt['complete'],receipt)
            result=json.loads((Path(directory)/'exclusive_output/private_result.json').read_bytes())
            self.assertEqual(result['private']['provenance']['validated_body_count'],12)
            self.assertEqual([c['available'] for c in result['public_aggregate']['joint_window_states'].values()],[4,4,4])

    def test_gate12_paths_triplet_clocks_role_and_caps_before_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);plan,auth,buffers=h.validate_gate(args);self.assertEqual(len(buffers),8)
            for mutate in (
                lambda p:p['slots'][3]['components']['Z'].update(body_path='relative_twelfth'),
                lambda p:p['slots'][3]['components']['Z']['expected_nslc'].update(channel='HHN'),
                lambda p:p['slots'][0]['components']['E']['expected_nslc'].update(station='BBB'),
                lambda p:p['slots'][1].update(t0_ns=None),lambda p:p['slots'][0].update(slot_index=True),
                lambda p:p['slots'][0]['components']['E'].update(body_bytes=h.BODY_CAP+1),
                lambda p:p['slots'][2].update(filename_year=2021,filename_doy=366),
                lambda p:p['slots'][1]['components']['N'].update(body_path=p['slots'][0]['components']['N']['body_path'])):
                args=self.fixture(directory);bad=copy.deepcopy(plan);mutate(bad);self.update(args,plan=bad)
                with patch.object(h,'verify_runtime',side_effect=AssertionError('must not start runtime')):
                    with self.assertRaises(ValueError):h.run(args)
            self.assertEqual(h.TOTAL_BODY_CAP,768*1024*1024)

    def test_new_prerequisite_authority_identity_context_source_pins(self):
        for subject in ('plan','authorization'):
            for field,value in (('precontext_s',3.0),('precontext_s',True),('precontext_s',5),
                                ('protocol_id','geonet-archive-precontext-sensitivity-v2')):
                with tempfile.TemporaryDirectory() as directory:
                    args=self.fixture(directory);obj=json.loads(Path(getattr(args,subject)).read_bytes());obj[field]=value
                    self.update(args,**{subject if subject=='plan' else 'auth':obj})
                    with self.assertRaises(ValueError):h.validate_gate(args)
        for field in ('v5_transfer_all_eight_complete','independent_v4_all_eight_passed','parent_fixed_bindings_verified','offline_decode_authorized'):
            with tempfile.TemporaryDirectory() as directory:
                args=self.fixture(directory);auth=json.loads(Path(args.authorization).read_bytes());auth[field]=False;self.update(args,auth=auth)
                with self.assertRaises(ValueError):h.validate_gate(args)
        for field,value in (('transport_protocol_id','geonet-anonymous-archive-transport-v4'),('transport_proposal_sha256','0'*64),('independent_v4_audit_sha256','bad')):
            with tempfile.TemporaryDirectory() as directory:
                args=self.fixture(directory);plan=json.loads(Path(args.plan).read_bytes());plan['prerequisites'][field]=value
                auth=json.loads(Path(args.authorization).read_bytes());auth['prerequisites']=copy.deepcopy(plan['prerequisites']);self.update(args,plan=plan,auth=auth)
                with self.assertRaises(ValueError):h.validate_gate(args)
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);plan=json.loads(Path(args.plan).read_bytes());plan['source_files']['core.py']='0'*64
            auth=json.loads(Path(args.authorization).read_bytes());auth['source_files']=plan['source_files'];self.update(args,plan=plan,auth=auth)
            with self.assertRaises(ValueError):h.validate_gate(args)

    def test_every_limit_requires_exact_integer_in_plan_and_auth(self):
        for subject in ('plan','authorization'):
            for key,value in h.LIMITS.items():
                with self.subTest(subject=subject,key=key),tempfile.TemporaryDirectory() as directory:
                    args=self.fixture(directory);obj=json.loads(Path(getattr(args,subject)).read_bytes())
                    obj['limits'][key]=float(value)
                    self.update(args,**{subject if subject=='plan' else 'auth':obj})
                    with patch.object(h,'verify_runtime',side_effect=AssertionError('must not start decoder')):
                        with self.assertRaises(ValueError):h.run(args)

    def test_failed_component_retains_other_objects_and_unknowns(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);plan=json.loads(Path(args.plan).read_bytes());obj=plan['slots'][0]['components']['E'];p=Path(obj['body_path'])
            p.write_bytes(b'invented invalid miniseed');obj.update(body_sha256=h.digest(p.read_bytes()),body_bytes=p.stat().st_size);self.update(args,plan=plan)
            result=h.run(args);self.assertEqual(result['public_aggregate']['failed_objects'],1)
            self.assertEqual(result['private']['provenance']['validated_body_count'],12)
            self.assertTrue(all(w['available'] is None for w in result['private']['slots'][0]['joint_windows'].values()))
            receipt={'plan_sha256':args.plan_sha256,'authorization_sha256':args.authorization_sha256,'adapter_sha256':args.adapter_sha256,'supervisor_sha256':args.supervisor_sha256}
            s.validate_result(result,receipt)

    def test_bad_body_pin_aborts_not_scientific_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);plan=json.loads(Path(args.plan).read_bytes());Path(plan['slots'][3]['components']['Z']['body_path']).write_bytes(b'changed')
            with self.assertRaises(ValueError):h.run(args)

    def test_regular_reader_symlink_fifo_json_bounds_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();p=root/'invented';p.write_bytes(b'1234');link=root/'link';link.symlink_to(p)
            for path,cap,deadline in ((str(link),4,time.monotonic()+1),(str(p),3,time.monotonic()+1),(str(p),4,time.monotonic()-1)):
                with self.assertRaises((ValueError,TimeoutError)):h.bounded_read(path,cap,deadline)
            import os
            fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaises(ValueError):h.bounded_read(str(fifo),4,time.monotonic()+1)
        for b in (b'{"a":1,"a":2}',b'{"a":NaN}'):
            with self.assertRaises(ValueError):h.strict_json(b)
        with patch.object(h,'OUTPUT_CAP',64),self.assertRaises(ValueError):h.bounded_result({'too_large':'x'*100})
        with self.assertRaises(ValueError):h.bounded_result({'nonfinite':math.inf})

if __name__=='__main__':unittest.main()
