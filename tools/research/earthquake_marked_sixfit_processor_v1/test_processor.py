"""Invented optimizer, causal permissions, failure custody and fixed score gates."""
import copy
import math
import time
import unittest
from unittest import mock
import numpy as np
import torch
import fixtures as f
import numeric_state as ns
import processor as p


def checked(raw):return ns.decode(raw,ns.digest(raw))


class ProcessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1);cls.packet=f.packet();cls.bindings=f.bindings();cls.sink=f.Sink();start=time.monotonic()
        cls.raw=p.prepare(cls.packet,cls.bindings,cls.sink,processing_begin=start);a=time.monotonic()-start
        cls.adm=checked(cls.raw);cls.pin=ns.digest(cls.raw);cls.fit_sink=f.Sink();start=time.monotonic()
        cls.fit=p.fit_one(cls.packet,cls.raw,cls.pin,cls.bindings,cls.fit_sink,seed=p.SEEDS[0],arm='D',processing_begin=start);b=time.monotonic()-start
        cls.final=checked(cls.fit['checkpoint']);cls.score_sink=f.Sink();start=time.monotonic()
        cls.score=p.score_final(cls.packet,cls.raw,cls.pin,cls.fit['checkpoint'],cls.fit['receipt']['sha256'],cls.bindings,cls.score_sink,processing_begin=start)
        cls.result=checked(cls.score['result']);print('INVENTED admission/D300/D66seconds',a,b,time.monotonic()-start)

    def test_six_gradient_unions_same_prior_bytes_and_actual_capacity(self):
        self.assertEqual([(x['seed'],x['arm']) for k,x,_ in self.sink.records if k=='initial'],list(p.ORDER))
        schema=self.adm['schema'];k=len(schema['static']['kept'])
        for seed in p.SEEDS:
            items=[self.adm['models'][f'{seed}:{a}'] for a in p.ARMS];self.assertEqual(len(set(x['prior_sha256'] for x in items)),1)
            for arm,item in zip(p.ARMS,items):
                self.assertEqual(item['probe']['terms'],195);self.assertEqual(item['probe']['used'],item['probe']['total']);self.assertTrue(all(v.all() for v in item['probe']['masks'].values()))
                model=p.model_for(self.bindings,schema,seed,arm);self.assertEqual(sum(v.numel() for v in model.parameters()),self.adm['capacity'][arm])
        self.assertEqual(self.adm['capacity']['S'],16*k+544);self.assertEqual(self.adm['capacity']['D'],16*k+527+len(schema['summary']['active']))
        self.assertTrue(all(j not in schema['summary']['active'] for j in (4,9,14)))
        self.assertLessEqual(max(self.adm['capacity'].values())/min(self.adm['capacity'].values()),1.05)

    def test_scalers_initialization_ignore_dev_targets_context(self):
        changed=copy.deepcopy(self.packet)
        for r in changed['rows']:
            if r['partition']=='DEV':
                r['mw']+=.7
                if r['common']:r['precontext'][8:11]+=100.
        raw=p.prepare(changed,self.bindings,f.Sink(),processing_begin=time.monotonic());other=checked(raw)
        self.assertEqual(ns.encode(self.adm['schema']),ns.encode(other['schema']))
        for key in self.adm['models']:self.assertEqual(ns.encode(self.adm['models'][key]['initial']),ns.encode(other['models'][key]['initial']))
        self.assertNotEqual(self.adm['packet_sha256'],other['packet_sha256'])

    def test_current_marks_activity_cannot_change_prior(self):
        row=copy.deepcopy(self.packet['rows'][4]);initial=p.context(row,self.adm['schema']['static'])
        row['horizons'][2]['reported'][:]=123.;row['horizons'][0]['states'][:]=1
        self.assertTrue(torch.equal(initial,p.context(row,self.adm['schema']['static'])))
        self.assertEqual(self.adm['schema']['static']['reference_keep'],list(p.KEEP))

    def test_rank_reconstruction_fixed_order(self):
        train=[copy.deepcopy(self.packet['rows'][i]) for i in self.adm['schema']['train']]
        for r in train:r['precontext'][9]=2*r['precontext'][8]+3
        s=p.static_scaler(train);self.assertIn(p.KEEP.index(8),s['kept']);self.assertNotIn(p.KEEP.index(9),s['kept'])
        self.assertLessEqual(s['reconstruction_max_abs'],1e-10);self.assertEqual(s['kept'],sorted(s['kept']))

    def test_dev_censor_stops_whole_admission_before_optimizer(self):
        packet=copy.deepcopy(self.packet);row=next(r for r in packet['rows'] if r['common'] and r['partition']=='DEV')
        for h in row['horizons']:
            h['ratios'][0,0]=0.;h['reported'][0,0]=-12.;h['censor'][0,0]=1;h['max_ratios'][0]=max(h['ratios'][0]);h['states'][0]=int(h['max_ratios'][0]>9)
        sink=f.Sink()
        with mock.patch.object(torch.optim,'Adam',side_effect=AssertionError('forbidden')):
            with self.assertRaises(p.Failure):p.prepare(packet,self.bindings,sink,processing_begin=time.monotonic())
        self.assertFalse(any(k=='initial' for k,_,_ in sink.records));self.assertEqual(len(packet['rows']),115)

    def test_exact_300_unique_batches_and_no_dummy_gradients(self):
        ids=self.adm['schema']['train'];order=p.event_order(ids,p.SEEDS[0]);rng=np.random.default_rng(p.SEEDS[0]+1009)
        self.assertEqual(order.shape,(300,8))
        for row in order:self.assertEqual(len(set(row)),8);self.assertTrue(np.array_equal(row,rng.choice(ids,8,replace=False)))
        self.assertTrue(np.array_equal(order,np.asarray([x['ordinals'] for x in self.final['history']])))
        model=p.model_for(self.bindings,self.adm['schema'],p.SEEDS[0],'D');model.register_parameter('dummy',torch.nn.Parameter(torch.zeros(1,dtype=torch.float64)))
        with self.assertRaises(p.Failure):p.gradient_probe(model,[self.packet['rows'][i] for i in ids],self.adm['schema'],self.bindings,time.monotonic())

    def test_300_updates_learn_signal_then_final_checkpoint(self):
        self.assertEqual(len([k for k,_,_ in self.fit_sink.records if k=='step']),300);self.assertEqual(self.fit_sink.records[-1][0],'final')
        self.assertLess(self.final['history'][-1]['loss'],self.final['history'][0]['loss']);self.assertEqual(self.final['status'],'final')
        self.assertNotEqual(ns.encode(self.adm['models'][f'{p.SEEDS[0]}:D']['initial']),ns.encode(self.final['parameters']))
        self.assertEqual(self.final['final_probe']['terms'],195)
        for entry in self.final['optimizer'].values():self.assertEqual(float(entry['step']),300.)

    def test_partial_update_callback_failure_retains_state(self):
        sink=f.Sink('step',2)
        with self.assertRaises(p.Failure) as e:p.fit_one(self.packet,self.raw,self.pin,self.bindings,sink,seed=p.SEEDS[0],arm='D',processing_begin=time.monotonic())
        self.assertEqual(e.exception.evidence['update'],2);self.assertEqual(len(e.exception.evidence['history']),2)
        self.assertFalse(any(k=='final' for k,_,_ in sink.records));self.assertEqual(sink.records[-1][0],'failure')
        for entry in e.exception.evidence['optimizer'].values():self.assertEqual(float(entry['step']),2.)

    def test_initial_callback_failure_prevents_optimizer(self):
        with mock.patch.object(torch.optim,'Adam',side_effect=AssertionError('forbidden')):
            with self.assertRaises(p.Failure) as e:p.fit_one(self.packet,self.raw,self.pin,self.bindings,f.Sink('begin_fit'),seed=p.SEEDS[0],arm='D',processing_begin=time.monotonic())
        self.assertEqual(e.exception.evidence['update'],0)

    def test_final_callback_failure_never_success(self):
        with self.assertRaises(p.Failure) as e:p.fit_one(self.packet,self.raw,self.pin,self.bindings,f.Sink('final'),seed=p.SEEDS[0],arm='D',processing_begin=time.monotonic())
        self.assertEqual(e.exception.evidence['update'],300);self.assertEqual(e.exception.evidence['status'],'failure')

    def test_score_all66_proper_fields_no_optimizer(self):
        self.assertEqual(len(self.result['predictions']),66)
        for record in self.result['predictions']:p.validate_forecast(record);self.assertTrue(record['diagnostics']['allpositive_only']);self.assertIn('reference',record['source'])
        with mock.patch.object(torch.optim,'Adam',side_effect=AssertionError('forbidden')):
            result=p.score_final(self.packet,self.raw,self.pin,self.fit['checkpoint'],self.fit['receipt']['sha256'],self.bindings,f.Sink(),processing_begin=time.monotonic())
        self.assertEqual(checked(result['result'])['status'],'complete')

    def test_real_shared_s_300_updates_and_full66_proper_scores(self):
        sink=f.Sink();start=time.monotonic()
        fit=p.fit_one(self.packet,self.raw,self.pin,self.bindings,sink,seed=p.SEEDS[0],arm='S',processing_begin=start)
        elapsed=time.monotonic()-start;final=checked(fit['checkpoint']);self.assertEqual(final['update'],300)
        self.assertNotEqual(ns.encode(final['parameters']['coefficients']),ns.encode(self.adm['models'][f'{p.SEEDS[0]}:S']['initial']['coefficients']))
        start=time.monotonic();result=p.score_final(self.packet,self.raw,self.pin,fit['checkpoint'],fit['receipt']['sha256'],self.bindings,f.Sink(),processing_begin=start)
        scored=checked(result['result']);self.assertEqual(len(scored['predictions']),66)
        for record in scored['predictions']:
            self.assertEqual(record['source']['log_weights'].shape,(60,));self.assertAlmostEqual(float(record['source']['noise_probabilities'].sum()),1.,places=12)
            self.assertLessEqual(record['diagnostics']['errors']['crps'],1e-6)
        print('INVENTED S300/S66seconds',elapsed,time.monotonic()-start)

    def test_future_suffix_does_not_change_earlier_posterior_and_first_cell_once(self):
        model=p.model_for(self.bindings,self.adm['schema'],p.SEEDS[0],'S');row=copy.deepcopy(self.packet['rows'][4])
        first=p.posterior(model,row,0,self.adm['schema'],self.bindings,time.monotonic())
        row['horizons'][2]['reported'][4:]+=3.
        unchanged=p.posterior(model,row,0,self.adm['schema'],self.bindings,time.monotonic())
        self.assertTrue(torch.equal(first.logw,unchanged.logw));self.assertTrue(torch.equal(first.mu,unchanged.mu))
        self.assertEqual(len(first.reference['facts']),len(row['horizons'][0]['reported']))

    def test_score_partial_failure_retains_rows(self):
        with self.assertRaises(p.Failure) as e:p.score_final(self.packet,self.raw,self.pin,self.fit['checkpoint'],self.fit['receipt']['sha256'],self.bindings,f.Sink('forecast'),processing_begin=time.monotonic())
        self.assertEqual(len(e.exception.evidence['predictions']),1);self.assertEqual(e.exception.evidence['status'],'incomplete')

    def test_checkpoint_299_packet_mutation_expiry_receipt_rejected(self):
        c=copy.deepcopy(self.final);c['update']=299;raw=ns.encode(c)
        with self.assertRaises(p.Failure):p.score_final(self.packet,self.raw,self.pin,raw,ns.digest(raw),self.bindings,f.Sink(),processing_begin=time.monotonic())
        packet=copy.deepcopy(self.packet);packet['rows'][4]['mw']+=.1
        with self.assertRaises(p.Failure):p.bind_admission(packet,self.raw,self.pin,self.bindings,time.monotonic())
        with self.assertRaises(p.Failure):p.prepare(self.packet,self.bindings,f.Sink(),processing_begin=time.monotonic()-301)
        with self.assertRaises(p.Failure):p.publish(lambda k,b:dict(status='durable',sha256='0'*64),'x',{'x':1})

    def test_probe_failure_retains_current_initial_receipt_and_partial_union(self):
        real=p.posterior;count=[0];sink=f.Sink()
        def fail_after_one(*args,**kwargs):
            count[0]+=1
            if count[0]==2:raise p.Failure('invented probe failure',{'point':2})
            return real(*args,**kwargs)
        with mock.patch.object(p,'posterior',side_effect=fail_after_one):
            with self.assertRaises(p.Failure) as error:
                p.prepare(self.packet,self.bindings,sink,processing_begin=time.monotonic())
        evidence=error.exception.evidence;self.assertEqual(len(evidence['completed']),0)
        current=evidence['current'];self.assertEqual(current['initial_receipt']['sha256'],ns.digest(sink.records[0][2]))
        self.assertEqual(current['probe']['terms_completed'],1)
        self.assertTrue(any(v.any() for v in current['probe']['masks'].values()))
        self.assertEqual(current['probe']['current']['horizon'],3)
        self.assertEqual(sink.records[-1][0],'admission_failure')
        self.assertEqual(sink.records[-1][1]['current']['probe']['terms_completed'],1)

    def test_reference_failure_retains_current_source_input_and_work(self):
        def reject(post,target,reference):
            post.budget.check(17,31)
            raise f.core.NumericalFailure('invented parity',{'errors':{'mean':.5},'work':{'density_points':9}})
        sink=f.Sink()
        with mock.patch.object(self.bindings.operator,'checked_scores',side_effect=reject):
            with self.assertRaises(p.Failure) as error:
                p.score_final(self.packet,self.raw,self.pin,self.fit['checkpoint'],self.fit['receipt']['sha256'],self.bindings,sink,processing_begin=time.monotonic())
        evidence=error.exception.evidence;self.assertEqual(len(evidence['predictions']),0)
        self.assertEqual(evidence['current_record']['ordinal'],self.adm['schema']['dev'][0]);self.assertEqual(evidence['current_record']['horizon'],1)
        self.assertIn('source',evidence['current_record']);self.assertIn('marks',evidence['current_record'])
        self.assertGreaterEqual(evidence['current_work']['density_points'],17);self.assertEqual(evidence['exception_evidence']['errors']['mean'],.5)
        self.assertEqual(sink.records[-1][0],'score_failure');self.assertIn('source',sink.records[-1][1]['current_record'])

    def test_nonfinite_failure_retains_rejected_ieee_evidence(self):
        class Bad:
            def nll(self,target):return torch.tensor(float('nan'),dtype=torch.float64,requires_grad=True)
        sink=f.Sink()
        with mock.patch.object(p,'posterior',return_value=Bad()):
            with self.assertRaises(p.Failure) as error:
                p.fit_one(self.packet,self.raw,self.pin,self.bindings,sink,seed=p.SEEDS[0],arm='D',processing_begin=time.monotonic())
        self.assertEqual(error.exception.evidence['update'],0)
        failed=[obj for kind,obj,_ in sink.records if kind=='failure'][-1]
        self.assertIn('nonfinite_scalar_bits',failed['current']['loss'])

    def test_late_final_callback_cannot_pass_and_score_has900_not300_budget(self):
        original=p.deadline;expired=[False];sink=f.Sink()
        def callback(kind,raw):
            receipt=sink(kind,raw)
            if kind=='final':expired[0]=True
            return receipt
        def check(begin,seconds):
            if expired[0]:raise p.Failure('source_deadline')
            return original(begin,seconds)
        with mock.patch.object(p,'deadline',side_effect=check):
            with self.assertRaises(p.Failure):
                p.fit_one(self.packet,self.raw,self.pin,self.bindings,callback,seed=p.SEEDS[0],arm='D',processing_begin=time.monotonic())
        self.assertEqual(sink.records[-1][0],'failure')
        result=p.score_final(self.packet,self.raw,self.pin,self.fit['checkpoint'],self.fit['receipt']['sha256'],self.bindings,f.Sink(),processing_begin=time.monotonic()-350)
        self.assertEqual(result['status'],'complete')

    def test_plugin_300_updates_and_complete66(self):
        start=time.monotonic();fit=p.fit_one(self.packet,self.raw,self.pin,self.bindings,f.Sink(),seed=p.SEEDS[1],arm='P',processing_begin=start)
        elapsed=time.monotonic()-start;start=time.monotonic()
        score=p.score_final(self.packet,self.raw,self.pin,fit['checkpoint'],fit['receipt']['sha256'],self.bindings,f.Sink(),processing_begin=start)
        result=checked(score['result']);self.assertEqual(len(result['predictions']),66)
        self.assertTrue(all(x['source']['log_weights'].shape==(5,) and x['source']['noise_probabilities'] is None for x in result['predictions']))
        print('INVENTED P300/P66seconds',elapsed,time.monotonic()-start)

    def comparisons(self):
        new=[];old=[]
        for seed in p.SEEDS:
            for arm in ('S','P','D','B','F','H','T'):
                result=copy.deepcopy(self.result);result.update(seed=seed,arm=arm)
                for v in result['predictions']:
                    v.update(seed=seed,arm=arm,mean=v['target']+(.1 if arm=='S' else .3),median=v['target'],nll=.1 if arm=='S' else .3,crps=.1 if arm=='S' else .3,pit=.5)
                    v['quantiles']={str(q):v['target']+(q-.5)*2 for q in (.025,.1,.25,.5,.75,.9,.975)}
                    for level in (50,80,95):v['coverage_'+str(level)]=True
                    if arm in ('S','P'):
                        # Invented schema-complete guard fixtures, not independent scientific replay.
                        row=self.packet['rows'][v['ordinal']];marks=row['horizons'][p.HORIZONS.index(v['horizon'])]['reported']
                        source=v['source'];source['reference']['arm']=arm;source['reference']['nu']=row['noise']['nu'].copy()
                        source['reference']['facts']=[[np.zeros(3,dtype='<f8'),np.zeros(3,dtype='<f8'),np.ones(3,dtype='<f8'),q.copy()] for q in marks]
                        if arm=='S':
                            for key in ('log_weights','means','scales'):source[key]=np.tile(source[key],12)
                            source['log_weights']-=math.log(12);source['noise_probabilities']=np.ones(12,dtype='<f8')/12
                if arm in p.ARMS:new.append(result)
                else:
                    if arm in ('B','F'):
                        for v in result['predictions']:del v['quantiles']
                    result['independent_closure']=dict(verified=True,no_optimizer=True,checkpoint_sha256=result['checkpoint_sha256'],source_sha256='b'*64,packet_sha256=result['packet_sha256']);old.append(result)
        return new,old

    def test_original24_new12_and_mandatory_closed_strong(self):
        new,old=self.comparisons();r=p.aggregate(self.packet,self.raw,self.pin,new,old,self.bindings,processing_begin=time.monotonic())
        self.assertTrue(r['pass_all']);self.assertEqual(len(r['original24']),24);self.assertEqual(len(r['additional12']),12)
        old[0]['independent_closure']['verified']=False;r=p.aggregate(self.packet,self.raw,self.pin,new,old,self.bindings,processing_begin=time.monotonic())
        self.assertFalse(r['pass_all']);self.assertEqual(r['status'],'incomplete')

    def test_one_tail_worst_proper_failure_not_averaged(self):
        for failure in ('proper','worst','tail'):
            new,old=self.comparisons();v=new[0]['predictions'][0]
            if failure=='proper':v['nll']=100.
            elif failure=='worst':v['mean']=v['target']+2.
            else:
                for row in new[0]['predictions']:
                    if row['horizon']==1 and row['target']>=5.5:row['mean']=row['target']+.3
            r=p.aggregate(self.packet,self.raw,self.pin,new,old,self.bindings,processing_begin=time.monotonic());self.assertFalse(r['pass_all'],failure);self.assertEqual(r['status'],'complete')

    def test_new_missing_or_rejected_numerical_evidence_is_incomplete(self):
        for mutation in ('source','diagnostics','parity','work','shape','future'):
            new,old=self.comparisons();v=new[0]['predictions'][0]
            if mutation in ('source','diagnostics'):del v[mutation]
            elif mutation=='parity':v['diagnostics']['errors']['crps']=1e-3
            elif mutation=='work':v['diagnostics']['work']['density_points']=1000001
            elif mutation=='shape':v['source']['means']=np.zeros(5,dtype='<f8')
            else:v['source']['reference']['facts'].append(copy.deepcopy(v['source']['reference']['facts'][-1]))
            result=p.aggregate(self.packet,self.raw,self.pin,new,old,self.bindings,processing_begin=time.monotonic())
            self.assertEqual(result['status'],'incomplete',mutation);self.assertFalse(result['pass_all'],mutation)

    def test_duplicate_forecast_wrong_group_missing_proper_incomplete(self):
        for change in ('duplicate','group','proper'):
            new,old=self.comparisons()
            if change=='duplicate':new[0]['predictions'][1]=copy.deepcopy(new[0]['predictions'][0])
            elif change=='group':new[0]['predictions'][0]['group']=-1
            else:del new[0]['predictions'][0]['crps']
            r=p.aggregate(self.packet,self.raw,self.pin,new,old,self.bindings,processing_begin=time.monotonic());self.assertEqual(r['status'],'incomplete');self.assertFalse(r['pass_all'])


class NumericTests(unittest.TestCase):
    def test_numeric_bits_optimizer_dtype(self):
        a=np.asarray([1.,np.nextafter(1.,2.),-0.],dtype='<f8');step=np.asarray(300.,dtype='<f4');obj=checked(ns.encode(dict(a=a,step=step)))
        self.assertEqual(a.tobytes(),obj['a'].tobytes());self.assertEqual(step.tobytes(),obj['step'].tobytes())

    def test_duplicates_nonfinite_object_caps_hash(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}'):
            with self.assertRaises(ValueError):checked(raw)
        with self.assertRaises(ValueError):ns.encode(np.asarray([object()],dtype=object))
        with self.assertRaises(ValueError):ns.encode(np.zeros(100001,dtype='<f8'))
        with self.assertRaises(ValueError):ns.decode(b'{}','0'*64)
        with self.assertRaises(ValueError):checked(b' '*(ns.CAP+1))


if __name__=='__main__':unittest.main()
