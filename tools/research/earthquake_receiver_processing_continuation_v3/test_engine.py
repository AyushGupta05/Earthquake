"""Invented callbacks/forward stubs only: never real optimizer steps or actual data."""
import ast
import time
import unittest
from unittest.mock import patch,Mock
from types import SimpleNamespace
from pathlib import Path
import numpy as np
import torch
import engine as e


def admit(optional=False):
    counts={'B':5007,'F':5147,'H':5125,'T':5125,'C':5125}
    return dict(schema='receiver-continuation-admission-v3',original_replay_verified=True,source_runtime_verified=True,resource_verified=True,capacity={'counts':counts,'nonzero_TRAIN_probe_gradient_degrees':dict(counts)},scorer_mode='reviewed_optional' if optional else 'original',scorer_binding='invented-pinned',optional_scorer_verified=optional)


def histories():
    return [dict(update=i,base_nll=1.,sequence_nll=1.,joint_or_conditional_nll=1.,gradient_norm=1.,base_gradient_norm=1.,sequence_gradient_norm=1.,seconds=1.) for i in range(1,301)]


class FakeNet:
    def __init__(self,arm,mean):self.arm=arm;self.weight=torch.tensor([1.]);self.loaded=False
    def initialize(self,*_):pass
    def parameters(self):return [self.weight]
    def state_dict(self):return {'weight':self.weight}
    def load_state_dict(self,state,strict):self.weight=state['weight'];self.loaded=True
    def eval(self):pass
    def current(self,*_):return torch.zeros(1,15)
    def initial(self,*_):return torch.zeros(1,15),torch.zeros(1,36)


def fixture():
    rows=[]
    for i in range(87):
        ctx=np.zeros(35);ctx[15]=1
        rows.append(dict(mw=5.,group=i,initial={'context':ctx},horizons=[{'rate':[100,1]} for _ in (1,3,5)]))
    packet={'rows':rows};stats={'initial_mean':np.zeros(35),'initial_std':np.ones(35),'current_mean':np.zeros(36),'current_std':np.ones(36)}
    density=SimpleNamespace(mean_action=lambda *_:5.,quantile=lambda *_:5.,nll=lambda *_:1.,crps=lambda *_:.2,cdf=lambda *_:.5)
    mixture=SimpleNamespace(from_raw=lambda _:SimpleNamespace(weights=np.ones(5)/5,means=np.ones(5)*5,sigmas=np.ones(5)))
    pilot=SimpleNamespace(SEEDS=e.SEEDS,ARMS=e.ARMS,HORIZONS=e.HORIZONS,UPDATES=300,validate=lambda _:{'TRAIN':list(range(65)),'DEV':list(range(65,87))},scaler=lambda *_:stats,batch=lambda *_:(torch.zeros(1),)*4,state_batch=lambda *_:(torch.ones(1,2,dtype=torch.int64),torch.ones(1,2,dtype=torch.bool)),core=SimpleNamespace(Mixture=mixture,NumericalFailure=ValueError),density=density,metrics=lambda _:dict(invented=1),strata=lambda _:dict(invented=1),numerical=lambda *_:(_ for _ in ()).throw(RuntimeError('invented_score_failure')))
    deps=SimpleNamespace(pilot=pilot,models=SimpleNamespace(Net=FakeNet,nll=lambda *_:None),torch=torch)
    def anchor(seed,arm):
        return dict(schema='receiver-final-anchor-v3',seed=seed,arm=arm,kind='original_final' if (seed,arm) in e.ORIGINAL else 'v3_final',state={'weight':np.asarray([2.],dtype=np.float32)},scalers=stats,history=histories(),mref=5.,train_population_std=0.,retained_predictions=[dict(invented=True)]*(66 if arm in ('B','F') else 46) if (seed,arm) in e.ORIGINAL else [])
    return packet,deps,anchor


def accepted():
    numeric=dict(accepted=True,errors={k:0. for k in ('log_normalizer','mean','nll')},torch_errors={'64':0.,'128':0.},base_raw=[0.]*15,z=[0.]*36,c=[0.]*35,states=[1,1],hazard={'alpha':[0.,0.],'beta':[0.,0.],'gamma':[0.,0.],'extra':[0.,0.],'z_weights':[[0.]*36 for _ in range(2)],'c_weights':[[0.]*35 for _ in range(2)]},mref=5.,integrals={key:dict(method=method,log_normalizer=0.,mean=5.,nll=1.) for key,method in (('gh64','GH64'),('gh128','GH128'),('adaptive','adaptive'))})
    score=dict(mean=5.,median=5.,nll=1.,crps=.2,pit=.5,coverage_50=True,coverage_80=True,coverage_95=True,quantiles={k:5. for k in ('0.025','0.1','0.25','0.5','0.75','0.9','0.975')})
    return score,numeric


class EngineTests(unittest.TestCase):
    def clocks(self):return dict(processing_begin=time.monotonic(),experiment_begin=time.monotonic()-1)
    def test_exact_identity_roster(self):
        self.assertEqual(e.ORIGINAL,((20261012,'B'),(20261012,'F'),(20261012,'H')))
        self.assertEqual(e.FRESH,((20261012,'T'),(20261012,'C'),(20261013,'B'),(20261013,'F'),(20261013,'H'),(20261013,'T'),(20261013,'C')))
        for bad in (True,20261014):
            with self.assertRaises(ValueError):e.identity(bad,'C')
    def test_original_train_denied_before_claim_read_or_optimizer(self):
        with patch.object(torch.optim,'Adam',side_effect=AssertionError('optimizer')):
            r=e.train_stage(None,20261012,'B',None,lambda *_:self.fail('claim'),lambda *_:self.fail('checkpoint'),admission=admit(),**self.clocks())
        self.assertEqual(r['status'],'incomplete');self.assertEqual(r['exception_reason'],'identity')
    def test_failed_claim_precedes_packet_model_and_callbacks(self):
        r=e.score_stage(None,20261012,'H',None,lambda *_:False,lambda *_:self.fail('read'),admission=admit(),**self.clocks())
        self.assertEqual(r['exception_reason'],'claim_denied');self.assertNotIn('fit',r)
    def test_parent_replay_gate_precedes_claim(self):
        a=admit();a['original_replay_verified']=False
        r=e.score_stage(None,20261012,'B',None,lambda *_:self.fail('claim'),lambda *_:self.fail('read'),admission=a,**self.clocks());self.assertEqual(r['exception_reason'],'parent_gate')
    def test_existing_score_no_optimizer_checkpoint_or_mutation(self):
        packet,deps,reader=fixture();anchor=reader(20261012,'B');calls=[]
        with patch.object(torch.optim,'Adam',side_effect=AssertionError('optimizer')):
            r=e.score_stage(packet,20261012,'B',deps,lambda *a:calls.append(a) or True,lambda *_:anchor,prediction=lambda *_:None,admission=admit(),**self.clocks())
        self.assertEqual(r['status'],'complete');self.assertEqual(len(r['fit']['predictions']),66);self.assertIs(r['retained_anchor_predictions'],anchor['retained_predictions']);self.assertEqual(anchor['state']['weight'][0],2.);self.assertEqual(calls,[(20261012,'B','scoring')])
    def test_partial_score_callback_failure_preserves_first_record_no_retry(self):
        packet,deps,reader=fixture();calls=[]
        def broken(*args):calls.append(args);raise OSError('durable invented failure')
        r=e.score_stage(packet,20261012,'F',deps,lambda *_:True,reader,prediction=broken,admission=admit(),**self.clocks());self.assertEqual(r['status'],'incomplete');self.assertEqual(len(calls),1);self.assertEqual(len(r['fit']['predictions']),1);self.assertEqual(len(r['fit']['history']),300)
    def test_numerical_failure_preserves_current_raw_state_and_no_fallback(self):
        packet,deps,reader=fixture()
        r=e.score_stage(packet,20261012,'H',deps,lambda *_:True,reader,admission=admit(),**self.clocks());self.assertEqual(r['status'],'incomplete');self.assertEqual(len(r['fit']['numerical_failures']),1);self.assertEqual(r['fit']['numerical_failures'][0]['base_raw'],[0.]*15)
    def test_optional_gate_rejects_without_default_fallback(self):
        packet,deps,reader=fixture();a=admit();a['scorer_mode']='reviewed_optional'
        r=e.score_stage(packet,20261012,'H',deps,lambda *_:self.fail('claim'),reader,scorer=lambda *_:self.fail('score'),admission=a,**self.clocks());self.assertEqual(r['exception_reason'],'optional_scorer_gate')
    def test_supplied_optional_scorer_has_no_fallback(self):
        packet,deps,reader=fixture();calls=[]
        def bad(*args):calls.append(args);raise ValueError('rejected invented scorer')
        r=e.score_stage(packet,20261012,'H',deps,lambda *_:True,reader,scorer=bad,admission=admit(True),**self.clocks());self.assertEqual(len(calls),1);self.assertEqual(r['status'],'incomplete')
    def test_training_failure_retains_diagnostic_state_without_real_optimizer(self):
        packet,deps,_=fixture();calls=[]
        def order(*_):raise ValueError('invented before first update')
        deps.pilot.event_order=order
        with patch.object(torch.optim,'Adam',return_value=Mock()):
            r=e.train_stage(packet,20261012,'C',deps,lambda *_:True,lambda *args:calls.append(args),admission=admit(),**self.clocks())
        self.assertEqual(r['status'],'incomplete');self.assertEqual(len(calls),1);self.assertEqual(r['fit']['failure_checkpoint']['status'],'saved_failed_fit');self.assertEqual(r['fit']['history'],[])
    def test_checkpoint_failure_not_retried_or_overwritten(self):
        calls=[]
        def broken(*_):calls.append(1);raise OSError('invented')
        self.assertEqual(e.retained_checkpoint(broken,1,'C',FakeNet('C',5),{},False,False)['status'],'checkpoint_callback_failed');self.assertEqual(len(calls),1)
        for attempted,saved in ((True,False),(True,True)):
            e.retained_checkpoint(lambda *_:self.fail('retry'),1,'C',FakeNet('C',5),{},attempted,saved)
    def test_source_and_whole_deadline_bounds(self):
        with patch.object(e.time,'monotonic',return_value=8000.):
            for args in ((7699.,7698.,300),(7099.,7098.,900),(7999.,0.,900)):
                with self.assertRaises(RuntimeError):e.tick(*args)
            e.tick(7700.,7699.,300)
            e.tick(7100.,7099.,900)
    def test_scaler_or_identity_anchor_mismatch_denied(self):
        packet,deps,reader=fixture();a=reader(20261012,'B');a['scalers']=dict(a['scalers']);a['scalers']['initial_mean']=np.ones(35)
        r=e.score_stage(packet,20261012,'B',deps,lambda *_:True,lambda *_:a,admission=admit(),**self.clocks());self.assertEqual(r['exception_reason'],'anchor_scalers')
    def test_score_nonfinite_and_parity_veto(self):
        score=dict(mean=float('inf'),median=0.,nll=0.,crps=0.,pit=.5,coverage_50=True,coverage_80=True,coverage_95=True)
        with self.assertRaises(ValueError):e.score_checked(score,{},False)
        with self.assertRaises(ValueError):e.finite_record({'saved':float('nan')})
    def test_aggregate_missing_stages_retains_inputs_and_cannot_advance(self):
        packet,deps,_=fixture();stages=[]
        r=e.aggregate(packet,stages,deps,admission=admit(),**self.clocks());self.assertFalse(r['advance']['pass_all']);self.assertIs(r['retained_stage_results'],stages);self.assertEqual(r['status'],'incomplete')
    def test_training_loop_semantics_identical_to_original_ast(self):
        root=Path(__file__).parent
        original=ast.parse((root/'candidate_pilot.py').read_text());new=ast.parse((root/'engine.py').read_text())
        original_loop=next(n for n in ast.walk(original) if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple) and [getattr(v,'id',None) for v in n.target.elts]==['update','ids'])
        new_loop=next(n for n in ast.walk(new) if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple) and [getattr(v,'id',None) for v in n.target.elts]==['update','ids'])
        class Normalize(ast.NodeTransformer):
            def visit_Call(self,n):
                self.generic_visit(n)
                if isinstance(n.func,ast.Name) and n.func.id=='check':n.func.id='tick'
                return n
            def visit_Attribute(self,n):
                self.generic_visit(n)
                if isinstance(n.value,ast.Name) and n.value.id=='p' and n.attr in ('batch','state_batch','event_order'):return ast.copy_location(ast.Name(id=n.attr,ctx=ast.Load()),n)
                return n
        self.assertEqual(ast.dump(Normalize().visit(new_loop),include_attributes=False),ast.dump(original_loop,include_attributes=False))
        source=(root/'engine.py').read_text();self.assertIn('lr=1e-3,weight_decay=0',source);self.assertIn('net.initialize(mean,std)',source);self.assertIn('clip_grad_norm_(net.parameters(),5)',source)
    def test_all_ten_scoring_stages_aggregate_exact24_original_comparisons(self):
        packet,deps,reader=fixture();deps.pilot.numerical=lambda *_:accepted();stages=[]
        for seed,arm in e.IDENTITIES:
            stage=e.score_stage(packet,seed,arm,deps,lambda *_:True,reader,admission=admit(),**self.clocks());self.assertEqual(stage['status'],'complete');stages.append(stage)
        calls=[]
        deps.pilot.paired_intervals=lambda left,right,tick:calls.append((len(left),len(right))) or {'unchanged':True}
        deps.pilot.diagnostics=lambda _:{'invented':True};deps.pilot.advance=lambda fits:{'pass_all':False,'checks':['unchanged']}
        deps.pilot.observations=SimpleNamespace(canonical=lambda _:b'bounded')
        result=e.aggregate(packet,stages,deps,admission=admit(),**self.clocks())
        self.assertEqual(result['status'],'complete');self.assertEqual(len(result['fits']),10);self.assertEqual(len(result['comparisons']),24);self.assertEqual(calls,[(22,22)]*24);self.assertEqual(result['advance']['checks'],['unchanged']);self.assertIs(result['retained_stage_results'],stages)
    def test_aggregate_wrong_identity_or_scorer_binding_retains_all_input(self):
        packet,deps,_=fixture();stages=[dict(status='complete',stage='scoring',seed=1,arm='C') for _ in range(10)]
        result=e.aggregate(packet,stages,deps,admission=admit(),**self.clocks());self.assertIs(result['retained_stage_results'],stages);self.assertFalse(result['advance']['pass_all'])
    def test_optional_parity_failure_preserves_rejected_record(self):
        packet,deps,reader=fixture();score,numeric=accepted();numeric['errors']['mean']=.01
        r=e.score_stage(packet,20261012,'H',deps,lambda *_:True,reader,scorer=lambda *_:(score,numeric),admission=admit(True),**self.clocks())
        self.assertEqual(r['status'],'incomplete');self.assertEqual(r['fit']['numerical_failures'][0]['reason'],'score_contract');self.assertIs(r['fit']['numerical_failures'][0]['numerical'],numeric)
    def test_anchor_state_dtype_or_history_completion_rejected(self):
        packet,deps,reader=fixture()
        for change in ('dtype','history','kind'):
            anchor=reader(20261013,'C')
            if change=='dtype':anchor['state']['weight']=np.zeros(1,dtype=np.float64)
            elif change=='history':anchor['history']=anchor['history'][:-1]
            else:anchor['kind']='original_final'
            result=e.score_stage(packet,20261013,'C',deps,lambda *_:True,lambda *_:anchor,admission=admit(),**self.clocks());self.assertEqual(result['status'],'incomplete');self.assertNotIn('fit',result)
    def test_clock_expires_during_score_retains_current_prediction(self):
        packet,deps,reader=fixture();clock=self.clocks();calls=[]
        def durable(*args):calls.append(args);clock['expire']=True
        real_tick=e.tick
        def ticking(begin,experiment,limit):
            if clock.get('expire'):raise RuntimeError('renewal_deadline')
            return real_tick(begin,experiment,limit)
        with patch.object(e,'tick',side_effect=ticking):
            result=e.score_stage(packet,20261012,'B',deps,lambda *_:True,reader,prediction=durable,admission=admit(),processing_begin=clock['processing_begin'],experiment_begin=clock['experiment_begin'])
        self.assertEqual(result['status'],'incomplete');self.assertEqual(len(calls),1);self.assertEqual(len(result['fit']['predictions']),1)
    def test_optional_record_method_shape_and_text_limits(self):
        score,numeric=accepted();e.score_checked(score,numeric,True)
        numeric['integrals']['gh64']['method']='gh64'
        with self.assertRaises(ValueError):e.score_checked(score,numeric,True)
        with self.assertRaises(ValueError):e.finite_record({'text':'x'*129})

    def test_BF_mixture_and_analytic_failures_retain_current_raw(self):
        for arm,mode in (('B','mixture'),('F','analytic')):
            packet,deps,reader=fixture();calls=[]
            def rejected(*_):calls.append(1);raise ValueError('invented analytic failure')
            if mode=='mixture':deps.pilot.core.Mixture.from_raw=rejected
            else:deps.pilot.density.crps=rejected
            result=e.score_stage(packet,20261012,arm,deps,lambda *_:True,reader,admission=admit(),**self.clocks())
            self.assertEqual(result['status'],'incomplete');self.assertEqual(len(calls),1);record=result['fit']['numerical_failures'][0];self.assertEqual(record['base_raw'],[0.]*15);self.assertEqual((record['ordinal'],record['horizon']),(65,1));self.assertFalse(record['accepted'])
    def test_failed_nonfinite_raw_is_explicit_transportable_diagnostic(self):
        import json
        packet,deps,reader=fixture()
        class NonfiniteNet(FakeNet):
            def current(self,*_):return torch.tensor([[float('nan'),float('inf'),-float('inf')]+[0.]*12])
        deps.models.Net=NonfiniteNet
        def reject(*_):raise ValueError('nonfinite')
        deps.pilot.core.Mixture.from_raw=reject
        result=e.score_stage(packet,20261012,'B',deps,lambda *_:True,reader,admission=admit(),**self.clocks());record=result['fit']['numerical_failures'][0]
        self.assertEqual(record['base_raw'][:3],['NaN','+Infinity','-Infinity']);json.dumps(record,allow_nan=False);self.assertFalse(record['accepted'])

    def test_score_function_contains_no_optimizer_or_checkpoint(self):
        tree=ast.parse((Path(__file__).parent/'engine.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='score_stage')
        names={n.id for n in ast.walk(node) if isinstance(n,ast.Name)};attrs={n.attr for n in ast.walk(node) if isinstance(n,ast.Attribute)}
        self.assertNotIn('optimizer',names);self.assertNotIn('checkpoint',names);self.assertNotIn('Adam',attrs);self.assertNotIn('step',attrs)


if __name__=='__main__':unittest.main()
