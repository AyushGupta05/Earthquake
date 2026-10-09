from argparse import Namespace
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research/2026-10-09/phase2'))
import context_reference as method
import context_reference_train as runner
import train_instrument_scores as previous
import instrument_residual as baseline
from feature_residual import ResidualDistribution
from audit_and_export import sha256


def fixture_data():
    rng = np.random.default_rng(7051)
    data = {'centers': (np.arange(66)+.5)*.1}
    for split,n in [('train',60),('val',6)]:
        for key,dim in [('logits',66),('hidden',128),('prefix',51),('instrument',34),('native',12)]:
            data[split+'_'+key] = rng.normal(size=(n,dim)).astype(np.float32)
        data[split+'_y'] = np.repeat(np.resize(np.array([1.,2.,4.5]),n//2),2).astype(np.float32)
        data[split+'_ids'] = np.array([f'{split}_event{i//2}' for i in range(n)])
        data[split+'_trace_names'] = np.array([f'{split}_trace{i}' for i in range(n)])
    data['train_rows'] = np.arange(60)
    data['weights'] = np.linspace(.5,1.5,60).astype(np.float32)
    return data


def fit_args(**kwargs):
    values = dict(epochs=2,reference_epochs=2,batch_size=16,learning_rate=5e-4,
        reference_learning_rate=5e-4,reference_seed=20261011,fold_seed=20261009,
        permutation_seed=20261012,reference_folds=5)
    values.update(kwargs)
    return Namespace(**values)


def synthetic_references(data):
    p = np.full((len(data['train_y']),66),1/66)
    weights,_,_ = method.reference_weights(p)
    folds = method.event_folds(data['train_ids'])
    donor,average,_ = method.weight_controls(weights,data['weights'],folds,data['train_ids'])
    return dict(probability=p,weights=weights,folds=folds,donor=donor,average=average)


class ContextReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner.configure_runtime()

    def test_reference_features_exclude_entire_cnn_and_validation_pipeline(self):
        data = fixture_data(); original = method.reference_inputs(data)
        changed = copy.deepcopy(data)
        for key in changed:
            if key not in ('train_prefix','train_instrument') and changed[key].dtype.kind in 'fi':
                changed[key][:] = 999
        np.testing.assert_array_equal(original,method.reference_inputs(changed))
        np.testing.assert_array_equal(original[:,:51],data['train_prefix'])
        np.testing.assert_array_equal(original[:,51:],data['train_instrument'])
        self.assertEqual(original.shape,(60,85))
        changed['train_prefix'] = changed['train_prefix'][:,:50]
        with self.assertRaises(ValueError): method.reference_inputs(changed)

    def test_hash_folds_group_whole_events_are_order_and_replication_invariant(self):
        ids = fixture_data()['train_ids']; folds = method.event_folds(ids)
        order = np.random.default_rng(8).permutation(len(ids))
        np.testing.assert_array_equal(method.event_folds(ids[order]),folds[order])
        np.testing.assert_array_equal(method.event_folds(np.repeat(ids,2)),np.repeat(folds,2))
        for event in np.unique(ids): self.assertEqual(len(np.unique(folds[ids==event])),1)
        for bad in [np.array(['']), np.arange(20), np.array(['one']*20)]:
            with self.assertRaises(ValueError): method.event_folds(bad)

    def test_held_event_labels_and_weights_cannot_change_own_teacher(self):
        data=fixture_data();x=method.reference_inputs(data);labels=method.magnitude_labels(data['train_y'])
        folds=method.event_folds(data['train_ids']);args=fit_args(); held_fold=0
        held,a,ast,ar=method.fit_reference_fold(x,labels,data['weights'],folds,held_fold,args,torch.device('cpu'))
        changed_labels=labels.copy();changed_labels[held]=-999
        changed_weights=data['weights'].copy();changed_weights[held]=np.nan
        _,b,bst,br=method.fit_reference_fold(x,changed_labels,changed_weights,folds,held_fold,args,torch.device('cpu'))
        np.testing.assert_array_equal(a,b);self.assertEqual(ar,br)
        for key in ast['model']: torch.testing.assert_close(ast['model'][key],bst['model'][key],atol=0,rtol=0)
        changed_x=x.copy();changed_x[held] *= 99
        _,c,cst,cr=method.fit_reference_fold(changed_x,labels,data['weights'],folds,held_fold,args,torch.device('cpu'))
        self.assertFalse(np.array_equal(a,c))
        for key in ast['model']: torch.testing.assert_close(ast['model'][key],cst['model'][key],atol=0,rtol=0)
        torch.testing.assert_close(ast['feature_mean'],cst['feature_mean'],atol=0,rtol=0)
        torch.testing.assert_close(ast['feature_std'],cst['feature_std'],atol=0,rtol=0)
        self.assertEqual(ar,cr)

    def test_weight_equation_caps_and_mean_one_even_at_zero_one_cdf(self):
        p=np.array([[0.,.5,.5,0.],[1.,0.,0.,0.],[.1,.2,.3,.4]])
        w,cdf,capped=method.reference_weights(p)
        raw=np.minimum(25,1/(.01+cdf*(1-cdf)))
        np.testing.assert_allclose(w,raw/raw.mean(1,keepdims=True),rtol=1e-7)
        np.testing.assert_allclose(w.mean(1),1,atol=1e-7)
        self.assertTrue(np.isfinite(w).all());self.assertTrue((w>0).all())
        self.assertTrue(capped[1].all())
        for bad in [p*2,p*np.nan,-p,p[0],np.empty((0,4))]:
            with self.assertRaises(ValueError):method.reference_weights(bad)

    def test_permutation_is_bijection_inside_same_excluded_fold_and_average_is_population_weighted(self):
        data=fixture_data();folds=method.event_folds(data['train_ids'])
        rng=np.random.default_rng(3);p=rng.dirichlet(np.ones(66),len(folds))
        w,_,_=method.reference_weights(p)
        donor,avg,report=method.weight_controls(w,data['weights'],folds,data['train_ids'])
        np.testing.assert_array_equal(np.sort(donor),np.arange(len(folds)))
        np.testing.assert_array_equal(folds[donor],folds)
        np.testing.assert_allclose(avg,np.average(w.astype(float),weights=data['weights'],axis=0),atol=1e-7)
        donor2,avg2,report2=method.weight_controls(w,data['weights'],folds,data['train_ids'])
        np.testing.assert_array_equal(donor,donor2);self.assertEqual(report,report2)
        self.assertIn('same_event_donor_fraction',report)

    def test_all_scores_proper_at_truth_context_weights_fixed_and_ad_matches_closed_form(self):
        truth=torch.tensor([.07,.18,.25,.5],dtype=torch.float64);labels=torch.arange(4)
        frozen=torch.tensor([1.7,.5,.8],dtype=torch.float64)
        for control in method.CONTROLS:
            logits=truth.log().requires_grad_();batch=logits.expand(4,-1)
            value=truth@method.score_vector(batch,labels,control,frozen)
            value.backward()
            torch.testing.assert_close(logits.grad,torch.zeros_like(logits),atol=3e-16,rtol=0)
            alt=(truth.log()+torch.tensor([.7,-.5,.2,-.3])).expand(4,-1)
            self.assertGreater((truth@method.score_vector(alt,labels,control,frozen)).item(),value.item())
        p=truth.cumsum(0)[:-1];observed=labels[:,None]<=torch.arange(3)
        exact=.1*torch.where(observed,((1-p)/p).sqrt(),(p/(1-p)).sqrt()).sum(-1)
        exact += .075*F.cross_entropy(truth.log().expand(4,-1),labels,reduction='none')
        torch.testing.assert_close(method.score_vector(truth.log().expand(4,-1),labels,'properized_ad_ce'),exact,atol=2e-16,rtol=0)

    def test_context_excess_is_weighted_cdf_distance_and_ones_recover_crps(self):
        p=torch.tensor([.1,.2,.3,.4],dtype=torch.float64);q=torch.tensor([.3,.1,.2,.4],dtype=torch.float64)
        w=torch.tensor([.3,.7,2.],dtype=torch.float64);labels=torch.arange(4)
        a=method.score_vector(p.log().expand(4,-1),labels,'context_ce',w)
        b=method.score_vector(q.log().expand(4,-1),labels,'context_ce',w)
        expected=.1*(w*(p.cumsum(0)[:-1]-q.cumsum(0)[:-1]).square()).sum()+.075*(q*(q/p).log()).sum()
        torch.testing.assert_close(q@(a-b),expected,atol=2e-16,rtol=0)
        for dtype in [torch.float32,torch.float64]:
            logits=p.to(dtype).log().expand(4,-1)
            torch.testing.assert_close(method.score_vector(logits,labels,'context_ce',torch.ones(4,3,dtype=dtype)),
                method.score_vector(logits,labels,'crps_ce'),atol=0,rtol=0)

    def test_ad_does_not_silently_clip_extreme_wrong_predictions(self):
        logits=torch.tensor([[10000.,-10000.]],requires_grad=True);labels=torch.tensor([1])
        with self.assertRaises(FloatingPointError):method.score_vector(logits,labels,'properized_ad_ce')
        for control in ['crps_ce','ranked_bce_ce','context_ce']:
            x=logits.detach().clone().requires_grad_()
            value=method.score_vector(x,labels,control,torch.ones(1))
            value.sum().backward();self.assertTrue(torch.isfinite(value).all());self.assertTrue(torch.isfinite(x.grad).all())
        for w in [torch.ones(2),torch.tensor([0.]),torch.tensor([float('nan')]),torch.ones(1,requires_grad=True)]:
            with self.assertRaises(ValueError):method.score_vector(logits,labels,'context_ce',w)

    def test_crps_and_ranked_bce_exactly_replay_previous_fit_and_rng(self):
        data=fixture_data();args=fit_args();arrays,_,_,mask,_=runner.instrument_design(data)
        refs=synthetic_references(data)
        for seed in [20261009,20261010]:
            for control in ['crps_ce','ranked_bce_ce']:
                a,ast,ah,atrace=previous.fit_one(data,arrays,mask,args,seed,torch.device('cpu'),control,np.ones(65,np.float32))
                arng=torch.get_rng_state().clone()
                b,bst,bh,btrace=runner.fit_one(data,arrays,mask,args,seed,torch.device('cpu'),control,refs)
                np.testing.assert_array_equal(a,b);self.assertEqual(ah,bh)
                torch.testing.assert_close(arng,torch.get_rng_state(),atol=0,rtol=0)
                for key in atrace:self.assertEqual(atrace[key],btrace[key])
                for key in ast:torch.testing.assert_close(ast[key],bst[key],atol=0,rtol=0)

    def test_all_student_controls_share_init_order_rng_and_ignore_val_labels(self):
        data=fixture_data();args=fit_args();arrays,_,_,mask,_=runner.instrument_design(data);refs=synthetic_references(data)
        traces=[];rngs=[]
        for control in method.CONTROLS:
            a,_,ah,at=runner.fit_one(data,arrays,mask,args,20261009,torch.device('cpu'),control,refs)
            traces.append(at);rngs.append(torch.get_rng_state().clone())
            altered=copy.deepcopy(data);altered['val_y'][:]=-999
            b,_,bh,bt=runner.fit_one(altered,arrays,mask,args,20261009,torch.device('cpu'),control,refs)
            np.testing.assert_array_equal(a,b);self.assertEqual(ah,bh);self.assertEqual(at,bt)
        for t,r in zip(traces[1:],rngs[1:]):
            for key in ['initial_model_sha256','epoch_order_sha256','parameters']:self.assertEqual(t[key],traces[0][key])
            torch.testing.assert_close(r,rngs[0],atol=0,rtol=0)

    def test_end_to_end_mock_extract_freezes_aligned_oof_and_atomic_completion(self):
        data=fixture_data()
        with tempfile.TemporaryDirectory() as directory:
            args=runner.parse_args(['--seconds','1','--inventory','fixture.tgz','--output',directory,
                '--device','cpu','--epochs','1','--reference-epochs','1','--batch-size','16',
                '--seeds','20261009','--expected-train-records','60'])
            with patch.object(baseline,'extract',return_value=(data,{'mocked':True},{'alignment':'synthetic'},[f'f{i}' for i in range(34)])):
                out=runner.run(args)
            completion=json.loads((out/'COMPLETE.json').read_text());self.assertFalse((out/'COMPLETE.tmp').exists())
            self.assertEqual(completion['artifacts_sha256'],sha256(out/'artifacts.json'))
            with np.load(out/'reference_oof.npz',allow_pickle=False) as refs:
                for key,data_key in [('targets','train_y'),('event_ids','train_ids'),('row_index','train_rows'),('trace_names','train_trace_names')]:
                    np.testing.assert_array_equal(refs[key],data[data_key])
                np.testing.assert_allclose(refs['cdf'],refs['probability'].cumsum(1)[:,:-1],atol=1e-15)
                np.testing.assert_array_equal(refs['folds'],refs['folds'][refs['donor']])
            report=json.loads((out/'reference_report.json').read_text())
            self.assertEqual(report['targets_sha256'],runner.array_digest(data['train_y']))
            self.assertEqual(len(report['folds']),5);self.assertTrue(np.isfinite(report['population_weighted_oof_nll']))
            traces=json.loads((out/'training_traces.json').read_text())
            for control in method.CONTROLS:
                name=control+'_seed20261009';checkpoint=torch.load(out/(name+'.pth'),map_location='cpu',weights_only=True)
                model=ResidualDistribution(291);model.load_state_dict(checkpoint['model'])
                self.assertEqual(runner.model_digest(model),traces[name]['final_model_sha256'])
                self.assertNotIn('reference_model',checkpoint)
            manifest=json.loads((out/'artifacts.json').read_text())
            for name,identity in manifest.items():self.assertEqual(identity['sha256'],sha256(out/name))

    def test_defaults_and_invalid_cli(self):
        base=['--seconds','1','--inventory','fixture.tgz'];args=runner.parse_args(base)
        self.assertEqual((args.expected_train_records,args.max_per_event,args.epochs,args.reference_folds),(197676,4,15,5))
        self.assertEqual(args.controls,list(method.CONTROLS))
        for extra in [['--reference-epochs','0'],['--reference-learning-rate','nan'],['--reference-folds','1'],
                      ['--seeds','1','1'],['--controls','crps_ce','crps_ce'],['--expected-train-records','0']]:
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):runner.parse_args(base+extra)


if __name__ == '__main__':
    unittest.main()
