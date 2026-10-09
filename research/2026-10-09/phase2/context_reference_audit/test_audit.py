"""Synthetic audit fixtures; no source data, model fitting or CUDA use."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import audit as a

HAS_TORCH=importlib.util.find_spec('torch') is not None


def reference_fixture():
    protocol=a.Protocol(records=100,epochs=2,reference_epochs=2,batch_size=8,tail_events=3)
    ids=np.repeat(np.array([f'train_{i}' for i in range(50)]),2)
    n=len(ids);rng=np.random.default_rng(4)
    y=np.repeat(rng.uniform(0,6,50),2)
    p=rng.dirichlet(np.ones(66),n)
    cdf=np.clip(p.cumsum(1)[:,:-1],0,1)
    unscaled=np.minimum(25,1/(.01+cdf*(1-cdf)))
    weights=(unscaled/unscaled.mean(1,keepdims=True)).astype('float32')
    pop=rng.uniform(.4,4,n).astype('float32')
    folds=a.hash_folds(ids,protocol)
    donor=np.arange(n);rng=np.random.default_rng(protocol.permutation_seed)
    for k in range(protocol.folds):
        rows=np.flatnonzero(folds==k);donor[rows]=rng.permutation(rows)
    average=np.average(weights.astype(float),weights=pop,axis=0).astype('float32')
    ref=dict(targets=y,event_ids=ids,trace_names=np.array([f'trace_{i}' for i in range(n)]),
        row_index=np.arange(n),population_weights=pop,folds=folds,donor=donor,
        probability=p,cdf=cdf,weights=weights,average=average)
    report=dict(n_folds=5,fold_seed=protocol.fold_seed,reference_seed=protocol.reference_seed,
        population_weighted_oof_nll=float(np.average(-np.log(p[np.arange(n),np.floor(y/.1+1e-5).astype(int)]),weights=pop)),
        permutation=dict(donor_sha256=a.array_digest(donor),average_sha256=a.array_digest(average)),
        input_sha256='fixture-raw-input-unavailable',folds=[])
    for field,key in [('targets_sha256','targets'),('population_weights_sha256','population_weights'),
            ('row_index_sha256','row_index'),('event_ids_sha256','event_ids'),('trace_names_sha256','trace_names'),
            ('fold_sha256','folds'),('probability_sha256','probability'),('weight_sha256','weights')]:
        report[field]=a.array_digest(ref[key])
    for k in range(5):
        train=np.flatnonzero(folds!=k);held=np.flatnonzero(folds==k)
        report['folds'].append(dict(held_fold=k,seed=protocol.reference_seed+k,
            train_indices_sha256=a.array_digest(train),held_indices_sha256=a.array_digest(held),
            train_records=len(train),held_records=len(held),
            train_events=len(np.unique(ids[train])),held_events=len(np.unique(ids[held]))))
    return protocol,ref,report


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def finish_manifest(run):
    excluded={'COMPLETE.json','artifacts.json'}
    manifest={p.name:dict(bytes=p.stat().st_size,sha256=a.file_digest(p))
              for p in sorted(run.iterdir()) if p.is_file() and p.name not in excluded}
    write_json(run/'artifacts.json',manifest)
    write_json(run/'COMPLETE.json',dict(status='complete',artifacts_sha256=a.file_digest(run/'artifacts.json'),
                                      controls=list(a.CONTROLS),seeds=list(a.Protocol().seeds)))


def make_run(root):
    """Construct on-disk source-format artifacts, not a training smoke run."""
    torch=a.torch_tools();protocol,ref,report=reference_fixture()
    run=root/'run';run.mkdir();rng=np.random.default_rng(25)
    y=np.repeat(np.array([-.1,1.27,4.5,5.,6.8]),2)
    ids=np.repeat(np.array([f'val_{i}' for i in range(5)]),2)
    names=np.array([f'valtrace_{i}' for i in range(len(y))])
    logits=rng.normal(size=(len(y),66));p=np.exp(logits-logits.max(1,keepdims=True));p/=p.sum(1,keepdims=True)
    original=root/'validation.npz'
    np.savez(original,targets=y,event_ids=ids,trace_names=names,centers=a.CENTERS,logits=logits)
    inputs={'validation_reference_sha256':a.file_digest(original)};report['input_identities']=inputs
    config=dict(controls=list(a.CONTROLS),seeds=list(protocol.seeds),epochs=2,reference_epochs=2,
        reference_folds=5,reference_seed=protocol.reference_seed,fold_seed=protocol.fold_seed,
        permutation_seed=protocol.permutation_seed,expected_train_records=100,batch_size=8,max_per_event=4,
        reference_features=85,weight_epsilon=.01,weight_cap=25.,ce_weight=.075,bin_width=.1,
        learning_rate=5e-4,reference_learning_rate=5e-4,sampling_seed=20261009,ad_exponent_safety_bound=60.,
        family='instrument',seconds=1,runtime=dict(deterministic_algorithms=True,cudnn_deterministic=True,
        cudnn_benchmark=False,CUBLAS_WORKSPACE_CONFIG=':4096:8'))
    pins=dict(commit='synthetic_fixture_only',source_sha256={'fixture':'no-training-source'})
    write_json(run/'identity.json',dict(config=config,source_sha256=pins['source_sha256']))
    write_json(run/'run.json',dict(config,train_records=100))
    write_json(run/'input_identities.json',inputs)
    for name in ('alignment.json','feature_schema.json'):write_json(run/name,{})
    traces={};history={};metrics={}
    pred=dict(targets=y,event_ids=ids,trace_names=names,raw_mean=(p*a.CENTERS).sum(1),
              raw_median=a.CENTERS[(p.cumsum(1)<.5).sum(1)])

    def state(seed,dim,zero):
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            net=torch.nn.Sequential(torch.nn.Linear(dim,128),torch.nn.SiLU(),torch.nn.Dropout(.1),
                torch.nn.Linear(128,64),torch.nn.SiLU(),torch.nn.Linear(64,66))
            if zero:
                torch.nn.init.zeros_(net[-1].weight);torch.nn.init.zeros_(net[-1].bias)
        return {'net.'+k:v for k,v in net.state_dict().items()}

    for control in a.CONTROLS:
        probabilities=[]
        for seed in protocol.seeds:
            current=rng.dirichlet(np.ones(66),len(y));probabilities.append(current)
            key=f'{control}_seed{seed}';model=state(seed,291,True)
            traces[key]=dict(initial_model_sha256=a.state_digest(model),final_model_sha256=a.state_digest(model),
                epoch_order_sha256=a.expected_orders(torch,seed,100,2),parameters=sum(v.numel() for v in model.values()),
                preclip_gradient_norm_mean=1.,preclip_gradient_norm_max=2.,gradient_clipped_fraction=0.)
            history[key]=[1.,1.]
            torch.save(dict(model=model,feature_mean=torch.zeros(291),feature_std=torch.ones(291),
                feature_mask=torch.tensor(np.r_[np.ones(279),np.zeros(12)].astype('float32')),
                config=config,seed=seed,control=control),run/f'{key}.pth')
        ensemble=np.mean(probabilities,axis=0)
        np.savez(run/f'{control}_probabilities.npz',targets=y,event_ids=ids,trace_names=names,centers=a.CENTERS,
            mean_probability=ensemble.astype('float32'),
            **{f'seed{s}':v.astype('float32') for s,v in zip(protocol.seeds,probabilities)})
        for suffix,current in list(zip([f'seed{s}' for s in protocol.seeds],probabilities))+[('ensemble',ensemble)]:
            for decision,point in [('mean',(current*a.CENTERS).sum(1)),('median',a.CENTERS[(current.cumsum(1)<.5).sum(1)])]:
                key=f'{control}_{suffix}_{decision}';pred[key]=point
                metrics[key]=a.recompute_metrics(y,point,ids,current)
    for k,proof in enumerate(report['folds']):
        model=state(protocol.reference_seed+k,85,False);mean=torch.zeros(85);std=torch.ones(85)
        proof.update(initial_model_sha256=a.state_digest(model),final_model_sha256=a.state_digest(model),
            epoch_order_sha256=a.expected_orders(torch,protocol.reference_seed+k,proof['train_records'],2),
            history=[1.,1.],normalizer_mean_sha256=a.array_digest(mean.numpy()),normalizer_std_sha256=a.array_digest(std.numpy()))
        torch.save(dict(model=model,feature_mean=mean,feature_std=std,held_fold=k,
                        seed=protocol.reference_seed+k,feature_dimension=85),run/f'reference_fold{k}.pth')
    np.savez(run/'reference_oof.npz',**ref);np.savez(run/'predictions.npz',**pred)
    for name,value in [('reference_report',report),('metrics',metrics),('history',history),('training_traces',traces)]:
        write_json(run/f'{name}.json',value)
    finish_manifest(run)
    return run,pins,original,protocol


class AuditTests(unittest.TestCase):
    def test_continuous_crps_independent_pairwise_identity(self):
        rng=np.random.default_rng(2);p=rng.dirichlet(np.ones(66),15);y=np.linspace(-2,9,15)
        want=(p*np.abs(a.CENTERS-y[:,None])).sum(1)-.5*np.einsum('ni,ij,nj->n',p,np.abs(a.CENTERS[:,None]-a.CENTERS),p)
        np.testing.assert_allclose(a.continuous_crps(p,y),want,atol=4e-15,rtol=1e-14)

    def test_point_rounding_and_corruption(self):
        rng=np.random.default_rng(21);p=rng.dirichlet(np.ones(66),100)
        mean=(p*a.CENTERS).sum(1);med=a.CENTERS[(p.cumsum(1)<.5).sum(1)]
        a.validate_points(p.astype('float32'),mean,med)
        with self.assertRaisesRegex(ValueError,'Saved mean'):
            a.validate_points(p.astype('float32'),mean+.0001,med)
        with self.assertRaisesRegex(ValueError,'Saved median'):
            a.validate_points(p.astype('float32'),mean,med+.1)

    def test_rounded_median_tie_is_feasible(self):
        p=np.zeros((1,66));p[0,0]=.5-1e-10;p[0,1]=.5+1e-10
        result=a.validate_points(p.astype('float32'),(p*a.CENTERS).sum(1),a.CENTERS[[1]])
        self.assertEqual(result['median_rounding_ambiguous_rows'],1)

    def test_median_cannot_cross_float32_zero_gap(self):
        p=np.zeros((1,66),dtype='float32');p[0,0]=.5;p[0,65]=.5
        with self.assertRaisesRegex(ValueError,'probability gap'):
            a.validate_points(p,(p*a.CENTERS).sum(1),a.CENTERS[[20]])
        a.validate_points(p,(p*a.CENTERS).sum(1),a.CENTERS[[0]])

    def test_median_asymmetric_power_of_two_rounding(self):
        p=np.zeros((1,66),dtype='float32');p[0,:5]=[.25,.25,2e-8,.25,.25-2e-8]
        original=p.astype(float);original[0,0]-=original.sum()-1
        self.assertTrue(np.array_equal(original.astype('float32'),p))
        mean=(original*a.CENTERS).sum(1)
        a.validate_points(p,mean,a.CENTERS[[2]])
        with self.assertRaisesRegex(ValueError,'Saved median inconsistent'):
            a.validate_points(p,mean,a.CENTERS[[3]])

    def test_ensemble_rounding_intervals_and_zero_mass(self):
        rng=np.random.default_rng(72)
        seeds=[rng.dirichlet(np.ones(66),20) for _ in range(2)]
        a.verify_ensemble(np.mean(seeds,axis=0).astype('float32'),[p.astype('float32') for p in seeds])
        zero=np.zeros((1,66),dtype='float32');zero[0,0]=1
        for entry in (np.float32(1e-7),np.nextafter(np.float32(0),np.float32(1))):
            wrong=zero.copy();wrong[0,1]=entry
            with self.assertRaisesRegex(ValueError,'Ensemble'):a.verify_ensemble(wrong,[zero,zero])

    def test_zero_nll_and_event_macro(self):
        p=np.zeros((4,66));p[:,0]=1;y=np.array([0.,0.,0.,4.])
        result=a.recompute_metrics(y,np.zeros(4),np.array(['a','a','a','b']),p)
        self.assertEqual(result['mae'],1);self.assertEqual(result['event_macro_mae'],2)
        self.assertEqual(result['m4_records'],1);self.assertIsNone(result['nll'])
        self.assertEqual(result['nll_zero_target_probabilities'],1)
        json.dumps(result,allow_nan=False)

    def test_invalid_probability_rejected(self):
        for p in (np.zeros((3,66)),np.full((3,66),np.nan),np.full((3,65),1/65)):
            with self.assertRaises(ValueError):a.normalized_probability(p)

    def test_reference_equation_folds_and_control(self):
        protocol,ref,report=reference_fixture();result=a.verify_reference(ref,report,protocol)
        self.assertGreater(result['context_minus_average_weight_rms'],0)
        self.assertEqual(len(result['folds']),5)

    def test_reference_cross_fold_donor_rejected(self):
        protocol,ref,report=reference_fixture();changed=copy.deepcopy(ref)
        left=0;right=np.flatnonzero(ref['folds']!=ref['folds'][0])[0]
        changed['donor'][left],changed['donor'][right]=changed['donor'][right],changed['donor'][left]
        with self.assertRaisesRegex(ValueError,'crosses'):a.verify_reference(changed,report,protocol)

    def test_reference_weight_and_index_tamper_rejected(self):
        protocol,ref,report=reference_fixture();changed=copy.deepcopy(ref)
        changed['weights'][0,0]+=1;report['weight_sha256']=a.array_digest(changed['weights'])
        with self.assertRaisesRegex(ValueError,'prespecified'):a.verify_reference(changed,report,protocol)
        protocol,ref,report=reference_fixture();report['folds'][0]['train_indices_sha256']='forged'
        with self.assertRaisesRegex(ValueError,'row-index'):a.verify_reference(ref,report,protocol)

    def test_row_alignment_rejects_permutation(self):
        y=np.arange(5);ids=np.array(list('abcde'));names=np.array(list('fghij'))
        with self.assertRaisesRegex(ValueError,'row identities'):
            a.aligned(dict(targets=y[::-1],event_ids=ids,trace_names=names),y,ids,names)

    @unittest.skipUnless(HAS_TORCH,'Checkpoint audit requires CPU torch')
    def test_end_to_end_artifact_and_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);run,pins,original,protocol=make_run(root)
            result=a.audit_run(run,pins,original,protocol=protocol)
            self.assertEqual(len(result['metrics']),36)
            self.assertEqual(len(result['tail_events']),108)
            self.assertFalse(result['checkpoints']['cuda_used'])
            a.write_report(result,root/'output')
            self.assertEqual(a.read_json(root/'output/audit.json')['seconds'],1)
            for name in ('metrics.csv','tail_events.csv','report.md'):self.assertTrue((root/'output'/name).is_file())
            with self.assertRaisesRegex(ValueError,'fresh'):a.write_report(result,root/'output')

    @unittest.skipUnless(HAS_TORCH,'Checkpoint fixture requires CPU torch')
    def test_manifest_and_checkpoint_provenance_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            run,pins,original,protocol=make_run(Path(temp))
            with (run/'metrics.json').open('a') as stream:stream.write(' ')
            with self.assertRaisesRegex(ValueError,'Artifact mismatch'):a.verify_artifacts(run,pins,protocol)
            finish_manifest(run)
            trace=a.read_json(run/'training_traces.json');trace['context_ce_seed20261009']['epoch_order_sha256'][0]='wrong'
            write_json(run/'training_traces.json',trace);finish_manifest(run)
            with self.assertRaisesRegex(ValueError,'order does not replay'):a.audit_run(run,pins,original,protocol=protocol)
            (run/'COMPLETE.json').unlink()
            with self.assertRaises(FileNotFoundError):a.verify_artifacts(run,pins,protocol)


if __name__=='__main__':unittest.main()
