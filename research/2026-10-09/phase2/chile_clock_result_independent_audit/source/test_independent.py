"""Invented numbers, identities, JSON/NPZ and tensor checkpoints only."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np
import torch
import independent_math as calc
import independent_artifacts as art
import checkpoint_state_body as state
import audit_saved


def prediction(y=(0.,1.,6.)):
    y=np.asarray(y,dtype=np.float64);n=len(y);p={'event_ids':np.asarray(['invented'+str(i) for i in range(n)]),'targets':y}
    for t in (1,3,5):
        logits=np.tile([0.,-1000.,-1000.,-1000.,-1000.],(n,1));w=np.tile([1.,0.,0.,0.,0.],(n,1));mu=np.zeros((n,5));s=np.ones((n,5))
        p.update({f'{k}_{t}s':v for k,v in {'logits':logits,'weights':w,'means':mu,'scales':s}.items()})
        for k,v in calc.parameter_scores(logits,w,mu,s,y).items():p[f'{k}_{t}s']=v
    return p

def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')

def hist(arm,examples=65):
    answer=[]
    for epoch in range(1,7):
        bins=[0]*3000;bins[100 if arm=='source_uniform' else 600]=examples
        trace={'sha256':{k:'a'*64 for k in (*art.PAIRED,'clock','final_mask')},'examples':examples,'batches':2,'batch_sizes':[64,1],'clock_counts':bins}
        answer.append({'epoch':epoch,'learning_rate':9e-6,'train_loss':-.2,'seconds':1.,'last_gradient_norm':2.,'trace':trace})
    return answer

class MathTests(unittest.TestCase):
    def test_single_normal_closed_forms(self):
        p=prediction((0.,));r=calc.parameter_scores(p['logits_1s'],p['weights_1s'],p['means_1s'],p['scales_1s'],p['targets'])
        self.assertAlmostEqual(r['nll'][0],.5*math.log(2*math.pi),places=13);self.assertAlmostEqual(r['crps'][0],(math.sqrt(2)-1)/math.sqrt(math.pi),places=13)
        self.assertLess(abs(r['median'][0]),1e-12);self.assertEqual(r['mean'][0],0.)
    def test_far_tail_nll_has_no_density_floor(self):
        p=prediction((20.,));self.assertAlmostEqual(p['nll_1s'][0],200+.5*math.log(2*math.pi),places=12);self.assertGreater(p['nll_1s'][0],-math.log(1e-6))
    def test_stored_weights_not_renormalized_for_actions(self):
        p=prediction((0.,));p['weights_1s'][0,0]=float(np.float32(1+4e-7));p['means_1s'][0,0]=2.
        r=calc.parameter_scores(p['logits_1s'],p['weights_1s'],p['means_1s'],p['scales_1s'],p['targets']);self.assertGreater(r['mean'][0],2.)
    def test_validation_exact26_finite_native_float32(self):
        p=prediction();calc.validate(p)
        for mutation in ('key','duplicate','dtype','nonfinite','scale','weight','native'):
            q=copy.deepcopy(p)
            if mutation=='key':q['extra']=q['targets']
            if mutation=='duplicate':q['event_ids'][1]=q['event_ids'][0]
            if mutation=='dtype':q['targets']=q['targets'].astype(np.float32)
            if mutation=='nonfinite':q['mean_1s'][0]=np.nan
            if mutation=='scale':q['scales_1s'][0,0]=0
            if mutation=='weight':q['weights_1s'][0,0]=.9
            if mutation=='native':q['means_1s'][0,0]=.1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):calc.validate(q)
    def test_saved_parameter_replay_mismatch_preserves_tolerance(self):
        p=prediction();self.assertTrue(calc.replay_arrays(p)['passed']);p['mean_3s'][0]+=.001
        r=calc.replay_arrays(p);self.assertFalse(r['passed']);self.assertEqual(r['atol'],1e-9);self.assertEqual(r['rtol'],1e-9)
    def test_linear_quantile_even_median_and_cvar(self):
        r=calc.errors(np.asarray([1.,2.,3.,4.]),np.zeros(4));self.assertEqual(r['medae'],2.5);self.assertAlmostEqual(r['p95'],3.85);self.assertEqual(r['cvar95'],4.);self.assertIsNone(r['tail_mae'])
        self.assertEqual(calc.percentile([7],.95),7.);self.assertIsNone(calc.percentile([],.025))
    def test_tail_threshold_and_bias(self):
        r=calc.errors(np.asarray([5.,7.]),np.asarray([5.5,6.]));self.assertEqual(r['tail_events'],2);self.assertEqual(r['mae'],.75);self.assertEqual(r['bias'],.25)
    def test_paired_nonlinear_bootstrap_recomputes_each_arm(self):
        p=prediction((0.,0.,0.));q=copy.deepcopy(p)
        for t in (1,3,5):p[f'mean_{t}s']=np.asarray([0.,0.,100.]);q[f'mean_{t}s']=np.asarray([0.,100.,100.])
        ix=np.tile([0,1,2],(2000,1)).astype(np.int64);r=calc.paired(p,q,ix,calc.index_digest(ix))
        self.assertEqual(r['delta_discrete_minus_source']['1.mean.medae'],-100.);self.assertEqual(r['paired_event_ci95']['1.mean.medae']['low'],-100.);self.assertIsNone(r['delta_discrete_minus_source']['1.mean.tail_mae']);self.assertEqual(r['paired_event_ci95']['1.mean.tail_mae']['valid_draws'],0)
    def test_zero_tail_draw_omission_only_applies_to_tail(self):
        p=prediction();ix=np.tile([0,0,0],(2000,1)).astype(np.int64);ix[:100]=[2,2,2];r=calc.paired(p,p,ix,calc.index_digest(ix))
        self.assertEqual(r['paired_event_ci95']['1.mean.tail_mae']['valid_draws'],100);self.assertEqual(r['paired_event_ci95']['1.mean.mae']['valid_draws'],2000)
    def test_index_shape_range_checksum_and_shared_identity_guards(self):
        p=prediction();ix=np.tile([0,1,2],(2000,1)).astype(np.int64)
        for changed in (ix[:1],ix.astype(np.int32),np.full_like(ix,3)):
            with self.assertRaises(ValueError):calc.validate_indices(changed,3,calc.index_digest(ix))
        with self.assertRaises(ValueError):calc.validate_indices(ix,3,'0'*64)
        q=copy.deepcopy(p);q['event_ids']=q['event_ids'][::-1]
        with self.assertRaisesRegex(ValueError,'alignment'):calc.paired(q,p,ix,calc.index_digest(ix))
    def test_gate_both_seeds_points_before_uncertainty(self):
        p=prediction();ix=np.tile([0,1,2],(2000,1)).astype(np.int64);r=calc.paired(p,p,ix,calc.index_digest(ix));rows={str(s):copy.deepcopy(r) for s in (20261011,20261012)}
        self.assertEqual(calc.gate(rows)['status'],'failed')
        for row in rows.values():row['delta_discrete_minus_source']['equal_deadline_mean_mae']=-.1
        self.assertEqual(calc.gate(rows)['status'],'inconclusive')
        for row in rows.values():row['paired_event_ci95']['equal_deadline_mean_mae']['high']=-.01
        self.assertEqual(calc.gate(rows)['status'],'pass');rows['20261012']['delta_discrete_minus_source']['3.mean.medae']=.003
        self.assertEqual(calc.gate(rows)['status'],'failed')
    def test_probability_and_worst_error_tradeoffs_do_not_change_gate(self):
        p=prediction();ix=np.tile([0,1,2],(2000,1)).astype(np.int64);r=calc.paired(p,p,ix,calc.index_digest(ix));r['delta_discrete_minus_source']['equal_deadline_mean_mae']=-.1;r['paired_event_ci95']['equal_deadline_mean_mae']['high']=-.01;r['delta_discrete_minus_source']['1.nll']=.01;r['delta_discrete_minus_source']['5.mean.maximum']=.02
        g=calc.gate({str(s):copy.deepcopy(r) for s in (20261011,20261012)});self.assertEqual(g['status'],'pass');self.assertTrue(g['checks']['20261011']['proper_nll_tradeoff']);self.assertEqual(g['checks']['20261011']['mean_worst_error_regression']['5'],['maximum'])

class ArtifactTests(unittest.TestCase):
    def grid_fixture(self,root,mutation=None):
        identity={'protocol_sha256':art.PROTOCOL,'source_manifest_sha256':art.SOURCE_MANIFEST,'epochs':6,'batch_size':64,'optimizer':art.OPTIMIZER,'baseline_initial_state_sha256':art.BASELINE_STATE,'fit_ids_sha256':art.FIT_IDS,'runtime':{'torch':'invented_runtime'},'baseline_artifact_sha256':{}}
        dump(root/'STARTED.json',{'protocol_sha256':art.PROTOCOL,'source_manifest_sha256':art.SOURCE_MANIFEST,'plan_sha256':art.PLAN});dump(root/'grid_identity.json',identity)
        for fit in art.FITS:
            arm,seed=fit.rsplit('_',1);i=identity|{'arm':arm,'seed':int(seed)}
            dump(root/fit/'history.json',hist(arm));init={'identity':i,'model_state_sha256':art.BASELINE_STATE,'optimizer_state_entries':0,'model_rng_sha256':'a'*64,'generator_state_sha256':'b'*64}
            if mutation=='init' and fit==art.FITS[1]:init['generator_state_sha256']='c'*64
            dump(root/fit/'INIT.json',init)
            for n in ('model.pth','latest.pth'):(root/fit/n).write_bytes(b'invented hashed body, not deserialized')
            r={'identity':i,'completed_epochs':5 if mutation=='epoch' and fit==art.FITS[1] else 6,'files_sha256':{n:art.file_pin(root/fit/n)['sha256'] for n in ('model.pth','latest.pth','history.json','INIT.json')}};dump(root/fit/'FIT_COMPLETE.json',r)
        dump(root/'TRAINING_COMPLETE.json',{'keys':list(art.FITS),'fit_seconds':30.,'fit_completion_sha256':{fit:art.file_pin(root/fit/'FIT_COMPLETE.json')['sha256'] for fit in art.FITS}});dump(root/'report.json',{})
        for split in ('calibration','dev'):
            for fit in (*art.FITS,'starting_epoch97'):(root/f'{split}_{fit}_predictions.npz').write_bytes(b'invented hashed body, not decoded')
        artifacts={str(p.relative_to(root)):art.file_pin(p)['sha256'] for p in root.rglob('*') if p.is_file()}
        if mutation=='missing':del artifacts[art.FITS[0]+'/model.pth']
        dump(root/'COMPLETE.json',{'schema':'chile-clock-grid-complete-v1','protocol_sha256':art.PROTOCOL,'source_manifest_sha256':art.SOURCE_MANIFEST,'plan_sha256':art.PLAN,'test_reads':0,'selection':'fixed_final6','fits':4,'artifacts_sha256':artifacts})
        return art.file_pin(root/'COMPLETE.json')
    def test_complete34_member_barrier_and_fit_init_failures(self):
        execution={'worker_exit_code':0,'supervisor_exit_code':0,'preservation_complete':True}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pin=self.grid_fixture(root);r=art.grid(root,pin,execution);self.assertEqual(len(r['pins']),34);self.assertEqual(len(r['histories']),4)
        for mutation in ('missing','epoch','init'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);pin=self.grid_fixture(root,mutation)
                with self.assertRaises(ValueError):art.grid(root,pin,execution)
    def test_original_split_identity_exhaustion_and_repetition_thresholds(self):
        ids=['invented'+str(i) for i in range(5)];parts={'fit':(ids[:3],[0,1,2]),'calibration':(ids[3:4],[3]),'dev':(ids[4:],[4])}
        split={k:{'event_ids':v[0],'source_rows':v[1],'ids_sha256':art.ids_digest(v[0])} for k,v in parts.items()};run={k+suffix:value for k,v in split.items() for suffix,value in (('_ids_sha256',v['ids_sha256']),('_events',len(v['event_ids'])))};manifest={'author_split_boundaries':[4,5],'cache_rows':5,'splits':{'train':{'ids_sha256':art.ids_digest(ids[:4])},'dev':{'ids_sha256':art.ids_digest(ids[4:])}}}
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'metadata.csv';p.write_text('EVENT,MA,TIME,source_row_index,benchmark_split\n'+''.join(f'{e},{y},100,{i},{"train" if i<4 else "dev"}\n' for i,(e,y) in enumerate(zip(ids,[4.,5.,6.,5.5,6.]))))
            with mock.patch.object(art,'FIT_IDS',art.ids_digest(ids[:3])):
                r=art.split_and_targets(split,run,manifest,p,art.file_pin(p));self.assertEqual(r['training_examples_per_epoch'],25);self.assertEqual(r['targets']['calibration'].tolist(),[5.5])
                q=copy.deepcopy(split);q['dev']['source_rows']=[3]
                with self.assertRaises(ValueError):art.split_and_targets(q,run,manifest,p,art.file_pin(p))
            with self.assertRaisesRegex(ValueError,'TRAIN-fit'):art.split_and_targets(split,run,manifest,p,art.file_pin(p))
    def test_trace_pairing_clock_support_and_remainder(self):
        h={fit:hist('source_uniform' if fit.startswith('source_uniform') else 'discrete_1_3_5') for fit in art.FITS};self.assertTrue(art.traces(h,65)['passed'])
        for mutation in ('pair','clock','remainder','loss'):
            q=copy.deepcopy(h);r=q[art.FITS[1]][0]
            if mutation=='pair':r['trace']['sha256']['label_draw']='b'*64
            if mutation=='clock':r['trace']['clock_counts'][600]=0;r['trace']['clock_counts'][700]=65
            if mutation=='remainder':r['trace']['batch_sizes']=[64]
            if mutation=='loss':r['train_loss']=float('nan')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):art.traces(q,65)
    def test_artifact_path_traversal_symlink_and_size_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);f=root/'f';f.write_bytes(b'abc');(root/'link').symlink_to(f)
            for n in ('../f','/tmp/f','link'):
                with self.assertRaises(ValueError):art.contained(root,n)
            with self.assertRaises(ValueError):art.file_pin(f,2)
    def test_saved_archive_pickle_disabled_and_exact_member_bounds(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/'p.npz';p=prediction();np.savez_compressed(f,**p);q=art.prediction_archive(f,art.file_pin(f));self.assertTrue(calc.replay_arrays(q)['passed'])
            p['event_ids']=np.asarray([object()],dtype=object);np.savez_compressed(f,**p)
            with self.assertRaises(ValueError):art.prediction_archive(f,art.file_pin(f))
    def test_incomplete_grid_rejected_before_any_checkpoint_load(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);dump(root/'COMPLETE.json',{'fits':3})
            with self.assertRaisesRegex(ValueError,'barrier'):art.grid(root,art.file_pin(root/'COMPLETE.json'),{'worker_exit_code':0,'supervisor_exit_code':0,'preservation_complete':True})
            with self.assertRaisesRegex(ValueError,'normal'):art.grid(root,art.file_pin(root/'COMPLETE.json'),{'worker_exit_code':-9,'supervisor_exit_code':0,'preservation_complete':True})
    def test_bootstrap_backend_or_private_file_required(self):
        rng=np.random.default_rng(20261013);ix=np.asarray([rng.integers(0,3,3) for _ in range(2000)],dtype=np.int64);digest=calc.index_digest(ix)
        item={'seed':20261013,'draws':2000,'events':3,'dtype':'int64','calls':'2000 successive integers(0,N,N)','pairing':'same indices across both arms/actions/deadlines; reset per split/seed','numpy_version':np.__version__,'backend':type(rng.bit_generator).__name__,'canonical_sha256_by_seed':{str(s):digest for s in (20261011,20261012)}}
        actual,_=audit_saved.load_indices(item,3,np.__version__);self.assertTrue(np.array_equal(actual,ix));item['backend']='invented_other'
        with self.assertRaisesRegex(ValueError,'backend'):audit_saved.load_indices(item,3,np.__version__)
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/'indices.npy';np.save(f,ix);item['file']={'path':str(f),'pin':art.file_pin(f)};actual,_=audit_saved.load_indices(item,3,np.__version__);self.assertTrue(np.array_equal(actual,ix))
    def test_guard_rejects_unbound_actual_execution_before_data(self):
        with self.assertRaisesRegex(ValueError,'source-bound'):audit_saved.inspect({'schema':'invented'})
    def test_restricted_load_checks_hash_before_call(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/'a';f.write_bytes(b'not pickle');fake=mock.Mock()
            with self.assertRaisesRegex(ValueError,'before deserialization'):state.load_checkpoint(f,{'bytes':1,'sha256':'0'*64},fake)
            fake.load.assert_not_called()
    def test_independent_tensor_digest_and_restricted_toy_loading(self):
        values={'z':torch.tensor([2.],dtype=torch.float32),'a':torch.tensor([3,4],dtype=torch.int64)};h=hashlib.sha256()
        for name,dtype,shape,data in [('a','torch.int64',[2],np.asarray([3,4],dtype=np.int64).tobytes()),('z','torch.float32',[1],np.asarray([2.],dtype=np.float32).tobytes())]:h.update(name.encode()+b'\0'+json.dumps([dtype,shape],separators=(',',':')).encode()+b'\0'+data)
        self.assertEqual(state.digest(values),h.hexdigest())
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/'toy.pth';torch.save(values,f);actual=state.load_checkpoint(f,art.file_pin(f),torch);self.assertEqual(state.digest(actual),h.hexdigest())
    def test_recorded_runtime_mismatch_precedes_checkpoint_reads(self):
        with mock.patch.object(state,'load_checkpoint') as load:
            with self.assertRaisesRegex(ValueError,'recorded'):state.inspect({'expected_runtime':{'python':'wrong'}},torch,np)
            load.assert_not_called()
    def state_fixture(self,root,mutation=None):
        baseline=root/'baseline.pth';torch.save({'model':{'weight':torch.tensor([1.,2.])},'config':{},'selected_epoch':97},baseline)
        req={'expected_runtime':{'python':sys.version,'torch':str(torch.__version__),'numpy':np.__version__,'byteorder':sys.byteorder},'execution':{'worker_exit_code':0,'supervisor_exit_code':0,'preservation_complete':True},'baseline':{'path':str(baseline),'pin':art.file_pin(baseline),'expected_state_sha256':state.digest({'weight':torch.tensor([1.,2.])})},'fits':{}}
        members={}
        for fit in art.FITS:
            arm,seed=fit.rsplit('_',1);identity={'arm':arm,'seed':int(seed)};history=hist(arm)
            model={'weight':torch.tensor([3.,4.])};streams={k:torch.tensor([1,2],dtype=torch.uint8) for k in ('clock','station_count','station_rank','label')}
            if mutation=='rng' and fit==art.FITS[1]:streams['label'][0]=9
            opt={'param_groups':[{'params':[0],'lr':9e-6,'betas':(.9,.999),'eps':1e-8,'weight_decay':0,'amsgrad':False}],'state':{0:{'step':torch.tensor(12.),'exp_avg':torch.zeros(2),'exp_avg_sq':torch.ones(2)}}}
            final={'schema':'chile-clock-final-v1','model':model,'identity':identity,'completed_epochs':6}
            latest={'schema':'chile-clock-completed-epoch-v1','completed_epoch':6,'model':copy.deepcopy(model),'optimizer':opt,'streams':streams,'model_rng':{'cpu':torch.tensor([1,2],dtype=torch.uint8),'cuda':torch.tensor([3,4],dtype=torch.uint8)},'python_rng':(3,(1,2),None),'numpy_rng':{'algorithm':'MT19937','keys':[1,2],'position':0,'has_gauss':0,'cached_gaussian':0.},'identity':identity,'history':history,'resume_supported':False}
            if mutation=='state' and fit==art.FITS[1]:latest['model']['weight'][0]=99.
            if mutation=='step' and fit==art.FITS[1]:latest['optimizer']['state'][0]['step']=torch.tensor(11.)
            req['fits'][fit]={'identity':identity,'history':history}
            for name,payload in (('model',final),('latest',latest)):
                p=root/fit/(name+'.pth');p.parent.mkdir(parents=True,exist_ok=True);torch.save(payload,p);member={'path':str(p),'pin':art.file_pin(p)};req['fits'][fit][name]=member;members[fit+'/'+name+'.pth']=member['pin']['sha256']
        c=root/'COMPLETE.json';dump(c,{'schema':'chile-clock-grid-complete-v1','fits':4,'test_reads':0,'selection':'fixed_final6','protocol_sha256':art.PROTOCOL,'source_manifest_sha256':art.SOURCE_MANIFEST,'plan_sha256':art.PLAN,'artifacts_sha256':members});req['complete']={'path':str(c),'pin':art.file_pin(c)}
        return req
    def test_restricted_toy_final_latest_optimizer_rng_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            req=self.state_fixture(Path(temp));r=state.inspect(req,torch,np)
            self.assertTrue(r['all_checks_pass']);self.assertEqual(len(r['fits']),4);self.assertEqual(r['forwards'],0);self.assertTrue(r['paired_rng']['20261012']['clock_state_exempt'])
    def test_restricted_state_step_rng_mutations_rejected(self):
        for mutation,reason in (('state','tensor state'),('step','Adam steps'),('rng','nonclock RNG')):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp:
                req=self.state_fixture(Path(temp),mutation)
                with self.assertRaisesRegex(ValueError,reason):state.inspect(req,torch,np)

if __name__=='__main__':unittest.main(verbosity=2)
