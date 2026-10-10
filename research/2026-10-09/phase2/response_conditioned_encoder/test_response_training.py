import copy
import math
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
import torch
from synthetic_shared_fixture import fixture
from export_waveforms import write_export,complete
from response_data import CompletedExport,fit_export_normalizers,file_sha
from response_metrics import (CENTERS,point,scores,deltas,paired_bootstrap,primary_gate,SEEDS,DEADLINES,SUBSETS)
from train_response_grid import (schedules,supervised_loss,prepare,read_prepared,fit_model,predict,runtime,state_sha,verify_bundle,SOURCE_NAMES,verify_fit_protocol,completed_runs,report_grid,atomic_json,array_sha,EPOCHS,BATCH,PROTOCOL_SHA,ARMS)


def make_dataset(directory):
    raw,rows,expected,provider=fixture()
    expected['valid'][0,2]=False;expected['invalid_codes'][0,2]=64
    out=Path(directory)/'export';write_export(raw,rows,expected,provider,out,{'synthetic':True});complete(out)
    return CompletedExport(out)


class TrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):runtime()

    def test_schedule_matched_cycles_and_rng_isolation(self):
        p={1:np.array([10,20,30]),3:np.array([10,20]),5:np.array([20])}
        np.random.seed(91);before=np.random.get_state();a=schedules(p,SEEDS[0],0);after=np.random.get_state()
        self.assertTrue(all(np.array_equal(x,y) for x,y in zip(before,after)))
        b=schedules(p,SEEDS[0],0)
        for t in DEADLINES:
            np.testing.assert_array_equal(a[t],b[t]);self.assertEqual(len(a[t]),3);self.assertTrue(set(a[t])<=set(p[t]))
        self.assertEqual(set(a[1]),{10,20,30});self.assertEqual(set(a[3][:2]),{10,20})
        with self.assertRaises(ValueError):schedules({1:np.array([]),3:p[3],5:p[5]},1,0)

    def test_exact_huber_ce_and_population_weight_normalization(self):
        logits=torch.zeros(3,66,requires_grad=True);y=torch.tensor([1.,4.,5.]);w=torch.tensor([.5,1.,2.])
        value=supervised_loss(logits,y,w);pred=torch.tensor(3.25)
        ref=((1+5*(y-3.5).clamp_min(0))*torch.nn.functional.huber_loss(pred.expand_as(y),y,reduction='none')+.075*np.log(66))*w
        torch.testing.assert_close(value,ref.mean());self.assertNotAlmostEqual(float(value.detach()),float(ref.sum()/w.sum()))
        value.backward();self.assertTrue(torch.isfinite(logits.grad).all());self.assertGreater(float(logits.grad.abs().sum()),0)

    def test_normalizer_provenance_and_artifact_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            ds=make_dataset(d);prep=Path(d)/'prepared';prepare(ds,prep);norms,prov=read_prepared(ds,prep)
            self.assertEqual(prov['per_deadline_fit_population']['5']['rows'],3)
            p=json.loads((prep/'normalizers.json').read_text());p['per_deadline_fit_population']['1']['sha256']='bad';(prep/'normalizers.json').write_text(json.dumps(p))
            with self.assertRaises(ValueError):read_prepared(ds,prep)

    def test_repeated_fit_and_held_labels_do_not_change_updates(self):
        with tempfile.TemporaryDirectory() as d:
            ds=make_dataset(d);norms,_=fit_export_normalizers(ds)
            a,fa=fit_model(ds,norms,'B',SEEDS[0],'cpu',epochs=1,batch_size=3)
            ds.metadata['targets'][ds.metadata['subset']!='fit']+=100
            b,fb=fit_model(ds,norms,'B',SEEDS[0],'cpu',epochs=1,batch_size=3)
            self.assertEqual(fa['initial_state_sha256'],fb['initial_state_sha256']);self.assertEqual(state_sha(a.state_dict()),state_sha(b.state_dict()))
            self.assertEqual(fa['steps'],2);self.assertEqual(fa['order_sha256'],fb['order_sha256'])
            self.assertEqual(fa['fit_rows'],{'1':4,'3':4,'5':3})
            self.assertNotEqual(fa['initial_state_sha256'],fa['final_state_sha256'])

    def test_all_arm_initialization_orders_and_predictions(self):
        with tempfile.TemporaryDirectory() as d:
            ds=make_dataset(d);norms,_=fit_export_normalizers(ds);runs=[]
            for arm in ('A','B','C','D'):
                model,fit=fit_model(ds,norms,arm,SEEDS[0],'cpu',epochs=1,batch_size=4);runs.append(fit)
            for fit in runs:
                self.assertEqual(fit['initial_state_sha256'],runs[0]['initial_state_sha256']);self.assertEqual(fit['order_sha256'],runs[0]['order_sha256'])
            p,diagnostics=predict(model,ds,'cpu',batch_size=3)
            self.assertEqual(len(p),12);self.assertEqual(len(diagnostics),6)
            for t in DEADLINES:
                for subset in SUBSETS:
                    key=f'{t}_{subset}';np.testing.assert_array_equal(p['rows_'+key],ds.valid_rows(subset,t))
                    np.testing.assert_allclose(p['p_'+key].sum(1),1,rtol=0,atol=1e-12)

    def test_complete_grid_alignment_budget_and_report(self):
        with tempfile.TemporaryDirectory() as d:
            ds=make_dataset(d);root=Path(d)/'grid';root.mkdir();prepare(ds,root/'prepared');normalizer_sha=file_sha(root/'prepared'/'normalizers.json');pop={t:ds.valid_rows('fit',t) for t in DEADLINES};draws=max(map(len,pop.values()))
            for arm in ARMS:
                for seed in SEEDS:
                    path=root/f'{arm}_{seed}';path.mkdir();npz={}
                    for t in DEADLINES:
                        for subset in SUBSETS:
                            rows=ds.valid_rows(subset,t);key=f'{t}_{subset}';npz['rows_'+key]=rows;npz['p_'+key]=np.full((len(rows),66),1/66)
                    np.savez(path/'predictions.npz',**npz);(path/'checkpoint.pt').write_bytes(b'synthetic stub never loaded');atomic_json(path/'gain_diagnostic.json',{})
                    fit={'initial_state_sha256':'synthetic','fit_rows':{str(t):len(v) for t,v in pop.items()},'fit_weight_mean':{str(t):float(ds.metadata['sampling_weight'][v].mean()) for t,v in pop.items()},
                        'steps':EPOCHS*math.ceil(draws/BATCH),'order_sha256':[{str(t):array_sha(v) for t,v in schedules(pop,seed,e).items()} for e in range(EPOCHS)],
                        'history':[{'epoch':e+1,'draws_per_horizon':draws,'training_loss':1.} for e in range(EPOCHS)]}
                    m={'status':'complete','arm':arm,'seed':seed,'epochs':EPOCHS,'batch_size':BATCH,'protocol_sha256':PROTOCOL_SHA,'bundle_sha256':'synthetic-bundle',
                        'export_manifest_sha256':file_sha(ds.path/'manifest.json'),'normalizers_sha256':normalizer_sha,'fit':fit,'seconds':1.,
                        'outputs_sha256':{n:file_sha(path/n) for n in ('checkpoint.pt','predictions.npz','gain_diagnostic.json')}}
                    atomic_json(path/'manifest.json',m);atomic_json(path/'COMPLETE.json',{'manifest_sha256':file_sha(path/'manifest.json')})
            records,p=completed_runs(root,ds,'synthetic-bundle');self.assertEqual(len(records),8);self.assertEqual(len(p),48)
            report=report_grid(root,ds,'synthetic-bundle');self.assertEqual(len(report['scores']),72);self.assertEqual(len(report['comparisons']),6)
            self.assertEqual(report['gate']['status'],'inconclusive_support');json.dumps(report,allow_nan=False)
            fit=copy.deepcopy(records[('A',SEEDS[0])]['fit']);fit['steps']-=1
            with self.assertRaises(ValueError):verify_fit_protocol(fit,ds,SEEDS[0])
            for arm in ARMS:
                path=root/f'{arm}_{SEEDS[1]}';m=json.loads((path/'manifest.json').read_text());m['normalizers_sha256']='different-second-seed'
                atomic_json(path/'manifest.json',m);atomic_json(path/'COMPLETE.json',{'manifest_sha256':file_sha(path/'manifest.json')})
            with self.assertRaisesRegex(ValueError,'shared grid normalizers'):completed_runs(root,ds,'synthetic-bundle')
            for arm in ARMS:
                path=root/f'{arm}_{SEEDS[1]}';m=json.loads((path/'manifest.json').read_text());m['normalizers_sha256']=normalizer_sha
                atomic_json(path/'manifest.json',m);atomic_json(path/'COMPLETE.json',{'manifest_sha256':file_sha(path/'manifest.json')})
            bad=root/f'A_{SEEDS[0]}'/'predictions.npz'
            with bad.open('ab') as stream:stream.write(b'changed')
            with self.assertRaises(ValueError):completed_runs(root,ds,'synthetic-bundle')

    def test_source_bundle_exact_allowlist_and_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bundle.json';base=Path(__file__).parent
            p.write_text(json.dumps({'files':{n:file_sha(base/n) for n in SOURCE_NAMES}}));verify_bundle(p,file_sha(p))
            data=json.loads(p.read_text());data['files']['response_model.py']='0'*64;p.write_text(json.dumps(data))
            with self.assertRaises(ValueError):verify_bundle(p,file_sha(p))
            command=[sys.executable,str(base/'train_response_grid.py'),'--export',str(Path(d)/'missing'),'--bundle',str(Path(d)/'missing2'),'--bundle-sha256','0'*64,'--output',str(Path(d)/'not-created')]
            r=subprocess.run(command,text=True,capture_output=True,check=True)
            self.assertFalse(json.loads(r.stdout)['execute']);self.assertFalse((Path(d)/'not-created').exists())


class MetricTests(unittest.TestCase):
    def test_continuous_crps_pointmass_and_tail_zero_json(self):
        p=np.zeros((2,66));p[:,20]=1;y=np.array([2.05,1.95]);w=np.array([1.,3.]);events=np.array(['a','b'])
        value=scores(p,y,w,events);self.assertAlmostEqual(value['distribution']['continuous_label_crps'],.05)
        diff=deltas(value['mean'],value['mean']);self.assertIsNone(diff['m4_weighted_mae']);json.dumps(diff,allow_nan=False)
        with self.assertRaises(ValueError):scores(p*.9,y,w,events)

    def test_fractional_weighted_cvar_and_macro(self):
        value=point(np.array([0.,10.]),np.zeros(2),np.array([99.,1.]),np.array(['a','b']))
        self.assertAlmostEqual(value['cvar95'],2.);self.assertAlmostEqual(value['event_macro_mae'],5.);self.assertEqual(value['medae'],0.)

    def test_paired_bootstrap_identical_probabilities(self):
        p=np.zeros((4,66));p[:,40]=1;y=np.array([3.5,4.,4.2,5.]);w=np.array([1.,2.,1.,3.]);event=np.array(['a','b','b','c'])
        b=paired_bootstrap(p,p,y,w,event)
        for k in ('weighted_mae','medae','m4_weighted_mae','m4_event_macro_mae'):self.assertEqual(b[k],[0.,0.])
        with self.assertRaises(ValueError):paired_bootstrap(p,p,y,w,event,replicates=10)

    def test_exact_gate_all_seeds_panels_and_support(self):
        rows=[];d={'weighted_mae':.001,'medae':.001,'m4_weighted_mae':-.01,'m4_event_macro_mae':-.02}
        for t in DEADLINES:
            for subset in SUBSETS:rows.append({'seconds':t,'subset':subset,'m4_events':20,'valid_fraction':1.,'seed_deltas':{str(s):d.copy() for s in SEEDS},'bootstrap':{k:[v-.01,v] for k,v in d.items()}})
        self.assertTrue(primary_gate(rows)['pass']);self.assertEqual(primary_gate(rows[:-1])['status'],'incomplete')
        bad=copy.deepcopy(rows);bad[0]['seed_deltas'][str(SEEDS[1])]['medae']=.0021;self.assertEqual(primary_gate(bad)['status'],'failed')
        bad=copy.deepcopy(rows);bad[0]['m4_events']=19;self.assertEqual(primary_gate(bad)['status'],'inconclusive_support')
        bad=copy.deepcopy(rows);bad[0]['bootstrap']['m4_weighted_mae'][1]=0;self.assertFalse(primary_gate(bad)['pass']);self.assertEqual(primary_gate(bad)['status'],'inconclusive_precision')


if __name__=='__main__':unittest.main()
