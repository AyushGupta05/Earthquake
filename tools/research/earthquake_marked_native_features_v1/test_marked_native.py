"""Meaningful invented native records only; no private packet or actual data IO."""
import copy
from fractions import Fraction
import hashlib
import json
import math
import statistics
import time
import unittest

import numpy as np
import marked_native as m
import fixtures as f


def independent(native,row):
    # Separate sample-index enumeration and reduction, no original window helper.
    def samples(c,lo,hi):
        out=[]
        for piece in native[c]['pieces']:
            step=Fraction(*piece['rational_period'])
            for k,v in enumerate(piece['values']):
                tick=piece['start_ns']+k*step
                if lo<=tick<hi:out.append(float(v))
        return out
    centers=[];powers=[];nhat=[];ratios=[];t0=row['t0_ns'];p=row['pick_ns']
    for c in range(3):
        xs=samples(c,t0-3*m.SECOND,t0);center=math.fsum(xs)/len(xs);centers.append(center)
        qs=[]
        for j in range(12):
            xs=samples(c,t0-3*m.SECOND+j*m.Q,t0-3*m.SECOND+(j+1)*m.Q)
            qs.append(math.fsum((v-center)*(v-center) for v in xs)/len(xs))
        powers.append(qs);nhat.append(max(1.,statistics.median(qs)))
    for j in range((5*m.SECOND-(p-t0))//m.Q):
        cs=[]
        for c in range(3):
            xs=samples(c,p+j*m.Q,p+(j+1)*m.Q)
            cs.append(math.fsum((v-centers[c])*(v-centers[c]) for v in xs)/len(xs)/nhat[c])
        ratios.append(cs)
    etas=np.asarray([[math.log(max(1.,statistics.median(q[:j]+q[j+1:]))) for q in powers] for j in range(12)])
    means=[math.fsum(etas[:,c])/12 for c in range(3)]
    return centers,powers,nhat,np.asarray(ratios),etas-np.asarray(means)


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=f.corpus();cls.packet=f.build(cls.c)

    def test_fixed_population_all_statuses_and_no_fitting(self):
        p=self.packet;self.assertEqual(p['denominators'],m.DENOMINATORS)
        self.assertEqual([r['ordinal'] for r in p['rows']],list(range(115)))
        self.assertEqual(sum(len(r['horizons']) for r in p['rows']),345)
        self.assertFalse(p['fit_authorized'])
        self.assertEqual(sum(r['common'] and r['partition']=='TRAIN' for r in p['rows']),65)
        self.assertEqual(sum(r['common'] and r['partition']=='DEV' for r in p['rows']),22)
        for r in p['rows']:
            if not r['common']:
                self.assertIsNone(r['noise']);self.assertIsNone(r['precontext'])
                self.assertEqual(r['horizons'],[dict(seconds=h,status='unavailable') for h in (1,3,5)])

    def test_original_exact_activity_context_drop_only_and_prefix(self):
        for r,old in zip(self.packet['rows'],self.c['original']['rows']):
            if not r['common']:continue
            self.assertTrue(m.bit_equal(r['precontext'],np.delete(old['initial']['context'],6)))
            self.assertEqual(r['precontext'].shape,(34,))
            for h,a in zip(r['horizons'],old['horizons']):
                self.assertTrue(m.bit_equal(h['max_ratios'],np.asarray(a['ratios'],dtype='<f8')))
                self.assertEqual(h['states'].tolist(),a['states']);self.assertEqual(h['run_ages'].tolist(),a['run_ages'])
            for a,b in zip(r['horizons'],r['horizons'][1:]):
                self.assertEqual(len(b['ratios'])-len(a['ratios']),8)
                for k in ('ratios','reported','censor','max_ratios','states','run_ages'):
                    self.assertTrue(m.bit_equal(a[k],b[k][:len(a['ratios'])]))

    def test_independent_native_reductions_and_shared_leave_one_index(self):
        native,row,meta=f.one_native(self.c)
        centers,powers,nhat,ratios,nu=independent(native,row)
        r=self.packet['rows'][4];n=r['noise']
        for a,b in ((n['centers'],centers),(n['powers'],powers),(n['nhat'],nhat),(n['nu'],nu),(r['horizons'][2]['ratios'],ratios)):
            self.assertTrue(m.bit_equal(a,np.asarray(b,dtype='<f8')))
        self.assertEqual(n['nu'].shape,(12,3));self.assertEqual(n['weights'].tolist(),[1/12]*12)
        # All components of each support point delete the same chronological index.
        for c in range(3):
            eta=[math.log(max(1.,statistics.median(powers[c][:ell]+powers[c][ell+1:]))) for ell in range(12)]
            self.assertEqual(n['nu'][:,c].tolist(),[e-math.fsum(eta)/12 for e in eta])

    def test_native_i4_f4_f8_hashes_and_no_f32_inverse(self):
        dtypes={entry['dtype'] for _,q,_ in self.c['pairs'] for entry in q['records']}
        self.assertEqual(dtypes,{'i4','f4','f8'})
        native,row,meta=f.one_native(self.c);rounded=copy.deepcopy(native)
        for c in rounded:
            for p in c['pieces']:p['values']=[float(np.float32(v)) for v in p['values']]
        original=independent(native,row);lossy=independent(rounded,row)
        self.assertFalse(np.array_equal(original[1],lossy[1]))
        with self.assertRaisesRegex(m.FeatureError,'activity_anchor_parity|context_anchor_parity'):
            m.event_marks(rounded,row,meta,f.event_anchor(native,row,meta),bindings=f.BINDINGS,processing_begin=time.monotonic())

    def test_all_arrival_offsets_and_complete_first_cell_once(self):
        for i in (4,5,6,7):
            r=self.packet['rows'][i];delta=r['noise']['arrival_offset_ns']
            counts=[(h*m.SECOND-delta)//m.Q for h in (1,3,5)]
            self.assertEqual([len(h['ratios']) for h in r['horizons']],counts)
            self.assertEqual(r['precontext'][6],delta/1e9)
        self.assertEqual(len(self.packet['rows'][7]['horizons'][0]['ratios']),1)

    def test_future_native_change_preserves_earlier_packet(self):
        native,row,meta=f.one_native(self.c);changed=copy.deepcopy(native)
        for c in changed:
            for p in c['pieces']:
                period=Fraction(*p['rational_period'])
                for k in range(len(p['values'])):
                    if p['start_ns']+k*period>=row['t0_ns']+m.SECOND:p['values'][k]+=100
        a=m.event_marks(native,row,meta,f.event_anchor(native,row,meta),bindings=f.BINDINGS,processing_begin=time.monotonic())
        b=m.event_marks(changed,row,meta,f.event_anchor(changed,row,meta),bindings=f.BINDINGS,processing_begin=time.monotonic())
        self.assertTrue(m.bit_equal(a[0],b[0]))
        for k in ('centers','powers','nhat','floors','nu','weights'):self.assertTrue(m.bit_equal(a[1][k],b[1][k]))
        for k in ('ratios','reported','censor','max_ratios','states','run_ages'):self.assertTrue(m.bit_equal(a[2][0][k],b[2][0][k]))
        self.assertFalse(m.bit_equal(a[2][2]['ratios'],b[2][2]['ratios']))

    def test_anchor_missing_status_negative_history_and_future_mismatch(self):
        original=json.loads(self.c['raw']['activity_anchor'])
        for mutation in ('row','status','history','negative','future','context'):
            c=copy.deepcopy(self.c);a=copy.deepcopy(original)
            if mutation=='row':a['rows'].pop()
            elif mutation=='status':del a['rows'][4]['horizons'][0]['status']
            elif mutation=='history':a['rows'][4]['horizons'][0]['run_ages'][0]=2
            elif mutation=='negative':a['rows'][4]['horizons'][0]['ratios'][0]=-1
            elif mutation=='future':a['rows'][4]['horizons'][1]['ratios'][0]=1.0
            else:a['rows'][4]['context35'][0]+=1
            c['raw']['activity_anchor']=m.canonical(a);c['pins']['activity_anchor']=m.pin(c['raw']['activity_anchor'])
            with self.subTest(mutation=mutation),self.assertRaises(m.FeatureError):f.build(c)

    def test_pins_before_decode_and_common_failure_rejects_stage(self):
        c=copy.deepcopy(self.c);c['raw']['old_plan']+=b' '
        with self.assertRaisesRegex(m.FeatureError,'input_pin') as caught:f.build(c,lambda *_:self.fail('must not decode'))
        self.assertEqual(caught.exception.observed_samples,dict(old=0,new=0))
        def wrong(raw,d):
            v=f.decode(raw,d);v['rate']*=2;return v
        with self.assertRaises(m.FeatureError) as caught:f.build(self.c,wrong)
        self.assertGreater(caught.exception.observed_samples['old'],0)
        self.assertEqual(len(caught.exception.partial_rows),4)

    def test_decode_failure_count_charged_before_abort(self):
        class DecodeFailure(ValueError):pass
        def fail(*_):
            error=DecodeFailure('invented');error.observed_samples=257;raise error
        with self.assertRaises(m.FeatureError) as caught:f.build(self.c,fail)
        self.assertEqual(caught.exception.observed_samples,dict(old=257,new=0))

    def test_body_and_full_record_hashes_are_not_crop_only(self):
        c=copy.deepcopy(self.c);body=bytearray(c['pairs'][0][2][1]);body[-1]^=1;c['pairs'][0][2][1]=bytes(body)
        with self.assertRaises(m.FeatureError):f.build(c)
        # Even after body-pin update, the qualified per-record raw pin must fail.
        op=json.loads(c['raw']['old_plan']);op['batches'][1]['body_sha256']=hashlib.sha256(bytes(body)).hexdigest()
        c['raw']['old_plan']=m.canonical(op);c['pins']['old_plan']=m.pin(c['raw']['old_plan'])
        a=json.loads(c['raw']['activity_anchor']);a['input_pins']['old_plan']=c['pins']['old_plan']
        c['raw']['activity_anchor']=m.canonical(a);c['pins']['activity_anchor']=m.pin(c['raw']['activity_anchor'])
        with self.assertRaises(m.FeatureError):f.build(c)

    def test_namespaces_replay_charges_and_distinct_values(self):
        self.assertEqual(self.packet['observed_samples'],self.c['original']['observed_samples'])
        self.assertGreater(self.packet['observed_samples']['old'],0);self.assertGreater(self.packet['observed_samples']['new'],0)
        self.assertFalse(np.array_equal(self.packet['rows'][4]['horizons'][0]['ratios'],self.packet['rows'][65]['horizons'][0]['ratios']))


class ScalarTests(unittest.TestCase):
    def native(self,noise=1.,post=3.,rate=64,family='ENZ'):
        n=8*rate;values=[(noise if k<3*rate else post)*(1 if k%2 else -1) for k in range(n)]
        components=[dict(name='HH'+s,pieces=[dict(start_ns=0,rational_period=[m.SECOND,rate] if math.gcd(m.SECOND,rate)==1 else [m.SECOND//math.gcd(m.SECOND,rate),rate//math.gcd(m.SECOND,rate)],values=list(values))]) for s in family]
        row=dict(t0_ns=3*m.SECOND,pick_ns=3*m.SECOND,family=family)
        meta=dict(station_latitude=0.,station_longitude=0.,station_elevation=None,sensitivities=[None,1.,2.],units=[None,'M/S','M'])
        return components,row,meta

    def run_event(self,native,row,meta):
        return m.event_marks(native,row,meta,f.event_anchor(native,row,meta),bindings=f.BINDINGS,processing_begin=time.monotonic())

    def test_exact_noise_floor_and_activity_threshold(self):
        for noise,flag in ((0.,1),(.5,1),(1.,0)):
            native,row,meta=self.native(noise,3.)
            _,n,hs=self.run_event(native,row,meta)
            self.assertEqual(n['nhat'].tolist(),[1.]*3);self.assertEqual(n['floors'].tolist(),[flag]*3)
            self.assertEqual(hs[0]['max_ratios'].tolist(),[9.]*4)
            self.assertEqual(hs[0]['states'].tolist(),[0]*4)
            self.assertTrue((n['nu']==0).all())

    def test_censor_zero_and_positive_boundary(self):
        native,row,meta=self.native(1.,0.);_,_,hs=self.run_event(native,row,meta)
        self.assertTrue((hs[0]['censor']==1).all());self.assertTrue((hs[0]['reported']==-12).all())
        native,row,meta=self.native(1.,math.exp(-5.));_,_,hs=self.run_event(native,row,meta)
        self.assertTrue((hs[0]['censor']==0).all());self.assertTrue(np.all(hs[0]['reported']>-12))

    def test_noninteger_native_period_half_open_oracle(self):
        native,row,meta=self.native(2.,7.,rate=3,family='12Z')
        # At 3 Hz some .25 s cells have no samples: must reject, not synthesize.
        with self.assertRaises(ValueError):self.run_event(native,row,meta)
        native,row,meta=self.native(2.,7.,rate=12,family='12Z')
        _,noise,hs=self.run_event(native,row,meta)
        independent_values=independent(native,row)
        self.assertEqual(noise['rate'],[12,1])
        self.assertTrue(m.bit_equal(hs[2]['ratios'],independent_values[3]))

    def test_no_overlap_gap_rate_or_literal_family_repair(self):
        native,row,meta=self.native()
        for change in ('gap','order','rate','family'):
            altered=copy.deepcopy(native)
            if change=='gap':altered[0]['pieces'][0]['start_ns']=1
            if change=='order':altered[0],altered[1]=altered[1],altered[0]
            if change=='rate':altered[0]['pieces'][0]['rational_period']=[m.SECOND//32,1]
            if change=='family':altered[0]['name']='HH1'
            with self.subTest(change=change),self.assertRaises(ValueError):self.run_event(altered,row,meta)

    def test_deadline_is_source_started_not_reset(self):
        native,row,meta=self.native();a=f.event_anchor(native,row,meta)
        with self.assertRaisesRegex(m.FeatureError,'deadline'):
            m.event_marks(native,row,meta,a,bindings=f.BINDINGS,processing_begin=time.monotonic()-301)


if __name__=='__main__':unittest.main()
