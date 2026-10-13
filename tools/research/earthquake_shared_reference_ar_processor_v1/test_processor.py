"""Invented L admission, actual optimizer cadence, numerical export and strict guards."""
import copy
import hashlib
import math
from pathlib import Path
import time
import unittest
from unittest import mock
import numpy as np
import torch
import fixtures as f
import processor as p
import l_math as lm
import numeric_state as ns


def decode(raw):
    return ns.decode(raw, ns.digest(raw))


class LTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.packet=f.packet()
        cls.oldraw=f.old.prepare(cls.packet,f.old_bindings(),f.Sink(),processing_begin=time.monotonic())
        cls.b=f.bindings(cls.oldraw,f.ar);cls.sink=f.Sink()
        cls.raw=p.prepare(cls.packet,cls.b,cls.sink,processing_begin=time.monotonic());cls.ad=decode(cls.raw);cls.pin=ns.digest(cls.raw)
        start=time.monotonic();cls.fit_sink=f.Sink()
        cls.fit=p.fit_one(cls.packet,cls.raw,cls.pin,cls.b,cls.fit_sink,seed=p.SEEDS[0],arm='L',processing_begin=start)
        cls.final=decode(cls.fit['checkpoint']);cls.fit_seconds=time.monotonic()-start
        start=time.monotonic();cls.score_sink=f.Sink()
        cls.result=decode(p.score_final(cls.packet,cls.raw,cls.pin,cls.fit['checkpoint'],cls.fit['receipt']['sha256'],cls.b,cls.score_sink,processing_begin=start)['result'])
        print('INVENTED_L300_L66_SECONDS',cls.fit_seconds,time.monotonic()-start)

    def test_original_initial_exact_both_seeds_and_all_degrees_used(self):
        old=decode(self.oldraw)
        self.assertEqual([(v['seed'],v['arm']) for k,v,_ in self.sink.records if k=='initial'],list(p.ORDER))
        for seed in p.SEEDS:
            item=self.ad['models'][f'{seed}:L'];initial=old['models'][f'{seed}:S']['initial']
            self.assertEqual(ns.encode(item['initial']),ns.encode(initial));self.assertEqual(item['original_initial_sha256'],ns.digest(ns.encode(initial)))
            self.assertEqual(item['probe']['terms'],195);self.assertTrue(all((v==1).all() for v in item['probe']['masks'].values()))
            self.assertEqual(item['probe']['used'],16*len(self.ad['schema']['static']['kept'])+544)
            self.assertEqual(item['order'].tobytes(),old['models'][f'{seed}:S']['order'].tobytes())
        self.assertEqual(ns.encode(self.ad['schema']),ns.encode(old['schema']))

    def test_fit_original_300_eventorders_fresh_adam_final_probe(self):
        self.assertEqual(len(self.final['history']),300);self.assertEqual(self.final['update'],300)
        order=self.ad['models'][f'{p.SEEDS[0]}:L']['order']
        for i,entry in enumerate(self.final['history']):self.assertEqual(entry['ordinals'],order[i].tolist())
        for value in self.final['optimizer'].values():self.assertEqual(float(value['step']),300.)
        self.assertEqual(self.final['final_probe']['used'],self.final['final_probe']['total'])
        self.assertFalse(any(k=='forecast' for k,_,_ in self.fit_sink.records))

    def test_full66_saved_L_law_allreal_parity_bool_coverage(self):
        self.assertEqual(len(self.result['predictions']),66)
        p.validate_population(self.result['predictions'],self.packet,p.SEEDS[0],'L')
        for record in self.result['predictions']:
            p.numeric_evidence(record,self.packet['rows'][record['ordinal']]);s=record['source'];self.assertEqual(s['means'].shape,(60,))
            self.assertAlmostEqual(float(s['noise_probabilities'].sum()),1.,places=12)
            for level in (50,80,95):self.assertIs(type(record['coverage_'+str(level)]),bool)
            self.assertLessEqual(record['diagnostics']['work']['density_points'],1000000)

    def test_score_has_no_optimizer_or_mutation(self):
        with mock.patch.object(torch.optim,'Adam',side_effect=AssertionError('optimizer forbidden')):
            result=p.score_final(self.packet,self.raw,self.pin,self.fit['checkpoint'],self.fit['receipt']['sha256'],self.b,f.Sink(),processing_begin=time.monotonic())
        self.assertEqual(decode(result['result'])['predictions'][0]['source']['means'].tobytes(),self.result['predictions'][0]['source']['means'].tobytes())

    def test_scalar_B1_target_matches_original24_backwards_and_loss_order(self):
        model=p.model_for(self.b,self.ad['schema'],p.SEEDS[0],'L');p.load_state(model,self.ad['models'][f'{p.SEEDS[0]}:L']['initial'])
        ids=self.ad['models'][f'{p.SEEDS[0]}:L']['order'][0]
        values=[];calls=[];original=self.b.kernel.marked_nll
        def traced(prior,marks,coeff,nu,targets,*args,**kw):
            calls.append((len(marks),len(targets)));return original(prior,marks,coeff,nu,targets,*args,**kw)
        with mock.patch.object(self.b.kernel,'marked_nll',side_effect=traced):
            for ordinal in ids:
                row=self.packet['rows'][int(ordinal)]
                for hi in range(3):
                    loss=p.posterior(model,row,hi,self.ad['schema'],self.b,time.monotonic()).nll(torch.tensor(row['mw'],dtype=torch.float64))
                    values.append(float(loss.detach()));(loss/24.).backward()
        self.assertEqual(calls,[(1,1)]*24)
        expected=0.
        for v in values:expected+=v/24.
        self.assertEqual(self.final['history'][0]['loss'],expected)
        norm=float(torch.nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True))
        self.assertEqual(self.final['history'][0]['gradient_norm'],norm)

    def test_future_suffix_cannot_change_early_prior_or_posterior(self):
        row=copy.deepcopy(self.packet['rows'][4]);model=p.model_for(self.b,self.ad['schema'],p.SEEDS[0],'L')
        a=p.posterior(model,row,0,self.ad['schema'],self.b,time.monotonic());row['horizons'][2]['reported'][4:]+=3.
        b=p.posterior(model,row,0,self.ad['schema'],self.b,time.monotonic())
        self.assertTrue(torch.equal(a.logw,b.logw));self.assertTrue(torch.equal(a.mu,b.mu))
        self.assertEqual(a.reference['prior'][1].numpy().tobytes(),b.reference['prior'][1].numpy().tobytes())

    def test_rho0_S_and_noise0_P_fixed_parameter_nulls(self):
        row=self.packet['rows'][4];model=p.model_for(self.b,self.ad['schema'],p.SEEDS[0],'L');ctx=p.context(row,self.ad['schema']['static']);prior=model.prior(ctx)
        coeff=model.coefficients.detach().clone();coeff[:,4]=0;marks=p.tensor(row['horizons'][1]['reported']);nu=p.tensor(row['noise']['nu'])
        l=lm.forecast(f.op,f.kernel,prior,marks,coeff,nu,self.ad['schema']['mref'],3,row['noise']['arrival_offset_ns'],row['mw'],processing_begin=time.monotonic())
        s=f.op.marked(prior,marks,coeff,nu,'S',self.ad['schema']['mref'],processing_begin=time.monotonic())
        torch.testing.assert_close(l.mu,s.mu,rtol=0,atol=2e-14);torch.testing.assert_close(l.logw,s.logw,rtol=0,atol=2e-14)
        zero=torch.zeros_like(nu);l=lm.forecast(f.op,f.kernel,prior,marks,model.coefficients,zero,self.ad['schema']['mref'],3,row['noise']['arrival_offset_ns'],row['mw'],processing_begin=time.monotonic())
        plug=f.op.marked(prior,marks,model.coefficients,zero,'P',self.ad['schema']['mref'],processing_begin=time.monotonic())
        self.assertAlmostEqual(float(l.mean().detach()),float(plug.mean().detach()),places=12)
        self.assertAlmostEqual(float(l.nll(torch.tensor(row['mw'],dtype=torch.float64)).detach()),float(plug.nll(torch.tensor(row['mw'],dtype=torch.float64)).detach()),places=12)

    def test_loading_derivative_first_cell_and_negative_rho(self):
        row=self.packet['rows'][4];model=p.model_for(self.b,self.ad['schema'],p.SEEDS[0],'L');coeff=model.coefficients.detach().clone().requires_grad_();coeff.data[:,4]=torch.tensor([-1.,1.,.4],dtype=torch.float64)
        prior=model.prior(p.context(row,self.ad['schema']['static']));marks=p.tensor(row['horizons'][0]['reported']);nu=p.tensor(row['noise']['nu'])
        result=f.kernel.marked_nll(tuple(v[None,:] for v in prior),(marks,),coeff,nu[None,:,:],torch.tensor([row['mw']],dtype=torch.float64),'L',self.ad['schema']['mref'],(1,),(0,),processing_begin=time.monotonic())
        self.assertTrue(torch.equal(result['loadings'][0],torch.ones(3,dtype=torch.float64)))
        self.assertTrue(torch.equal(result['loadings'][1],1-coeff[:,4]));g=torch.autograd.grad(result['loadings'][1].sum(),coeff)[0]
        self.assertTrue(torch.equal(g[:,4],-torch.ones(3,dtype=torch.float64)))

    def test_nonGaussian_far_modes_and_graded_loading_scoring_parity(self):
        prior=(torch.log(torch.tensor([.05,.1,.7,.1,.05],dtype=torch.float64)),torch.tensor([-25.,-.01,0.,.01,25.],dtype=torch.float64),torch.full((5,),.05,dtype=torch.float64))
        marks=torch.zeros((4,3),dtype=torch.float64);nu=torch.arange(36,dtype=torch.float64).reshape(12,3)/100
        coeff=torch.tensor([[0.,0.,0.,0.,-.7,math.log(math.expm1(.95))]]*3,dtype=torch.float64)
        post=lm.forecast(f.op,f.kernel,prior,marks,coeff,nu,0.,1,0,0.,processing_begin=time.monotonic())
        score=lm.checked_scores(post,0.,f.ar);self.assertLessEqual(score['diagnostics']['errors']['crps'],1e-6)
        self.assertLess(score['quantiles']['0.025'],-24.);self.assertGreater(score['quantiles']['0.975'],24.)
        self.assertIs(type(score['coverage_95']),bool)

    def test_L_gradient_loading_path_matches_finite_difference(self):
        row=self.packet['rows'][4];model=p.model_for(self.b,self.ad['schema'],p.SEEDS[0],'L')
        prior=tuple(v.detach() for v in model.prior(p.context(row,self.ad['schema']['static'])))
        marks=p.tensor(row['horizons'][0]['reported']);nu=p.tensor(row['noise']['nu']);coeff=model.coefficients.detach().clone().requires_grad_()
        def loss(c):
            post=lm.forecast(f.op,f.kernel,prior,marks,c,nu,self.ad['schema']['mref'],1,0,row['mw'],processing_begin=time.monotonic())
            return post.nll(torch.tensor(row['mw'],dtype=torch.float64))
        analytic=torch.autograd.grad(loss(coeff),coeff)[0][0,4].item();step=1e-6
        left=coeff.detach().clone();right=left.clone();left[0,4]-=step;right[0,4]+=step
        numerical=float((loss(right)-loss(left)).detach())/(2*step)
        self.assertAlmostEqual(analytic,numerical,places=6)

    def test_original_trained_checkpoint_or_relabelled_initial_rejected(self):
        original=decode(self.oldraw);original['models'][f'{p.SEEDS[0]}:S']['initial']['coefficients'][0,0]+=.01
        raw=ns.encode(original);b=f.bindings(raw,f.ar)
        with self.assertRaises(p.Failure):p.prepare(self.packet,b,f.Sink(),processing_begin=time.monotonic())
        raw=self.fit['checkpoint'];b=f.bindings(raw,f.ar)
        with self.assertRaises(p.Failure):p.prepare(self.packet,b,f.Sink(),processing_begin=time.monotonic())

    def test_original_train_schema_order_or_archive_hash_rejected(self):
        for field in ('schema','order','pin'):
            original=decode(self.oldraw)
            if field=='schema':original['schema']['static']['mean'][0]+=.1
            if field=='order':original['models'][f'{p.SEEDS[0]}:S']['order'][0,0]=original['models'][f'{p.SEEDS[0]}:S']['order'][0,1]
            raw=ns.encode(original);b=f.bindings(raw,f.ar)
            if field=='pin':b=p.Bindings(b.operator,b.native_validator,b.reference,b.kernel,b.source_pins,b.original_admission_raw,'0'*64,b.original_source_pins)
            with self.assertRaises(p.Failure):p.prepare(self.packet,b,f.Sink(),processing_begin=time.monotonic())

    def test_no_cohort_censor_repair_DEV_learning_or_TEST(self):
        for change in ('censor','roster','TEST'):
            pkt=copy.deepcopy(self.packet)
            if change=='censor':pkt['rows'][4]['horizons'][0]['censor'][0,0]=1
            if change=='roster':pkt['rows'][4]['common']=False
            if change=='TEST':pkt['rows'][4]['partition']='TEST'
            with self.assertRaises(p.Failure):p.prepare(pkt,self.b,f.Sink(),processing_begin=time.monotonic())
        changed=copy.deepcopy(self.packet)
        for r in changed['rows']:
            if r['common'] and r['partition']=='DEV':r['mw']+=.9;r['precontext'][8]+=.4
        self.assertEqual(ns.encode(p.current_schema(changed,self.b)),ns.encode(self.ad['schema']))

    def test_initial_callback_rejection_prevents_optimizer(self):
        with mock.patch.object(torch.optim,'Adam',side_effect=AssertionError('forbidden')):
            with self.assertRaises(p.Failure) as err:p.fit_one(self.packet,self.raw,self.pin,self.b,f.Sink('begin_fit'),seed=p.SEEDS[0],arm='L',processing_begin=time.monotonic())
        self.assertEqual(err.exception.evidence['update'],0)

    def test_partial_step_failure_retains_exact_parameters_optimizer_history(self):
        with self.assertRaises(p.Failure) as err:p.fit_one(self.packet,self.raw,self.pin,self.b,f.Sink('step',2),seed=p.SEEDS[0],arm='L',processing_begin=time.monotonic())
        e=err.exception.evidence;self.assertEqual(e['update'],2);self.assertEqual(len(e['history']),2);self.assertIn('partial_gradients',e)
        for entry in e['optimizer'].values():self.assertEqual(float(entry['step']),2.)

    def test_partial_score_failure_retains_complete_source_and_current_evidence(self):
        with self.assertRaises(p.Failure) as err:p.score_final(self.packet,self.raw,self.pin,self.fit['checkpoint'],self.fit['receipt']['sha256'],self.b,f.Sink('forecast'),processing_begin=time.monotonic())
        e=err.exception.evidence;self.assertEqual(len(e['predictions']),1);self.assertEqual(e['current_record']['source']['reference']['arm'],'L');self.assertIn('current_work',e)

    def test_numeric_rejection_not_fallback(self):
        def reject(ref,budget):raise ValueError('invented independent numerical rejection')
        b=p.Bindings(self.b.operator,self.b.native_validator,type('Reference',(),{'complete':staticmethod(reject)}),self.b.kernel,self.b.source_pins,self.oldraw,ns.digest(self.oldraw),self.b.original_source_pins)
        with self.assertRaises(p.Failure) as err:p.score_final(self.packet,self.raw,self.pin,self.fit['checkpoint'],self.fit['receipt']['sha256'],b,f.Sink(),processing_begin=time.monotonic())
        self.assertEqual(len(err.exception.evidence['predictions']),0);self.assertIsNotNone(err.exception.evidence['current_record']['source'])

    def test_deadline_strict_shared_budget_and_invalid_identity(self):
        with self.assertRaises(p.Failure):p.prepare(self.packet,self.b,f.Sink(),processing_begin=time.monotonic()-301)
        with self.assertRaises(p.Failure):p.fit_one(self.packet,self.raw,self.pin,self.b,f.Sink(),seed=p.SEEDS[0],arm='S',processing_begin=time.monotonic())
        b=lm.SharedBudget(time.monotonic());b.charge(1000000,1)
        with self.assertRaises(ValueError):b.charge(1,0)
        self.assertEqual(b.points,1000000)
        with self.assertRaises(ValueError):lm.SharedBudget(time.monotonic()-11)

    def test_tampered_loading_lag_noise_bool_and_normalization_rejected(self):
        original=self.result['predictions'][0]
        for key in ('loading','previous','noise','coverage','normalization'):
            r=copy.deepcopy(original)
            if key in ('loading','previous'):r['source']['reference']['facts'][1][key][0]+=.1
            if key=='noise':r['source']['noise_probabilities'][0]+=.1
            if key=='coverage':r['coverage_80']=float(r['coverage_80'])
            if key=='normalization':r['source']['log_weights']+=.01
            with self.assertRaises(p.Failure):p.validate_forecast(r)

    def test_final_299_or_source_packet_mutation_rejected(self):
        c=copy.deepcopy(self.final);c['update']=299;raw=ns.encode(c)
        with self.assertRaises(p.Failure):p.score_final(self.packet,self.raw,self.pin,raw,ns.digest(raw),self.b,f.Sink(),processing_begin=time.monotonic())
        pkt=copy.deepcopy(self.packet);pkt['rows'][4]['mw']+=.1
        with self.assertRaises(p.Failure):p.bind_admission(pkt,self.raw,self.pin,self.b,time.monotonic())

    def test_inherited_training_loop_bytes_unchanged_except_identity_and_bridge(self):
        original=Path(__file__).parent/'reference/original_processor.py';a=original.read_text();b=Path(p.__file__).read_text()
        first='def fit_one(';last='def export_numeric('
        self.assertEqual(a[a.index(first):a.index(last)],b[b.index(first):b.index(last)])
        self.assertEqual(a[a.index('def gradient_probe('):a.index('def prepare(')],b[b.index('def gradient_probe('):b.index('def current_schema(')])
        self.assertEqual(a[a.index('def optimizer_state('):a.index('def fit_one(')],b[b.index('def optimizer_state('):b.index('def fit_one(')])

    def test_independent_rejected_IEEE_and_partial_fields_are_retained(self):
        row=self.packet['rows'][41];model=p.model_for(self.b,self.ad['schema'],p.SEEDS[0],'L')
        post=p.posterior(model,row,0,self.ad['schema'],self.b,time.monotonic())
        mix=f.ar.complete(lm.arrays(post.reference),post.budget)
        def reject(target):
            exc=f.proper.AuditFailure('nll_representation')
            exc.numeric_evidence={'candidate_float64_hex':'000000000000f07f','bound_float64_hex':'0000000000000000'}
            raise exc
        mix.nll=reject
        with mock.patch.object(f.ar,'complete',return_value=mix):
            with self.assertRaises(lm.ScoringFailure) as err:lm.checked_scores(post,row['mw'],f.ar)
        e=err.exception.evidence;self.assertIn('mean',e['independent_scores']);self.assertIn('median',e['independent_scores'])
        self.assertEqual(e['rejected_numeric']['candidate_float64_hex'],'000000000000f07f')
        self.assertEqual(e['independent_scores']['rejected_nll'],e['rejected_numeric'])
        self.assertIn('independent_posterior',e);self.assertEqual(e['phase'],'independent_scores')

    def test_numerical_parity_rejection_retains_both_scores_errors(self):
        row=self.packet['rows'][41];model=p.model_for(self.b,self.ad['schema'],p.SEEDS[0],'L');post=p.posterior(model,row,0,self.ad['schema'],self.b,time.monotonic())
        mix=f.ar.complete(lm.arrays(post.reference),post.budget);original=mix.scores
        def change(target,**kwargs):
            score=original(target,**kwargs);score['mean']+=.1;return score
        mix.scores=change
        with mock.patch.object(f.ar,'complete',return_value=mix):
            with self.assertRaises(lm.ScoringFailure) as err:lm.checked_scores(post,row['mw'],f.ar)
        e=err.exception.evidence;self.assertEqual(e['phase'],'parity');self.assertGreater(e['errors']['mean'],.09)
        self.assertIn('crps',e['primary_scores']);self.assertIn('crps',e['independent_scores']);self.assertIn('quantiles',e['errors'])

    def comparators(self):
        new=[];reused=[];strong=[]
        for seed in p.SEEDS:
            for arm in ('L','S','P','D','B','F','H','T'):
                rec=copy.deepcopy(self.result);rec.update(seed=seed,arm=arm)
                for v in rec['predictions']:v.update(seed=seed,arm=arm)
                if arm=='L':new.append(rec)
                else:
                    rec['independent_closure']=dict(verified=True,no_optimizer=True,checkpoint_sha256=rec['checkpoint_sha256'],source_sha256='a'*64,packet_sha256=rec['packet_sha256'],independent_audit_sha256='b'*64)
                    rec['origin']={'original_closure_proof_pin':dict(bytes=1,sha256='b'*64)}
                    if arm in ('S','P','D'):
                        rec.update(admission_sha256=self.b.original_admission_pin,source_pins=self.b.original_source_pins);reused.append(rec)
                    else:strong.append(rec)
        return new,reused,strong

    def test_aggregate42_guards_retains1056_origins_and_negative(self):
        new,reused,strong=self.comparators()
        result=p.aggregate(self.packet,self.raw,self.pin,new,reused,strong,self.b,processing_begin=time.monotonic())
        self.assertEqual(result['status'],'complete');self.assertFalse(result['pass_all']);self.assertEqual(len(result['original24'])+len(result['additional18']),42)
        self.assertEqual(result['record_counts']['total'],1056);self.assertEqual(len(result['origins']),14);self.assertEqual(len(result['paired_L_minus_S']),6)
        reused[0]['independent_closure']['verified']=False
        self.assertEqual(p.aggregate(self.packet,self.raw,self.pin,new,reused,strong,self.b,processing_begin=time.monotonic())['status'],'incomplete')
    def test_bootstrap_deadline_retains_completed_panels_current_draws_metrics_origins(self):
        new,reused,strong=self.comparators();real=p.desc.paired;count=[0]
        def interrupted(a,b,tick,evidence):
            count[0]+=1
            if count[0]==1:return real(a,b,tick,evidence)
            evidence.update(completed=3,draws={'mae':[.1,.2,.3]},support={'mae':22})
            raise p.Failure('source_deadline')
        with mock.patch.object(p.desc,'paired',side_effect=interrupted):
            out=p.aggregate(self.packet,self.raw,self.pin,new,reused,strong,self.b,processing_begin=time.monotonic())
        self.assertEqual(out['status'],'incomplete');self.assertFalse(out['pass_all']);self.assertEqual(len(out['metrics']),16);self.assertEqual(len(out['origins']),14)
        self.assertEqual(list(out['paired_L_minus_S']),[f'{p.SEEDS[0]}:1']);self.assertEqual(out['bootstrap_progress']['horizon'],3)
        self.assertEqual(out['bootstrap_progress']['evidence']['completed'],3);self.assertEqual(out['bootstrap_progress']['evidence']['draws']['mae'],[.1,.2,.3])


if __name__=='__main__':unittest.main()
