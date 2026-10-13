"""Invented density/tensor tests; no optimizer, IO to actual inputs or cloud."""
import math
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import torch
import adapter
import candidate_core as core
import candidate_models as models
import fast_scorer as fast
import fast_reference as reference
with patch.dict(sys.modules,{'numerical_core':core}):
    import candidate_scores as original_scores


def example(arm='C',states=(1,1,0,0,1)):
    torch.manual_seed(73);net=models.Net(arm,.5)
    with torch.no_grad():
        net.hazards.alpha.copy_(torch.tensor([-.2,-.3]));net.hazards.beta.copy_(torch.tensor([.15,-.13]));net.hazards.gamma.copy_(torch.tensor([.1,-.12]));net.hazards.extra.copy_(torch.tensor([.05,-.04]));net.hazards.z_weights.fill_(.005);net.hazards.c_weights.fill_(-.005)
    raw=torch.tensor([[-.5,.3,.2,-.1,.1,-2.,-.8,.5,1.7,3.,.2,.1,-.1,.3,0.]],dtype=torch.float32)
    z=torch.linspace(-.4,.4,36)[None,:];ctx=torch.linspace(.3,-.2,35)[None,:];state=torch.tensor([list(states)],dtype=torch.int64);mask=torch.ones_like(state,dtype=torch.bool)
    deps=SimpleNamespace(core=core,models=models,torch=torch,fast_scorer=fast)
    return deps,net,raw,z,ctx,state,mask


def extracted(net,raw,z,ctx,states):
    h=net.hazards;hz=core.Hazard(net.arm,*[getattr(h,k).detach().double().numpy() for k in adapter.HAZARD_FIELDS],h.mref)
    return core.Mixture.from_raw(raw[0].double().numpy()),hz,z[0].double().numpy(),ctx[0].double().numpy(),states[0].tolist()


def run_example(values,target=.7,tick=lambda:None):
    deps,net,raw,z,c,states,mask=values
    with patch.dict(sys.modules,{'reference':reference}):
        return adapter.make_adapter(deps)(net,raw,z,c,states,mask,target,tick)


class AdapterTests(unittest.TestCase):
    def test_signed_factors_equal_original_likelihood_all_three_arms(self):
        for arm in ('C','T','H'):
            _,net,raw,z,c,states,_=example(arm);_,hz,zv,cv,sv=extracted(net,raw,z,c,states);factors=adapter.affine_factors(core,hz,zv,cv,sv)
            grid=np.asarray([-30.,-3.,0.,4.,40.]);got=-np.logaddexp(0,-(np.asarray(factors)[:,0]+grid[:,None]*np.asarray(factors)[:,1])).sum(1)
            np.testing.assert_allclose(got,core.log_likelihood(grid,hz,zv,cv,sv),rtol=1e-13,atol=1e-13)
    def test_C_T_same_initial_run_and_reset_difference(self):
        pairs=[]
        for arm in ('C','T'):
            _,n,r,z,c,s,_=example(arm,(1,1,1,1,1));_,h,zv,cv,sv=extracted(n,r,z,c,s);pairs.append(adapter.affine_factors(core,h,zv,cv,sv))
        self.assertEqual(pairs[0],pairs[1])
        pairs=[]
        for arm in ('C','T'):
            _,n,r,z,c,s,_=example(arm,(1,0,0,1,1));_,h,zv,cv,sv=extracted(n,r,z,c,s);pairs.append(adapter.affine_factors(core,h,zv,cv,sv))
        self.assertNotEqual(pairs[0],pairs[1])
    def test_H_initial_interaction_not_run_age(self):
        _,n,r,z,c,s,_=example('H');_,h,zv,cv,sv=extracted(n,r,z,c,s)
        idx,y,u,age=core.transitions(sv);common=h.alpha+h.z_weights@zv+h.c_weights@cv
        expected=common[idx]+h.gamma[idx]*np.log1p(u)+(h.extra*np.asarray([zv[0]*zv[1],zv[0]*cv[0]]))[idx]-h.mref*h.beta[idx]
        np.testing.assert_allclose(h.logits(0.,zv,cv,idx,u,age),expected)
        np.testing.assert_array_equal(h.logits(0.,zv,cv,idx,u,age),h.logits(0.,zv,cv,idx,u,np.ones_like(age)))
    def test_no_edges_for_first_cell_and_no_appended_exit(self):
        _,n,r,z,c,s,_=example('C',(1,));_,h,zv,cv,sv=extracted(n,r,z,c,s);self.assertEqual(adapter.affine_factors(core,h,zv,cv,sv),[])
        for length in range(1,21):
            self.assertEqual(len(adapter.affine_factors(core,h,zv,cv,[1]*length)),length-1)
    def test_fast_proper_score_matches_original_nonGaussian_allreal_reference(self):
        values=example();score,record=run_example(values);self.assertIsNotNone(score,record)
        _,net,raw,z,c,states,_=values;mix,h,zv,cv,sv=extracted(net,raw,z,c,states);checked=core.checked_inference(mix,h,zv,cv,sv,.7)
        reference_score=original_scores.scores(mix,h,zv,cv,sv,.7,checked,lambda:None)
        self.assertTrue(record['accepted']);self.assertEqual(set(record),{'accepted','errors','torch_errors','base_raw','z','c','states','hazard','mref','integrals'})
        self.assertEqual(score['mean'],checked['gh64'].mean);self.assertEqual(score['nll'],checked['gh64'].nll)
        for key in ('crps','median','pit'):self.assertLessEqual(abs(score[key]-reference_score[key]),1e-6)
        for key in adapter.QUANTILES:self.assertLessEqual(abs(score['quantiles'][key]-reference_score['quantiles'][key]),1e-6)
        self.assertTrue(all(type(score['coverage_'+str(k)]) is bool for k in (50,80,95)))
    def test_factorization_preserves_allreal_normalizer_all_three_arms(self):
        for arm in ('H','T','C'):
            _,net,raw,z,c,states,_=example(arm);mix,h,zv,cv,sv=extracted(net,raw,z,c,states);checked=core.checked_inference(mix,h,zv,cv,sv,.7)
            factors=adapter.affine_factors(core,h,zv,cv,sv);independent=reference.Posterior(mix.weights.tolist(),mix.means.tolist(),mix.sigmas.tolist(),factors)
            try:
                self.assertLessEqual(abs(independent.log_normalizer-checked['adaptive'].log_normalizer),1e-10);self.assertLessEqual(abs(independent.mean-checked['adaptive'].mean),1e-10);self.assertLessEqual(abs(-independent.log_pdf(.7)-checked['adaptive'].nll),1e-10)
            finally:independent._cdf_cache.clear();independent.components.clear()

    def test_sharp_GH_rejection_never_calls_fast(self):
        values=list(example('C',(0,1)));deps,net=values[:2]
        with torch.no_grad():net.hazards.beta.copy_(torch.tensor([80.,-80.]))
        calls=[];deps.fast_scorer=SimpleNamespace(score=lambda *_args,**_kwargs:calls.append(1))
        score,record=run_example(tuple(values));self.assertIsNone(score);self.assertFalse(record['accepted']);self.assertEqual(calls,[]);self.assertEqual(len(record['base_raw']),15)
    def test_first_external_tick_failure_has_complete_parameters(self):
        def denied():raise RuntimeError('invented tick failure')
        score,record=run_example(example(),tick=denied);self.assertIsNone(score);self.assertEqual(len(record['base_raw']),15);self.assertEqual(len(record['z']),36);self.assertEqual(len(record['c']),35);self.assertEqual(set(record['hazard']),set(adapter.HAZARD_FIELDS));self.assertEqual(record['fast_diagnostics'],{'status':'not_called'})
    def test_fast_failure_evidence_retained_without_retry(self):
        values=list(example());deps=values[0];calls=[]
        def failed(*args,**kwargs):calls.append(kwargs);raise fast.NumericalFailure('invented',{'retained':1.})
        deps.fast_scorer=SimpleNamespace(score=failed);score,record=run_example(tuple(values));self.assertIsNone(score);self.assertEqual(len(calls),1);self.assertEqual(calls[0]['tolerance'],1e-6);self.assertEqual(calls[0]['budget_seconds'],10);self.assertIs(calls[0]['require_gh'],True);self.assertIs(calls[0]['gradients'],False);self.assertEqual(record['fast_diagnostics']['evidence'],{'retained':1.})
    def test_returned_fast_evidence_survives_final_tick_failure(self):
        values=list(example());deps=values[0];real=fast.score;returned=[]
        def wrapped(*a,**k):value=real(*a,**k);returned.append(value);return value
        deps.fast_scorer=SimpleNamespace(score=wrapped)
        def tick():
            if returned:raise RuntimeError('invented final tick')
        score,record=run_example(tuple(values),tick=tick);self.assertIsNone(score);self.assertTrue(record['fast_diagnostics']['accepted']);self.assertEqual(len(record['integrals']),3)
    def test_invalid_coverage_bool_fraction_and_inconsistent_truth_rejected(self):
        for bad in (True,.5,0.):
            values=list(example());deps=values[0];real=fast.score
            def changed(*a,**k):value=real(*a,**k);value['score']['coverage_95']=bad;return value
            deps.fast_scorer=SimpleNamespace(score=changed);score,record=run_example(tuple(values));self.assertIsNone(score);self.assertEqual(record['reason'],'coverage_indicator')
    def test_original_torch_parity_rejects_before_fast(self):
        values=list(example());deps=values[0];calls=[]
        deps.models=SimpleNamespace(edges=models.edges,torch_gh=lambda *_:(torch.tensor([100.]),torch.tensor([100.])))
        deps.fast_scorer=SimpleNamespace(score=lambda *_args,**_kwargs:calls.append(1))
        score,record=run_example(tuple(values));self.assertIsNone(score);self.assertEqual(record['reason'],'original_torch_rejected');self.assertEqual(calls,[])
    def test_fast_disagreement_rejected_full_evidence(self):
        values=list(example());deps=values[0];real=fast.score
        def changed(*a,**k):value=real(*a,**k);value['score']['mean']+=.01;return value
        deps.fast_scorer=SimpleNamespace(score=changed);score,record=run_example(tuple(values));self.assertIsNone(score);self.assertEqual(record['reason'],'original_fast_disagreement');self.assertIn('gh64',record['fast_parity_errors'])
    def test_nonfinite_parameter_has_diagnostic_tokens_no_accepted_forecast(self):
        values=list(example());values[2][0,0]=float('nan');score,record=run_example(tuple(values));self.assertIsNone(score);self.assertEqual(record['base_raw'][0],'NaN')
    def test_requires_grad_inference_scalars_under_warnings_as_errors(self):
        import warnings,copy
        values=list(example());deps,net,raw,z,c,states,mask=values
        mix,h,zv,cv,sv=extracted(net,raw,z,c,states)
        factors=adapter.affine_factors(core,h,zv,cv,sv)
        # Real frozen fast result, memoized for this SAME invented density only.
        import time
        with patch.dict(sys.modules,{'reference':reference}):
            fast_result=fast.score(mix.weights.tolist(),mix.means.tolist(),mix.sigmas.tolist(),factors,.7,processing_begin=time.monotonic(),budget_seconds=10,tolerance=1e-6,require_gh=True,gradients=False)
        raw.requires_grad_(True);z.requires_grad_(True);c.requires_grad_(True)
        logz,mean=models.torch_gh(raw,net.hazards,z,c,states,mask,64)
        self.assertTrue(logz.requires_grad);self.assertTrue(mean.requires_grad)
        gradient=torch.autograd.grad(logz.sum()+mean.sum(),net.hazards.alpha)[0];self.assertTrue(torch.isfinite(gradient).all())
        deps.fast_scorer=SimpleNamespace(score=lambda *args,**kwargs:copy.deepcopy(fast_result))
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            score,record=run_example(tuple(values))
        self.assertIsNotNone(score,record);self.assertTrue(record['accepted']);self.assertTrue(all(type(score['coverage_'+str(k)]) is bool for k in (50,80,95)))
    def test_disagreement_reason_with_graph_tensors_under_warnings_as_errors(self):
        import warnings,copy,time
        values=list(example());deps,net,raw,z,c,states,mask=values;mix,h,zv,cv,sv=extracted(net,raw,z,c,states)
        with patch.dict(sys.modules,{'reference':reference}):
            fast_result=fast.score(mix.weights.tolist(),mix.means.tolist(),mix.sigmas.tolist(),adapter.affine_factors(core,h,zv,cv,sv),.7,processing_begin=time.monotonic(),budget_seconds=10,tolerance=1e-6,require_gh=True,gradients=False)
        fast_result['score']['mean']+=.01;raw.requires_grad_(True);z.requires_grad_(True);c.requires_grad_(True)
        deps.fast_scorer=SimpleNamespace(score=lambda *args,**kwargs:copy.deepcopy(fast_result))
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            score,record=run_example(tuple(values))
        self.assertIsNone(score);self.assertEqual(record['reason'],'original_fast_disagreement');self.assertEqual(len(record['base_raw']),15)

    def test_input_caps_deny_long_states_without_allocation(self):
        values=list(example());values[-2]=torch.ones(1,21,dtype=torch.int64);values[-1]=torch.ones(1,21,dtype=torch.bool);score,record=run_example(tuple(values));self.assertIsNone(score);self.assertEqual(record['reason'],'states')


if __name__=='__main__':unittest.main()
