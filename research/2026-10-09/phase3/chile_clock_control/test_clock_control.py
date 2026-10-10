"""Invented fixtures only. No production files or arrays are opened by tests."""
import ast
import copy
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

HERE=Path(__file__).parent
SOURCE=Path(__file__).resolve().parents[1]/'repo/research/2026-10-09/phase3'
if not SOURCE.exists():SOURCE=HERE/'dependencies'
sys.path.insert(0,str(HERE))
from baseline_guards import sha, ids_sha, validate_splits, validate_plan, epoch_sequence
from clock_contract import metadata_rows, preflight, PROTOCOL_SHA, OWN_FILES, SOURCES, atomic_json, validate_baseline
from clock_rng import Streams, Trace, apply_augmentation, assert_paired, state_digest
from clock_training import train_epoch, completed_fits, _save_epoch, fresh_model, require_runtime
from clock_metrics import scores, paired_comparison, frozen_gate, add_proper_scores
from clock_replay import compare_parameters
from run_clock_control import supervise, validate_output

# The unchanged model has no HDF dependency. Load selected mathematical/source
# helpers by AST to keep local synthetic tests independent of optional PyTables/
# h5py; the parent runtime test additionally exercises real h5py and imports.
spec=importlib.util.spec_from_file_location('clock_test_team',SOURCE/'team_lm.py')
team=importlib.util.module_from_spec(spec);spec.loader.exec_module(team)
helper_names={'_event_seed','gaussian_mixture_crps','atomic_save','resampling_indices','sample_cutoffs','author_station_blinding','event_label_smoothing'}
source_ast=ast.parse((SOURCE/'train_team_lm.py').read_text())
helper_nodes=[node for node in source_ast.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in helper_names]
namespace={'torch':torch,'np':np,'math':math,'hashlib':hashlib,'Path':Path,'os':__import__('os'),'prepare_prefix':team.prepare_prefix}
exec(compile(ast.Module(body=helper_nodes,type_ignores=[]),str(SOURCE/'train_team_lm.py'),'exec'),namespace)
trainer=types.SimpleNamespace(**{name:namespace[name] for name in helper_names if name in namespace})

def fixture_metadata(directory):
    blocks={'fit':([0,2],['e0','e2']),'calibration':([1],['e1']),'dev':([3],['e3'])}
    splits={k:{'source_rows':rows,'event_ids':ids,'ids_sha256':ids_sha(ids)} for k,(rows,ids) in blocks.items()}
    run={k+s:v for k,b in splits.items() for s,v in [('_events',len(b['event_ids'])),('_ids_sha256',b['ids_sha256'])]}
    manifest={'author_split_boundaries':[3,4],'cache_rows':4,'splits':{'train':{'ids_sha256':ids_sha(['e0','e1','e2'])},'dev':{'ids_sha256':ids_sha(['e3'])}}}
    path=directory/'metadata.csv'
    with path.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['EVENT','MA','TIME','source_row_index','benchmark_split'])
        for i in range(4):w.writerow([f'e{i}',str(i+1) if i in (0,2) else 'DO_NOT_PARSE',str(i) if i in (0,2) else 'POISON',i,'train' if i<3 else 'dev'])
    return path,splits,manifest,{'rows':4},run


def prediction(n=8,shift=.2):
    y=np.arange(n,dtype=float)/2
    p={'event_ids':np.array([f'e{i}' for i in range(n)]),'targets':y}
    for t in (1,3,5):
        for action in ('mean','median'):p[f'{action}_{t}s']=y+shift*(1+np.arange(n)/n)
        p[f'nll_{t}s']=np.full(n,1+shift);p[f'crps_{t}s']=np.full(n,.2+shift)
    return p


class Tiny(torch.nn.Module):
    def __init__(self,*args):
        super().__init__();self.layer=torch.nn.Linear(1,15);self.single_station_head=torch.nn.Linear(1,1)
    def forward(self,x,coords,mask,cutoff_seconds):
        prefix,active=team.prepare_prefix(x,mask,cutoff_seconds)
        feature=prefix.square().mean((1,2,3),keepdim=False)[:,None]
        out=self.layer(feature);logits,means,raw=out.chunk(3,-1)
        return {'logits':logits,'weights':logits.softmax(-1),'means':means,'scales':raw.exp()+.1}


class TinyData(Dataset):
    def __init__(self,n=65):self.n=n
    def __len__(self):return self.n
    def __getitem__(self,index):
        # deterministic, variable prefix energy; no global RNG consumption
        x=torch.arange(9000,dtype=torch.float32).reshape(1,3000,3).sin()*(1+index/100)
        return x,torch.ones(1,3),torch.ones(1,dtype=torch.bool),torch.tensor(4.5),f'e{index}'


class ClockRngTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(2)
    def test_exact_uniform_sample_counts(self):
        s=Streams(3,'cpu');cut,n=s.cutoffs(25000,'cpu','source_uniform')
        self.assertGreaterEqual(int(n.min()),100);self.assertLess(int(n.max()),3000)
        self.assertTrue(torch.equal(((cut+5)*100).floor().long(),n))
        self.assertLess(abs(float((n<600).float().mean())-500/2900),.015)
    def test_discrete_law_and_counts(self):
        cut,n=Streams(4,'cpu').cutoffs(30000,'cpu','discrete_1_3_5')
        self.assertEqual(set(cut.tolist()),{1.,3.,5.});self.assertEqual(set(n.tolist()),{600,800,1000})
        for value in (600,800,1000):self.assertLess(abs(float((n==value).float().mean())-1/3),.015)
    def test_clock_does_not_consume_other_streams_or_model_rng(self):
        a,b=Streams(1,'cpu'),Streams(1,'cpu');rng=torch.get_rng_state().clone()
        a.cutoffs(19,'cpu','source_uniform');b.cutoffs(200,'cpu','discrete_1_3_5')
        aa=a.augmentation(torch.ones(9,4,dtype=torch.bool),torch.ones(9));bb=b.augmentation(torch.ones(9,4,dtype=torch.bool),torch.ones(9))
        for x,y in zip(aa,bb):self.assertTrue(torch.equal(x,y))
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
    def test_blinding_and_label_equations(self):
        x=torch.arange(2*4*3000*3).reshape(2,4,3000,3).float().sin();c=torch.ones(2,4,3);m=torch.ones(2,4,dtype=torch.bool)
        c[0,3]=0;m[1,3]=False;y=torch.tensor([3.,6.]);u=torch.tensor([.8,.1]);r=torch.arange(8).reshape(2,4).float();z=torch.tensor([2.,-1.])
        mask,noisy=apply_augmentation(x,c,m,y,1.,(u,r,z),team.prepare_prefix)
        self.assertEqual(mask.tolist(),[[False,False,True,True],[True,True,True,False]])
        torch.testing.assert_close(noisy,torch.tensor([3.,5.9]),rtol=0,atol=0)
    def test_all_inactive_no_forced_station(self):
        mask,label=apply_augmentation(torch.zeros(1,2,3000,3),torch.ones(1,2,3),torch.zeros(1,2,dtype=torch.bool),torch.tensor([5.]),1.,(torch.tensor([.9]),torch.zeros(1,2),torch.ones(1)),team.prepare_prefix)
        self.assertFalse(mask.any());self.assertAlmostEqual(float(label),5.05,places=5)
    def test_future_suffix_is_irrelevant(self):
        x=torch.rand(2,2,3000,3);c=torch.ones(2,2,3);m=torch.ones(2,2,dtype=torch.bool);y=torch.ones(2)
        for t in (1,3,5):
            altered=x.clone();altered[:,:,500+100*t:]=float('nan')
            draws=Streams(3,'cpu').augmentation(m,y)
            a=apply_augmentation(x,c,m,y,t,draws,team.prepare_prefix);b=apply_augmentation(altered,c,m,y,t,draws,team.prepare_prefix)
            for aa,bb in zip(a,b):self.assertTrue(torch.equal(aa,bb))
            self.assertTrue(torch.equal(team.prepare_prefix(x,m,t)[0],team.prepare_prefix(altered,m,t)[0]))
    def test_actual_team_forward_prefix_and_initial_state(self):
        source=team.TeamLM('transformer');initial=copy.deepcopy(source.state_dict())
        model=fresh_model(team,initial,20261011,torch.device('cpu')).eval()
        self.assertEqual(state_digest(model.state_dict()),state_digest(initial))
        x=torch.rand(1,2,3000,3);coords=torch.ones(1,2,3);mask=torch.ones(1,2,dtype=torch.bool)
        with torch.no_grad():
            for t in (1,3,5):
                altered=x.clone();altered[:,:,500+100*t:]=float('nan')
                a=model(x,coords,mask,t);b=model(altered,coords,mask,t)
                for key in a:self.assertTrue(torch.equal(a[key],b[key]));self.assertTrue(torch.isfinite(a[key]).all())
    def test_bad_arm_and_draw_shapes_fail(self):
        with self.assertRaises(ValueError):Streams(1,'cpu').cutoffs(1,'cpu','unknown')
        with self.assertRaises(ValueError):apply_augmentation(None,None,torch.ones(2,2),torch.ones(2),1,(torch.ones(3),torch.ones(2,2),torch.ones(2)),None)
    def test_trace_pairing(self):
        a=Trace().result();b=copy.deepcopy(a);b['sha256']['clock']='different';assert_paired(a,b)
        b['sha256']['event_order']='wrong'
        with self.assertRaises(ValueError):assert_paired(a,b)
    def test_optimizer_equivalence_and_remainder(self):
        tinyteam=types.SimpleNamespace(TeamLM=Tiny,prepare_prefix=team.prepare_prefix,mixture_nll=team.mixture_nll)
        initial=Tiny().state_dict();runs=[]
        for arm in ('source_uniform','source_uniform','discrete_1_3_5'):
            model=fresh_model(tinyteam,initial,23,torch.device('cpu'));params=[p for p in model.parameters() if p.requires_grad]
            opt=torch.optim.Adam(params,lr=9e-6);streams=Streams(23,'cpu');hist=[]
            for epoch in range(2):
                loader=DataLoader(TinyData(),batch_size=64,shuffle=True,generator=torch.Generator().manual_seed(23+1000+epoch))
                hist.append(train_epoch(model,loader,opt,params,streams,arm,team,trainer,torch.device('cpu'),seed=23,epoch=epoch,station_counts={f'e{i}':1 for i in range(65)}))
            runs.append((model,opt,hist,streams))
        self.assertEqual(state_digest(runs[0][0].state_dict()),state_digest(runs[1][0].state_dict()))
        for a,b in zip(runs[0][2],runs[1][2]):self.assertEqual(a['train_loss'],b['train_loss']);self.assertEqual(a['trace'],b['trace'])
        for a,b in zip(runs[0][2],runs[2][2]):assert_paired(a['trace'],b['trace']);self.assertEqual(a['trace']['batch_sizes'],[64,1])
        for state in runs[0][1].state.values():
            for value in state.values():self.assertTrue(torch.isfinite(value).all())
        self.assertIsNone(runs[0][0].single_station_head.weight.grad)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'latest.pth';_save_epoch(path,trainer,runs[0][0],runs[0][1],runs[0][3],2,runs[0][2],{'synthetic':True},torch.device('cpu'))
            saved=torch.load(path,weights_only=True);self.assertEqual(saved['completed_epoch'],2);self.assertFalse(saved['resume_supported'])
            self.assertEqual(state_digest(saved['model']),state_digest(runs[0][0].state_dict()))
            self.assertEqual(len(saved['optimizer']['state']),len(runs[0][1].state))


class ContractTests(unittest.TestCase):
    def test_fit_only_metadata_does_not_parse_poisoned_held_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            p,s,m,side,r=fixture_metadata(Path(temp));validate_splits(s,3,4,r)
            rows,_=metadata_rows(p,s,m,side,requested='fit');self.assertEqual([x['EVENT'] for x in rows],['e0','e2'])
            with self.assertRaisesRegex(ValueError,'Held-out'):metadata_rows(p,s,m,side,requested='dev')
            with self.assertRaises(ValueError):metadata_rows(p,s,m,side,requested='dev',all_fits_complete=True)
    def test_split_reordering_or_leak_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            _,s,_,_,r=fixture_metadata(Path(temp));s['fit']['source_rows']=[0,3]
            with self.assertRaises(ValueError):validate_splits(s,3,4,r)
    def test_synthetic_hdf_headers(self):
        try:import h5py
        except ImportError:self.skipTest('h5py absent locally; parent AWS synthetic test must run this case')
        from clock_contract import verify_cache_headers
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p,s,m,side,r=fixture_metadata(root);rows,ids=metadata_rows(p,s,m,side,requested='fit')
            path=root/'invented.hdf5'
            with h5py.File(path,'w') as h:
                h.attrs['schema']='chile-team-prefix-v1';h.attrs['stored_samples']=3000
                for name,val in [('sampling_rate',100),('time_before',5),('time_after',25)]:h.create_dataset('metadata/'+name,data=val)
                for name,begin,end in [('train',0,3),('dev',3,4)]:
                    h.create_dataset('splits/'+name+'_event_ids',data=np.array(ids[name],dtype=h5py.string_dtype()))
                    h.create_dataset('splits/'+name+'_source_rows',data=np.arange(begin,end))
                for event in ids['train']+ids['dev']:
                    h.create_dataset('data/'+event+'/waveforms',shape=(2,3000,3),dtype='f4')
                    h.create_dataset('data/'+event+'/coords',shape=(2,3),dtype='f4')
            self.assertEqual(verify_cache_headers(path,m,ids,rows),{'e0':2,'e2':2})
            with h5py.File(path,'a') as h:h.create_group('data/forbidden_test')
            with self.assertRaises(ValueError):verify_cache_headers(path,m,ids,rows)
    def test_epoch_completion_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'history.json';atomic_json(path,[{'epoch':i,'nll':'unread'} for i in range(1,4)]);self.assertEqual(epoch_sequence(path,3),[1,2,3])
            atomic_json(path,[{'epoch':1}])
            with self.assertRaises(ValueError):epoch_sequence(path,3)
    def test_baseline_extra_config_and_epoch(self):
        run={'selected_epoch':97};checkpoint={'config':{},'model':{},'selected_epoch':96}
        with mock.patch('clock_contract.validate_completion'):
            with self.assertRaisesRegex(ValueError,'selected97'):validate_baseline(run,checkpoint,{}, {})
            checkpoint['selected_epoch']=97
            with self.assertRaisesRegex(ValueError,'event config'):validate_baseline(run,checkpoint,{}, {})
    def test_pinned_migration_runtime_extension_and_precision(self):
        precision={'cuda_matmul_allow_tf32':False,'cudnn_allow_tf32':True,'float32_matmul_precision':'highest'}
        runtime={'torch':'synthetic_torch','cuda':'synthetic_cuda','cudnn':123,**precision}
        run={'torch_version':'synthetic_torch','runtime':{'torch_cuda':'synthetic_cuda','cudnn':123,'gpu':'synthetic_gpu',
            'station_backend':{'schema':'team-flat-station-runtime-v1','scope':'station_pretraining_and_train_calibration_only','strict_runtime':precision}}}
        with mock.patch('torch.cuda.is_available',return_value=True),mock.patch('torch.cuda.get_device_name',return_value='synthetic_gpu'):
            require_runtime(runtime,run,torch.device('cuda'))
            changed={**runtime,'cuda_matmul_allow_tf32':True}
            with self.assertRaisesRegex(ValueError,'precision'):require_runtime(changed,run,torch.device('cuda'))
            del run['runtime']['station_backend']
            with self.assertRaisesRegex(ValueError,'extension'):require_runtime(runtime,run,torch.device('cuda'))
    def test_completion_barrier_four_and_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);identities={}
            for seed in (20261011,20261012):
                for arm in ('source_uniform','discrete_1_3_5'):
                    key=f'{arm}_{seed}';directory=root/key;directory.mkdir();identities[key]={'key':key}
                    for name in ('model.pth','history.json','INIT.json','latest.pth'):(directory/name).write_text('invented')
                    atomic_json(directory/'FIT_COMPLETE.json',{'completed_epochs':6,'identity':identities[key],'files_sha256':{name:sha(directory/name) for name in ('model.pth','history.json','INIT.json','latest.pth')}})
            self.assertEqual(len(completed_fits(root,identities)),4)
            with self.assertRaises(ValueError):completed_fits(root,dict(list(identities.items())[:3]))
            (root/next(iter(identities))/'model.pth').write_text('tampered')
            with self.assertRaises(ValueError):completed_fits(root,identities)
    def test_preflight_never_opens_production_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);protocol=json.loads((HERE/'protocol.json').read_text());items={}
            for key,digest in protocol['artifact_sha256'].items():
                if key in ('cache','dataset_manifest','metadata','metadata_manifest'):
                    suffix={'cache':'','dataset_manifest':'.manifest.json','metadata':'.metadata.csv','metadata_manifest':'.metadata.csv.manifest.json'}[key];path='/imaginary/cache.hdf5'+suffix
                else:path='/imaginary/baseline/'+{'checkpoint':'model.pth','run':'run.json','split_manifest':'split_manifest.json','history':'history.json','pretrain_history':'pretrain_history.json'}[key]
                items[key]={'path':path,'sha256':digest}
            plan={'schema':'chile_floor_artifact_plan_v1','artifacts':items};atomic_json(d/'plan.json',plan)
            source={'schema':'chile-clock-sources-v1','own':{name:sha(HERE/name) for name in OWN_FILES},'dependencies':SOURCES,'protocol_sha256':PROTOCOL_SHA};atomic_json(d/'source.json',source)
            args=types.SimpleNamespace(plan=d/'plan.json',plan_sha256=sha(d/'plan.json'),source_dir=SOURCE,source_manifest=d/'source.json',source_manifest_sha256=sha(d/'source.json'),max_seconds=600,initial_replay=None)
            got,_,_=preflight(args);self.assertEqual(got,plan)
            source['own']['clock_rng.py']='0'*64;atomic_json(d/'source.json',source);args.source_manifest_sha256=sha(d/'source.json')
            with self.assertRaises(ValueError):preflight(args)
    def test_output_protects_inputs_and_existing(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);plan={'artifacts':{'a':{'path':str(d/'inputs/file')}}}
            with self.assertRaises(ValueError):validate_output(d/'inputs/new',plan,d/'source')
            with self.assertRaises(ValueError):validate_output(d,plan,d/'source')
            validate_output(d/'new',plan,d/'source')
    def test_supervisor_reaps_timeout_and_removes_false_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);(d/'COMPLETE.json').write_text('{}');started=time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):supervise([sys.executable,'-c','import time;time.sleep(10)'],.1,d)
            self.assertFalse((d/'COMPLETE.json').exists());self.assertLess(time.monotonic()-started,3)
    def test_supervisor_propagates_failure(self):
        with tempfile.TemporaryDirectory() as temp:self.assertEqual(supervise([sys.executable,'-c','raise SystemExit(7)'],2,Path(temp)),7)


class MetricsTests(unittest.TestCase):
    def test_point_metrics_and_worst_tail(self):
        p=prediction(20,0);p['targets'][:]=0.;p['targets'][-1]=6.;p['mean_1s']=p['targets']+np.arange(20)
        m=scores(p)['deadlines']['1']['mean'];self.assertEqual(m['mae'],9.5);self.assertEqual(m['medae'],9.5);self.assertEqual(m['maximum'],19);self.assertEqual(m['cvar95'],19)
        self.assertAlmostEqual(m['p95'],18.05);self.assertEqual(m['tail_events'],1);self.assertEqual(m['tail_mae'],19)
    def test_paired_bootstrap_identical_and_deterministic(self):
        p=prediction();a=paired_comparison(p,p,draws=20);b=paired_comparison(p,p,draws=20);self.assertEqual(a,b)
        self.assertEqual(a['delta_discrete_minus_source']['equal_deadline_mean_mae'],0)
        self.assertEqual(a['paired_event_ci95']['1.mean.mae']['low'],0);self.assertIsNone(a['delta_discrete_minus_source']['1.mean.tail_mae'])
        self.assertEqual(a['paired_event_ci95']['1.mean.tail_mae']['valid_draws'],0)
    def test_pair_ids_and_nonfinite_fail(self):
        p=prediction();q=copy.deepcopy(p);q['event_ids']=q['event_ids'][::-1]
        with self.assertRaises(ValueError):paired_comparison(p,q,draws=1)
        p['crps_1s'][0]=float('nan')
        with self.assertRaises(ValueError):scores(p)
    def test_gate_both_seeds_margins_ci_and_probability_tradeoff(self):
        row=paired_comparison(prediction(8,.1),prediction(8,.3),draws=10);c={str(s):copy.deepcopy(row) for s in (20261011,20261012)}
        self.assertEqual(frozen_gate(c)['status'],'pass')
        c['20261012']['paired_event_ci95']['equal_deadline_mean_mae']['high']=0
        self.assertEqual(frozen_gate(c)['status'],'inconclusive')
        c['20261012']['delta_discrete_minus_source']['3.mean.medae']=.00201
        self.assertEqual(frozen_gate(c)['status'],'failed')
        with self.assertRaises(ValueError):frozen_gate({'20261011':row})
    def test_analytic_gaussian_scores(self):
        p=prediction(4,0);p['targets']=np.zeros(4)
        for t in (1,3,5):
            p[f'logits_{t}s']=np.zeros((4,5));p[f'weights_{t}s']=np.full((4,5),.2);p[f'means_{t}s']=np.zeros((4,5));p[f'scales_{t}s']=np.ones((4,5))
        scored=add_proper_scores(p,team,trainer)
        np.testing.assert_allclose(scored['nll_1s'],.5*math.log(2*math.pi),rtol=1e-14)
        np.testing.assert_allclose(scored['crps_1s'],(math.sqrt(2)-1)/math.sqrt(math.pi),rtol=1e-14)
        p['scales_1s'][0,0]=0
        with self.assertRaises(ValueError):add_proper_scores(p,team,trainer)
    def test_nested_optimizer_digest_tracks_values(self):
        from clock_synthetic import nested_digest
        left={'state':{0:{'a':torch.tensor([1.])}},'group':[.1]};right=copy.deepcopy(left)
        self.assertEqual(nested_digest(left),nested_digest(right));right['state'][0]['a'][0]=2
        self.assertNotEqual(nested_digest(left),nested_digest(right))
    def test_parent_initial_replay_identity_native_dtype_and_tolerance(self):
        p={f'{t}_{k}':np.ones((16,5),dtype=np.float32) for t in (1,3,5) for k in ('logits','means','scales')};r={k:v.astype(float) for k,v in p.items()};ids=[f'e{i}' for i in range(16)]
        self.assertEqual(compare_parameters(p,r,ids,ids)['1']['means']['max_abs_error'],0)
        with self.assertRaises(ValueError):compare_parameters(p,r,ids,ids[::-1])
        r['5_scales'][0,0]+=.01
        with self.assertRaises(ValueError):compare_parameters(p,r,ids,ids)
        r['5_scales'][0,0]=float('nan')
        with self.assertRaises(ValueError):compare_parameters(p,r,ids,ids)


if __name__=='__main__':unittest.main()
