"""Invented-only causal/native/model/numerical tests; no actual data or pilot.run."""
import copy
from fractions import Fraction
import hashlib
import json
import math
import struct
import time
import unittest
from unittest.mock import patch
import numpy as np
import torch
import observations as obs
import models
import pilot
import numerical_core as core
import posterior_scores
import mixture_density
from decode_contract import ObservedDecodeFailure

START=1704067200000000000


def record(channel,index,tag):
    raw=bytearray(2048);station='ABC'+str(tag)
    raw[:20]=b'000001D '+station.ljust(5).encode()+b'  '+channel.encode()+b'NZ'
    values=[]
    for k in range(256):
        second=index*4+k/64
        if second<3:values.append((tag+1)*(1 if k%2 else -1))
        else:
            cell=int((second-3)*4);active=(cell%5) in (0,1,3)
            values.append((40+tag*10)*(1 if k%2 else .5) if active else 0)
    values=[int(x) for x in values]
    struct.pack_into('>HHBBBBHHhhBBBBiHH',raw,20,2024,1,0,0,index*4,0,0,len(values),64,1,0,0,0,1,0,56,48)
    struct.pack_into('>HHBBBB',raw,48,1000,0,3,1,11,0)
    struct.pack_into('>'+'i'*len(values),raw,56,*values)
    return bytes(raw)


def decode(raw,d):
    start,rate,_=obs.new_native.header_grid(d)
    values=list(struct.unpack_from('>'+'i'*d['npts'],raw,d['data_offset']))
    return dict(start_ns=start,rate=float(rate),dtype='i4',values=values)


def plans():
    body=b''.join(record('HH'+s,index,tag) for tag in range(4) for s in 'EN12Z' for index in (0,1))
    result=[]
    for n,b,core in [(65,17,obs.old_native),(50,13,obs.new_native)]:
        rows=[]
        for i in range(n):
            row=dict(ordinal=i,partition='TRAIN' if n==50 or i<41 else 'DEV',batch=i//4,
                     network='NZ',station='ABC'+str(i%4),location='',prefix='HH',t0_ns=START+3*10**9,
                     pick_ns=START+3*10**9,family=('ENZ' if n==50 or i>=61 or 4<=i<47 else '12Z' if 47<=i<61 else None),nominal_rates={})
            suffixes='ENZ' if row['family']=='ENZ' else '12Z' if row['family']=='12Z' else ''
            row['nominal_rates']={'HH'+s:[64,1] for s in suffixes}
            if n==50:row.update(global_ordinal=65+i,queryable=True)
            rows.append(row)
        bodies={i:body for i in range(b)}
        batches=[]
        for i in range(b):
            row=dict(ordinal=i,rows=list(range(4*i,min(4*i+4,n))),transport='http200',body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest())
            if n==50:row['requested_rows']=list(row['rows'])
            batches.append(row)
        plan=dict(study=core.STUDY,rows=rows,batches=batches);q=core.qualify(plan,bodies,decode)
        # The final shorter batch may have unrequested stations in the body, which
        # old qualifier correctly vetoes; use only the exact batch's station records.
        for batch in batches:
            tags={i%4 for i in batch['rows']};selected=b''.join(record('HH'+s,j,t) for t in sorted(tags) for s in 'EN12Z' for j in (0,1))
            bodies[batch['ordinal']]=selected;batch.update(body_bytes=len(selected),body_sha256=hashlib.sha256(selected).hexdigest())
        q=core.qualify(plan,bodies,decode);result.append((plan,q,bodies))
    metadata=[];roster=[]
    for i in range(115):
        partition='TRAIN' if i<41 or i>=65 else 'DEV';common=4<=i<63 or 65<=i<93
        metadata.append(dict(ordinal=i,partition=partition,mw=6. if i%3==0 else 4.5,group=i,operational_eligible=True,
                             station_latitude=float(i%15),station_longitude=float(i%17),station_elevation=float(i%11),sensitivities=[10.,20.,30.],units=['M/S']*3))
        roster.append(dict(ordinal=i,common=common))
    return result,metadata,dict(schema='receiver-renewal-roster-v1',study=obs.STUDY,rows=roster)


def make_packet():
    pairs,meta,roster=plans();(op,oq,ob),(np_,nq,nb)=pairs
    values=dict(old_plan=op,old_qualified=oq,new_plan=np_,new_qualified=nq,metadata=meta,roster=roster)
    raw={k:obs.canonical(v) for k,v in values.items()};pins={k:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for k,v in raw.items()}
    packet=obs.build(raw['old_plan'],raw['old_qualified'],ob,raw['new_plan'],raw['new_qualified'],nb,raw['metadata'],raw['roster'],decode,pins=pins,processing_begin=time.monotonic())
    return packet,pairs,meta,roster,raw,pins


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.packet,cls.pairs,cls.meta,cls.roster,cls.raw,cls.pins=make_packet()
    def test_fixed115_345_two_namespaces_and_explicit_dev_current_observations(self):
        roles=pilot.validate(self.packet);self.assertEqual((len(roles['TRAIN']),len(roles['DEV'])),(65,22))
        self.assertEqual(len(self.packet['rows']),115);self.assertFalse(self.packet['fit_authorized'])
        self.assertIsNotNone(self.packet['rows'][41]['initial']);self.assertIsNone(self.packet['rows'][63]['initial'])
        self.assertGreater(self.packet['observed_samples']['old'],0);self.assertGreater(self.packet['observed_samples']['new'],0)
    def test_native_causal_initial_and_current_future_invariance_bitwise(self):
        plan,q,bodies=self.pairs[0];counts={'old':0,'new':0}
        records=obs.replay_batch(obs.old_native,plan,q,bodies,decode,1,counts,'old',time.monotonic())
        native=obs.components(obs.old_native,plan['rows'][4],q['rows'][4],records)
        a,ha=obs.event_observations(native,plan['rows'][4],self.meta[4]);changed=copy.deepcopy(native)
        for c in changed:
            for p in c['pieces']:
                for k in range(len(p['values'])):
                    t=p['start_ns']+Fraction(*p['rational_period'])*k
                    if t>=START+4*10**9:p['values'][k]=99999
        b,hb=obs.event_observations(changed,plan['rows'][4],self.meta[4])
        for key in ('wave','amplitude','context'):self.assertEqual(a[key].tobytes(),b[key].tobytes())
        for key in ('wave','amplitude','context'):self.assertEqual(ha[0][key].tobytes(),hb[0][key].tobytes())
        self.assertEqual(ha[0]['ratios'],hb[0]['ratios']);self.assertFalse(np.array_equal(ha[2]['wave'],hb[2]['wave']))
    def test_immutable_delta_shared_across_initial_current_and_inside1s_future(self):
        plan,q,bodies=self.pairs[0];row=copy.deepcopy(plan['rows'][4]);row['pick_ns']+=500_000_000
        records=obs.replay_batch(obs.old_native,plan,q,bodies,decode,1,{'old':0,'new':0},'old',time.monotonic())
        native=obs.components(obs.old_native,plan['rows'][4],q['rows'][4],records)
        a,ha=obs.event_observations(native,row,self.meta[4]);self.assertEqual(a['context'][7],.5)
        self.assertTrue(all(h['context'][8]==.5 and h['context'][7]==h['seconds'] for h in ha))
        changed=copy.deepcopy(native)
        for component in changed:
            for piece in component['pieces']:
                for k in range(len(piece['values'])):
                    t=piece['start_ns']+Fraction(*piece['rational_period'])*k
                    if t>=row['pick_ns']+250_000_000:piece['values'][k]=77777
        b,hb=obs.event_observations(changed,row,self.meta[4])
        for key in ('wave','amplitude','context'):self.assertEqual(a[key].tobytes(),b[key].tobytes())
        self.assertFalse(np.array_equal(ha[0]['wave'],hb[0]['wave']))

    def test_pin_tamper_stops_before_decoder_and_no_common_shrink(self):
        raw=dict(self.raw);raw['metadata']=raw['metadata']+b' '
        with self.assertRaisesRegex(ValueError,'input_pin'):
            obs.build(raw['old_plan'],raw['old_qualified'],self.pairs[0][2],raw['new_plan'],raw['new_qualified'],self.pairs[1][2],raw['metadata'],raw['roster'],lambda *_:self.fail('bad pin decode'),pins=self.pins,processing_begin=time.monotonic())
        bad=copy.deepcopy(self.packet);bad['rows'][4]['common']=False
        with self.assertRaises(ValueError):pilot.validate(bad)
    def test_grid_raw_native_view_and_observed_mismatch_veto(self):
        plan,q,bodies=copy.deepcopy(self.pairs[0]);q['records'][0]['raw_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'raw_hash'):obs.replay_batch(obs.old_native,plan,q,bodies,decode,0,{'old':0,'new':0},'old',time.monotonic())
        plan,q,bodies=copy.deepcopy(self.pairs[0])
        def bad(raw,d):out=decode(raw,d);out['values'][0]+=1;return out
        with self.assertRaisesRegex(ValueError,'sample_hash'):obs.replay_batch(obs.old_native,plan,q,bodies,bad,0,{'old':0,'new':0},'old',time.monotonic())
        records=obs.replay_batch(obs.old_native,plan,q,bodies,decode,1,{'old':0,'new':0},'old',time.monotonic());next(c for c in q['rows'][4]['cells'][0]['components'] if c['channel']=='HHE')['view_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'view_hash'):obs.components(obs.old_native,plan['rows'][4],q['rows'][4],records)
    def test_failure_counts_before_discard_invalid_counts_no_output(self):
        plan,q,bodies=self.pairs[1]
        def failure(*_):raise ObservedDecodeFailure(8_000_001)
        counts={'old':0,'new':0}
        with self.assertRaisesRegex(ValueError,'observed_cap'):obs.replay_batch(obs.new_native,plan,q,bodies,failure,0,counts,'new',time.monotonic())
        self.assertEqual(counts['new'],8_000_001)
        class Bad(ValueError):observed_samples=True
        def invalid(*_):raise Bad()
        with self.assertRaisesRegex(ValueError,'observed_accounting'):obs.replay_batch(obs.new_native,plan,q,bodies,invalid,0,{'old':0,'new':0},'new',time.monotonic())
    def test_train_scalers_exclude_dev_and_shared_static_identical(self):
        roles=pilot.validate(self.packet);a=pilot.scaler(self.packet,roles['TRAIN']);changed=copy.deepcopy(self.packet)
        for i in roles['DEV']:changed['rows'][i]['initial']['context']+=1000
        b=pilot.scaler(changed,roles['TRAIN'])
        for k in a:np.testing.assert_array_equal(a[k],b[k])
        for k in range(35):
            j=k if k<7 else k+1;self.assertEqual(a['initial_mean'][k],a['current_mean'][j]);self.assertEqual(a['initial_std'][k],a['current_std'][j])
    def test_strict_role_types_extra_inference_fields_and_caps(self):
        bad=copy.deepcopy(self.packet);bad['rows'][0]['ordinal']=False
        with self.assertRaises(ValueError):pilot.validate(bad)
        bad=copy.deepcopy(self.packet);bad['rows'][4]['initial']['Mw']=6.
        with self.assertRaises(ValueError):pilot.validate(bad)
        with patch.object(obs,'MAX_ELEMENTS',1):
            with self.assertRaisesRegex(ValueError,'observation_output_cap'):make_packet()
    def test_capacity_probe_uses_individual_degrees_on_full_train_without_fit(self):
        roles=pilot.validate(self.packet);stats=pilot.scaler(self.packet,roles['TRAIN'])
        proof=pilot.capacity_probe(self.packet,roles,stats)
        counts=proof['nonzero_TRAIN_probe_gradient_degrees']
        self.assertLessEqual(max(counts.values())/min(counts.values()),1.05)
        self.assertTrue(all(counts[a]<=proof['counts'][a] for a in counts))

    def test_json_bounds_duplicate_and_nonfinite(self):
        for raw in [b'{"x":1,"x":2}',b'{"x":NaN}',('['*34+'0'+']'*34).encode(),('1'*1025).encode()]:
            with self.assertRaises(ValueError):obs.json_load(raw,65536)

    def test_age_zero_no_exit_and_single_count_disjoint_edges(self):
        states=[1,1,0,0,1,1,0,1];idx,y,u,r=core.transitions(states)
        self.assertEqual(len(y),7);self.assertTrue(np.all(r>=1));self.assertEqual(y[-1],1)
        h=core.Hazard('C',[0,0],[.2,-.1],np.zeros((2,2)),np.zeros((2,1)),[.1,.2],[.1,.2],5.)
        full=core.log_likelihood(6.,h,[.2,.4],[.3],states);prefix=core.log_likelihood(6.,h,[.2,.4],[.3],states,4)
        ell=h.logits(6.,[.2,.4],[.3],idx[3:],u[3:],r[3:]);suffix=-np.logaddexp(0.,np.where(y[3:]==1,-ell,ell)).sum()
        self.assertAlmostEqual(float(full),float(prefix+suffix))
        self.assertEqual(float(core.log_likelihood(5.,h,[.2,.4],[.3],[1])),0.)
        with self.assertRaises(ValueError):h.logits(5.,[.2,.4],[.3],[1],[.25],[0])


class ModelTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1);torch.use_deterministic_algorithms(True);torch.manual_seed(12)
        self.w=torch.randn(2,3,17);self.a=torch.randn(2,4);self.c=torch.randn(2,35);self.mask=torch.ones(2,17,dtype=torch.bool)
        self.states=torch.tensor([[1,1,0,1]+[0]*16,[0,0,1,1]+[0]*16]);self.valid=torch.tensor([[True]*4+[False]*16]*2)
    def test_counts_and_used_autograd_five_arms(self):
        self.assertEqual(models.parameter_counts(),{'B':5007,'F':5147,'H':5125,'T':5125,'C':5125})
        for arm in ('C','H','T'):
            net=models.Net(arm,5.);raw,z=net.initial(self.w,self.a,self.c,self.mask)
            loss=(models.nll(torch.tensor([4.,6.]),raw)-net.hazards.likelihood(torch.tensor([4.,6.]),z,self.c,self.states,self.valid)).mean();loss.backward()
            self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in net.parameters()))
        net=models.Net('F',5.);activity=torch.randn(2,5,20);raw=net.current(self.w,self.a,torch.randn(2,36),self.mask,activity,self.valid)
        models.nll(torch.tensor([4.,6.]),raw).mean().backward();self.assertGreater(float(net.feature.weight.grad.abs().sum()),0.)
    def test_initial_future_padding_veto_and_no_current_context_api(self):
        net=models.Net('C',5.);a,z=net.initial(self.w,self.a,self.c,self.mask)
        wave=torch.cat((self.w,torch.full((2,3,15),float('nan'))),2);mask=torch.cat((self.mask,torch.zeros(2,15,dtype=torch.bool)),1)
        b,z2=net.initial(wave,self.a,self.c,mask);torch.testing.assert_close(a,b);torch.testing.assert_close(z,z2)
        with self.assertRaises(ValueError):net.initial(self.w,self.a,torch.randn(2,36),self.mask)
        with self.assertRaises(ValueError):net.current(self.w,self.a,torch.randn(2,36),self.mask)
    def test_torch_core_parity_and_differentiable_quadrature(self):
        net=models.Net('C',5.).double();net.hazards.beta.data[:]=torch.tensor([.3,-.2],dtype=torch.float64);net.hazards.extra.data[:]=.1
        raw,z=net.initial(self.w.double(),self.a.double(),self.c.double(),self.mask)
        logz,mean=models.torch_gh(raw,net.hazards,z,self.c.double(),self.states,self.valid,64)
        target=5.;states=self.states[0,self.valid[0]].tolist();h=net.hazards
        hazard=core.Hazard('C',*[getattr(h,k).detach().numpy() for k in ('alpha','beta','z_weights','c_weights','gamma','extra')],h.mref)
        mixture=core.Mixture.from_raw(raw[0].detach().numpy());ref=core.gauss_hermite(mixture,hazard,z[0].detach().numpy(),self.c[0].numpy(),states,target,64)
        self.assertAlmostEqual(float(logz[0].detach()),ref.log_normalizer,places=10);self.assertAlmostEqual(float(mean[0].detach()),ref.mean,places=10)
        (logz.sum()+mean.sum()).backward();self.assertTrue(torch.isfinite(net.hazards.beta.grad).all())
    def test_h_age_free_but_global_time_dependent_and_extra_effective(self):
        net=models.Net('H',5.);net.hazards.gamma.data[:]=1.;net.hazards.extra.data[:]=1.
        raw,z=net.initial(self.w,self.a,self.c,self.mask)
        index,y,u,r,valid=models.edges(self.states,self.valid)
        self.assertEqual(u.tolist(),[.25*x for x in range(1,20)]);self.assertTrue(torch.all(r[:,:3]>=1))
        value=net.hazards.likelihood(torch.tensor([4.,6.]),z,self.c,self.states,self.valid)
        net.hazards.extra.data.zero_();other=net.hazards.likelihood(torch.tensor([4.,6.]),z,self.c,self.states,self.valid)
        self.assertFalse(torch.equal(value,other))
    def test_masked_future_states_do_not_duplicate_evidence(self):
        net=models.Net('C',5.);net.hazards.beta.data[:]=.3;net.hazards.extra.data[:]=.2
        raw,z=net.initial(self.w,self.a,self.c,self.mask)
        a=net.hazards.likelihood(torch.tensor([4.,6.]),z,self.c,self.states,self.valid)
        changed=self.states.clone();changed[:,4:]=1
        b=net.hazards.likelihood(torch.tensor([4.,6.]),z,self.c,changed,self.valid);torch.testing.assert_close(a,b)
    def test_stable_uncapped_head_and_train_order(self):
        raw=torch.zeros(2,15,requires_grad=True);raw.data[:,5:10]=100.
        loss=models.nll(torch.tensor([4.,6.]),raw).mean();loss.backward();self.assertTrue(torch.isfinite(raw.grad).all())
        orders=list(pilot.event_order(list(range(65)),20261012));self.assertEqual(len(orders),300);self.assertTrue(all(len(set(x))==8 for x in orders))
    def test_source_deadline_before_fit_and_every_guard(self):
        with self.assertRaises(RuntimeError):pilot.deadline(time.monotonic()-3301)
        fits=[]
        for seed in pilot.SEEDS:
            for arm in pilot.ARMS:
                row=dict(tail_mae_5_5=.4 if arm=='C' else .5,nll=.4 if arm=='C' else .5,crps=.4 if arm=='C' else .5,mae=.4,medae=.4,lower_mae=.4,lower_medae=.4,cvar95=.4,maximum=.4)
                fits.append(dict(seed=seed,arm=arm,status='complete',metrics={str(h):dict(row) for h in (1,3,5)}))
        self.assertTrue(pilot.advance(fits)['pass_all'])
        fits[-1]['metrics']['1']['medae']=.41;self.assertFalse(pilot.advance(fits)['pass_all'])
        fits[-1]['metrics']['1']['medae']=.4;fits[0]['metrics']['3']['tail_mae_5_5']=None;self.assertFalse(pilot.advance(fits)['pass_all'])


class ScoreTests(unittest.TestCase):
    def test_proper_scores_match_gaussian_when_likelihood_magnitude_independent(self):
        mixture=core.Mixture([1,0,0,0,0],[5]*5,[.5]*5)
        hazard=core.Hazard('C',[0,0],[0,0],np.zeros((2,2)),np.zeros((2,1)),[0,0],[0,0],5.)
        checked=core.checked_inference(mixture,hazard,[.2,.4],[.3],[1,0,1],6.)
        p=posterior_scores.Posterior(mixture,hazard,[.2,.4],[.3],[1,0,1],checked['adaptive'].log_normalizer,checked['adaptive'].mean,lambda:None)
        self.assertAlmostEqual(p.cdf(5.),.5,places=8);self.assertAlmostEqual(p.quantile(.5),5.,places=8)
        reference=mixture_density.crps(6.,mixture.weights.tolist(),mixture.means.tolist(),mixture.sigmas.tolist())
        self.assertAlmostEqual(p.crps(6.),reference,places=6)
        self.assertAlmostEqual(p.crps(1000.),995.-.5/math.sqrt(math.pi),places=6)
    def test_non_gaussian_adaptive_crps_cdf_matches_independent_direct_density(self):
        from scipy.integrate import quad
        mixture=core.Mixture([1,0,0,0,0],[5]*5,[.7]*5)
        hazard=core.Hazard('C',[-.2,.3],[.5,-.7],np.zeros((2,2)),np.zeros((2,1)),[.1,.1],[.2,-.1],5.)
        z,c,states,target=[.2,.4],[.3],[1,1,0,0,1],6.
        checked=core.checked_inference(mixture,hazard,z,c,states,target);self.assertTrue(checked['accepted'])
        p=posterior_scores.Posterior(mixture,hazard,z,c,states,checked['adaptive'].log_normalizer,checked['adaptive'].mean,lambda:None)
        def pdf(x):return math.exp(float(mixture.logpdf(x)+core.log_likelihood(x,hazard,z,c,states)-checked['adaptive'].log_normalizer))
        def cdf(x):return quad(pdf,-np.inf,x,epsabs=1e-9,epsrel=1e-9)[0] if x<=p.mean else 1.-quad(pdf,x,np.inf,epsabs=1e-9,epsrel=1e-9)[0]
        self.assertAlmostEqual(quad(pdf,-np.inf,np.inf)[0],1.,places=8)
        self.assertAlmostEqual(p.cdf(5.5),cdf(5.5),places=8)
        independent=quad(lambda x:cdf(x)**2,-np.inf,target,epsabs=1e-7,epsrel=1e-7)[0]+quad(lambda x:(1-cdf(x))**2,target,np.inf,epsabs=1e-7,epsrel=1e-7)[0]
        self.assertAlmostEqual(p.crps(target),independent,places=6)
        self.assertAlmostEqual(cdf(p.quantile(.9)),.9,places=7)

    def test_steep_broad_fixed_quadrature_failure_retained(self):
        m=core.Mixture([.2]*5,[3,4,5,6,7],[10]*5);h=core.Hazard('C',[0,0],[50,-50],np.zeros((2,2)),np.zeros((2,1)),[0,0],[0,0],5.)
        check=core.checked_inference(m,h,[.2,.4],[.3],[0,1,1,1],7.)
        self.assertFalse(check['accepted'])
        with self.assertRaises(core.NumericalFailure):posterior_scores.scores(m,h,[.2,.4],[.3],[0,1,1,1],7.,check,lambda:None)


if __name__=='__main__':unittest.main()
