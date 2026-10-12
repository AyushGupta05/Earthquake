"""Invented-only NEW115 tests; no actual IDs, waveforms, provenance or custody."""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

import adapter115 as adapter
import activity115
import native_core as producer
import old_activity
from native_decode_contract import ObservedDecodeFailure

START = 1704067200000000000


def record(channel, index, values):
    raw = bytearray(256)
    raw[:20] = b'000001D ABC    ' + channel.encode() + b'NZ'
    struct.pack_into('>HHBBBBHHhhBBBBiHH', raw, 20, 2024, 1, 0, 0, index * 4,
                     0, 0, len(values), 8, 1, 0, 0, 0, 1, 0, 56, 48)
    struct.pack_into('>HHBBBB', raw, 48, 1000, 0, 3, 1, 8, 0)
    struct.pack_into('>' + 'i' * len(values), raw, 56, *values)
    return bytes(raw)


def decode(raw, descriptor):
    start, rate, _ = producer.header_grid(descriptor)
    values = list(struct.unpack_from('>'+'i'*descriptor['npts'], raw, descriptor['data_offset']))
    return {'start_ns':start, 'rate':float(rate), 'dtype':'i4', 'values':values}


def old_fixture():
    results=[]
    for slot in range(65):
        train=slot<41
        ratios=([20,0]+[20]*18) if slot<4 else [20]*20
        cells=[]
        for h in (1,3,5):
            if not train:
                cells.append(old_activity._unknown(h,'DEFERRED_DEV'));continue
            values=ratios[:h*4]
            states,ages,transitions,episodes=old_activity._sequence(values)
            cells.append(dict(seconds=h,status='available',ratios=values,states=states,run_ages=ages,
                              transitions=transitions,episodes=episodes,noise_power=[1.,1.,1.],noise_floor=[True]*3))
        results.append(dict(schema='activity-event-v1',slot=slot,partition='TRAIN' if train else 'DEV',
                            family='ENZ',mw=6. if slot<20 else 4.,group='g'+str(slot),
                            external_support_asserted=[True]*3,external_group_eligible_asserted=True,
                            all_horizon_eligible=train,horizons=cells))
    external={'grouping_frozen':True,'prior_support_floor_pass':True}
    return dict(schema='earthquake-activity-native-adapter-v1',results=results,
                summary=old_activity.summarize(results,external),decoded_train_records=0,adapter_denials=[],
                claims={k:False for k in adapter.CLAIMS})


def fixture():
    body=b''.join(record('HH'+s,i,[0]*24+[20]*8 if i==0 else [20,20,0,0]*8) for s in 'ENZ' for i in (0,1))
    rows=[dict(ordinal=i,global_ordinal=65+i,partition='TRAIN',batch=i//4,queryable=True,network='NZ',station='ABC',
               location='',prefix='HH',t0_ns=START+3*10**9,pick_ns=START+3*10**9,family='ENZ',
               nominal_rates={'HH'+s:[8,1] for s in 'ENZ'}) for i in range(50)]
    bodies={i:body for i in range(13)}
    batches=[dict(ordinal=i,rows=list(range(4*i,min(4*i+4,50))),requested_rows=list(range(4*i,min(4*i+4,50))),
                  transport='http200',body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest()) for i in range(13)]
    plan=dict(study=producer.STUDY,rows=rows,batches=batches)
    qualified=producer.qualify(plan,bodies,decode)
    old=old_fixture()
    metadata=[dict(slot=i,mw=old['results'][i]['mw'],group='g'+str(i),group_eligible=True) for i in range(65)]
    metadata += [dict(slot=65+i,mw=5.7 if i<14 else 4.5,group='g'+str(65+i),group_eligible=True) for i in range(50)]
    return old,plan,qualified,bodies,metadata,{'grouping_frozen':True,'prior_support_floor_pass':True}


def pins(old,plan,q,meta):
    return {name+'_sha256':hashlib.sha256(producer.canonical(value)).hexdigest()
            for name,value in [('old_packet',old),('new_plan',plan),('new_qualified',q),('metadata115',meta)]}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.old,self.plan,self.q,self.bodies,self.meta,self.external=fixture()

    def run_adapter(self,decoder=decode,bindings=None):
        return adapter.run(self.old,self.plan,self.q,self.bodies,decoder,self.meta,self.external,
                           pins(self.old,self.plan,self.q,self.meta) if bindings is None else bindings)

    def test_namespace_denominator_original_unchanged_and_train_only(self):
        before=producer.canonical(self.old)
        out=self.run_adapter()
        self.assertEqual([r['slot'] for r in out['results']],list(range(115)))
        self.assertEqual(out['summary']['partition_counts'],dict(TRAIN=91,DEV=24))
        self.assertEqual(out['summary']['horizon_cells'],345)
        self.assertEqual(out['decoded_new_train_records'],300)
        self.assertEqual(out['observed_new_train_samples'],9600)
        self.assertEqual(producer.canonical(out['results'][:65]),producer.canonical(self.old['results']))
        self.assertEqual(producer.canonical(self.old),before)
        self.assertFalse(out['old_summary']['observational_variation_pass'])
        self.assertEqual(out['old_summary']['off_train_operational_groups'],4)
        self.assertTrue(out['summary']['combined_prospective_gate'])
        self.assertFalse(out['summary']['fit_authorized'])
        self.assertTrue(all(v is False for v in out['claims'].values()))
        self.assertEqual(out['support_panels']['new50']['horizon_cells'],150)

    def test_original_group_or_mw_or_eligibility_changes_abort_before_decode(self):
        for field,value in [('group','changed'),('mw',5.9),('group_eligible',False)]:
            altered=copy.deepcopy(self.meta);altered[0][field]=value
            with self.assertRaisesRegex(adapter.InvalidInput,'old_metadata_binding'):
                adapter.run(self.old,self.plan,self.q,self.bodies,lambda *_:self.fail('old mismatch decoded'),altered,
                            self.external,pins(self.old,self.plan,self.q,altered))

    def test_frozen_input_pin_tampering_before_decode(self):
        binding=pins(self.old,self.plan,self.q,self.meta)
        self.meta[-1]['mw']=2.0
        with self.assertRaisesRegex(adapter.InvalidInput,'input_pin'):
            self.run_adapter(lambda *_:self.fail('bad pin decode'),binding)

    def test_dev_scalar_values_denied(self):
        r=self.old['results'][41]
        r['horizons'][0]=copy.deepcopy(self.old['results'][0]['horizons'][0])
        with self.assertRaises(old_activity.InvalidInput):self.run_adapter(lambda *_:self.fail('DEV decoded'))

    def test_old_summary_tampering_and_claims_denied(self):
        self.old['summary']['events']=64
        with self.assertRaisesRegex(adapter.InvalidInput,'old_summary'):self.run_adapter()
        self.old=old_fixture();self.old['claims']['accuracy_improved']=True
        with self.assertRaisesRegex(adapter.InvalidInput,'old_claim'):self.run_adapter()

    def test_all_new_denied_preserves_old_negative_gate(self):
        for meta in self.meta[65:]:meta['group_eligible']=False
        out=self.run_adapter(lambda *_:self.fail('ineligible decoded'))
        self.assertEqual(out['decoded_new_train_records'],0)
        self.assertFalse(out['summary']['combined_prospective_gate'])
        self.assertEqual(out['summary']['off_train_operational_groups'],4)

    def test_no_target_nullable_clocks_preserve50_and345(self):
        for row in self.plan['rows']:
            row.update(queryable=False,network=None,station=None,location=None,prefix=None,pick_ns=None,family=None,nominal_rates={})
        self.plan['rows'][0]['t0_ns']=None
        for b in self.plan['batches']:b.update(requested_rows=[],transport='no_selection',body_bytes=0,body_sha256=None)
        self.bodies={i:None for i in range(13)}
        self.q=producer.qualify(self.plan,self.bodies,lambda *_:self.fail('no-target qualifier decode'))
        out=self.run_adapter(lambda *_:self.fail('no-target adapter decode'))
        self.assertEqual(len(out['results']),115);self.assertEqual(len(out['new_adapter_denials']),50)
        self.assertEqual(out['results'][65]['horizons'][0]['status'],'UNSUPPORTED')
        self.assertIsNone(self.plan['rows'][0]['t0_ns'])

    def test_unknown_family_and_long_native_station_no_fallback(self):
        self.plan['rows'][0].update(family=None,nominal_rates={})
        self.plan['rows'][1]['station']='ABCDEFGH'
        self.q=producer.qualify(self.plan,self.bodies,decode)
        visited=[];original=adapter.reconstruct
        def traced(plan,row,*args):visited.append(row['ordinal']);return original(plan,row,*args)
        with patch.object(adapter,'reconstruct',traced):out=self.run_adapter()
        self.assertNotIn(0,visited);self.assertNotIn(1,visited)
        self.assertEqual(out['results'][66]['horizons'][0]['status'],'UNSUPPORTED')
        self.assertEqual(self.plan['rows'][1]['station'],'ABCDEFGH')

    def test_pre_t0_and_late_base_picks_not_repaired(self):
        self.plan['rows'][0]['pick_ns']-=1
        self.plan['rows'][1]['pick_ns']+=750_000_001
        self.q=producer.qualify(self.plan,self.bodies,decode)
        out=self.run_adapter()
        self.assertEqual(out['results'][65]['horizons'][0]['status'],'UNSUPPORTED')
        self.assertEqual(out['results'][66]['horizons'][0]['status'],'LATE_BASE')
        self.assertEqual(out['decoded_new_train_records'],48*6)

    def test_body_raw_native_view_and_crop_hash_veto(self):
        edits=[lambda q:q['records'][0].update(raw_sha256='0'*64),lambda q:q['records'][0].update(samples_sha256='0'*64),
               lambda q:q['rows'][0]['cells'][0]['components'][0].update(view_sha256='0'*64),
               lambda q:q['rows'][0]['cells'][0]['components'][0]['pieces'][0].update(hi=31)]
        original=copy.deepcopy(self.q)
        for edit in edits:
            self.q=copy.deepcopy(original);edit(self.q)
            with self.assertRaises(adapter.InvalidInput):self.run_adapter()
        self.q=original;self.bodies[0]=self.bodies[0][:-1]+b'x'
        with self.assertRaises(ValueError):self.run_adapter(lambda *_:self.fail('body pin decode'))

    def test_wrong_grid_or_dtype_and_native_sample_mutation(self):
        for field,value in [('start_ns',START+1),('dtype','f4')]:
            def bad(raw,d):result=decode(raw,d);result[field]=value;return result
            with self.assertRaises(adapter.InvalidInput):self.run_adapter(bad)
        def bad(raw,d):result=decode(raw,d);result['values'][0]+=1;return result
        with self.assertRaisesRegex(adapter.InvalidInput,'sample_hash'):self.run_adapter(bad)

    def test_observed_overdelivery_charged_before_grid_mismatch(self):
        class Large:
            def __len__(self):return 8_000_001
        def bad(raw,d):return {'values':Large(),'start_ns':0,'rate':0.,'dtype':'wrong'}
        with self.assertRaisesRegex(adapter.InvalidInput,'sample_cap'):self.run_adapter(bad)

    def test_structured_failures_counted_before_discard_and_invalid_fail_count(self):
        def excess(*_):raise ObservedDecodeFailure(8_000_001)
        with self.assertRaisesRegex(adapter.InvalidInput,'sample_cap'):self.run_adapter(excess)
        def within(*_):raise ObservedDecodeFailure(31)
        with self.assertRaisesRegex(adapter.InvalidInput,'decode_failure'):self.run_adapter(within)
        class Bad(ValueError):observed_samples=True
        def invalid(*_):raise Bad()
        with self.assertRaisesRegex(adapter.InvalidInput,'observed_accounting_invalid'):self.run_adapter(invalid)

    def test_total_observed_cap_and_exact8million_limit(self):
        budget={'observed_samples':0}
        self.assertEqual(adapter.charge(8_000_000,0,budget),8_000_000)
        with self.assertRaisesRegex(adapter.InvalidInput,'sample_cap'):adapter.charge(1,8_000_000,budget)
        with patch.object(adapter,'MAX_OBSERVED_TOTAL',100):
            with self.assertRaisesRegex(adapter.InvalidInput,'sample_cap'):self.run_adapter()

    def test_metadata_exact_types_no_extra_old65_padding_or_new_dev(self):
        for field,value in [('slot',False),('mw',True),('group_eligible',1)]:
            meta=copy.deepcopy(self.meta);meta[65][field]=value
            with self.assertRaisesRegex(adapter.InvalidInput,'metadata'):
                adapter.run(self.old,self.plan,self.q,self.bodies,decode,meta,self.external,pins(self.old,self.plan,self.q,meta))
        self.plan['rows'][0]['partition']='DEV'
        with self.assertRaises(ValueError):self.run_adapter(lambda *_:self.fail('new DEV decode'))

    def test_incomplete_and_bad_aggregate_and_duplicate_records(self):
        self.q['disposition']='incomplete'
        with self.assertRaisesRegex(adapter.InvalidInput,'qualified_identity'):self.run_adapter()
        self.q['disposition']='complete';self.q['aggregate']['rows']=49
        with self.assertRaisesRegex(adapter.InvalidInput,'aggregate'):self.run_adapter()
        self.q=producer.qualify(self.plan,self.bodies,decode);self.q['records'].append(copy.deepcopy(self.q['records'][0]))
        with self.assertRaisesRegex(adapter.InvalidInput,'duplicate_record'):self.run_adapter()

    def test_deadline_and_output_caps_no_successful_partial(self):
        with patch.object(adapter.time,'monotonic',side_effect=[0,301]):
            with self.assertRaisesRegex(adapter.InvalidInput,'wall_timeout'):self.run_adapter()
        with patch.object(adapter,'MAX_PRIVATE',1):
            with self.assertRaises(adapter.InvalidInput):self.run_adapter()
        with patch.object(adapter,'MAX_PUBLIC',1):
            with self.assertRaisesRegex(adapter.InvalidInput,'public_cap'):self.run_adapter()

    def test_event_native_arrays_released_before_next(self):
        state={};original=adapter.reconstruct
        def traced(*args):
            if 'last' in state:self.assertEqual(sys.getrefcount(state['last']),2)
            components,count=original(*args);state['last']=components;return components,count
        with patch.object(adapter,'reconstruct',traced):self.run_adapter()

    def test_threshold_noise_censor_prefix_and_native_gap_rules_unchanged(self):
        self.assertEqual(activity115._sequence([9.,10.,0.,10.])[0],[0,1,0,1])
        self.assertTrue(activity115._sequence([10.,0.,10.])[-1][-1]['right_censored'])
        self.assertEqual(activity115._noise([[ (Fraction(START),Fraction(125_000_000),Fraction(START+3*10**9),[0]*24) ]]*3,START+3*10**9)[1],[1.,1.,1.])
        with self.assertRaises(activity115.InvalidInput):list(activity115._window_values([(Fraction(0),Fraction(1),Fraction(1),[0]),(Fraction(2),Fraction(1),Fraction(3),[0])],0,3))
        out=self.run_adapter();first=out['results'][65]['horizons']
        self.assertEqual(first[2]['ratios'][:4],first[0]['ratios']);self.assertEqual(first[2]['ratios'][:12],first[1]['ratios'])

    def test_exact_activity_profile_and_native_import_only_parity(self):
        root=Path(__file__).parent
        proof=json.loads((root/'REUSE_PROOF.json').read_text())
        source=(root/'old_activity.py').read_text()
        for a,b in proof['activity115_exact_replacements'].items():source=source.replace(a,b)
        self.assertEqual(source,(root/'activity115.py').read_text())
        core=(root/'native_core.py').read_text().replace('import native_scanner as scanner','import scanner').replace('from native_decode_contract import ObservedDecodeFailure','from decode_contract import ObservedDecodeFailure')
        self.assertEqual(hashlib.sha256(core.encode()).hexdigest(),proof['copied_sources']['work/geonet_train50_prefix_qualifier_v1/producer.py']['sha256'])
        for filename,origin in [('native_scanner.py','scanner.py'),('native_decode_contract.py','decode_contract.py')]:
            self.assertEqual(hashlib.sha256((root/filename).read_bytes()).hexdigest(),proof['copied_sources']['work/geonet_train50_prefix_qualifier_v1/'+origin]['sha256'])

    def test_new_same_operational_group_cannot_inflate_old_four_off_groups(self):
        for meta in self.meta[65:]:meta['group']='g0'
        out=self.run_adapter()
        self.assertEqual(out['summary']['off_train_operational_groups'],4)
        self.assertFalse(out['summary']['combined_prospective_gate'])

    def test_b100_exact_period_outside_activity_bound_never_decoded(self):
        rate=Fraction.from_float(struct.unpack('>f',struct.pack('>f',40.1))[0])
        period=Fraction(10**9)/rate
        body=bytearray()
        for suffix in 'ENZ':
            for ordinal in range(11):
                micros=round(ordinal*32*period/1000)
                raw=bytearray(256);raw[:20]=b'000001D ABC    HH'+suffix.encode()+b'NZ'
                second,remainder=divmod(micros,10**6);fraction,correction=divmod(remainder,100)
                struct.pack_into('>HHBBBBHHhhBBBBiHH',raw,20,2024,1,0,0,second,0,fraction,32,8,1,0,0,0,3,0,84,48)
                struct.pack_into('>HHBBBB',raw,48,1000,56,3,1,8,0)
                struct.pack_into('>HHfBBBB',raw,56,100,68,float(rate),0,0,0,0)
                struct.pack_into('>HHBbBB',raw,68,1001,0,90,correction,0,0)
                struct.pack_into('>'+'i'*32,raw,84,*([0]*32));body.extend(raw)
        body=bytes(body);self.bodies={i:body for i in range(13)}
        for batch in self.plan['batches']:batch.update(body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest())
        for row in self.plan['rows']:row['nominal_rates']={code:[rate.numerator,rate.denominator] for code in row['nominal_rates']}
        self.q=producer.qualify(self.plan,self.bodies,decode)
        self.assertEqual(self.q['rows'][0]['cells'][2]['joint']['status'],'complete')
        out=self.run_adapter(lambda *_:self.fail('unsupported period decoded'))
        self.assertEqual(out['decoded_new_train_records'],0)
        self.assertEqual(len(out['new_adapter_denials']),50)
        self.assertEqual(out['new_adapter_denials'][0]['reason'],'activity_period_bound')

    def test_unearned_external_support_keeps_false_claim(self):
        self.external['prior_support_floor_pass']=False
        out=self.run_adapter();self.assertTrue(out['summary']['observational_variation_pass'])
        self.assertFalse(out['summary']['combined_prospective_gate']);self.assertFalse(out['claims']['fit_authorized'])


if __name__=='__main__':unittest.main()
