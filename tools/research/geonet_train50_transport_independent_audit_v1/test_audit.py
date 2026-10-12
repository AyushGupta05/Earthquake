"""Invented byte/receipt contracts, no new producer imports or actual data."""
import copy
import hashlib
import json
import unittest
import engine
import get_audit
import post_audit
import plans
from invented import Bundle,plan,raw,pin
from strict_inputs import Invalid,decode


class AuditTests(unittest.TestCase):
    def test_both_complete_and_callback_one_read_each(self):
        for profile,count in [('GET',50),('POST',13)]:
            b=Bundle(profile);r=b.audit();self.assertTrue(r['valid'],r);self.assertTrue(r['whole_complete']);self.assertEqual(r['qualified_requests'],count);self.assertEqual(len(b.calls),len(set(b.calls)))
            self.assertEqual(set(b.calls),set(b.members))
            if profile=='GET':self.assertEqual(len(r['transport']['rows']),50)
            else:self.assertIsNone(r['transport'])
    def test_GET_null_target_empty_request_and_nonfabricated_attempt(self):
        b=Bundle('GET',[0,2,49]);r=b.audit();self.assertTrue(r['whole_complete'],r);self.assertEqual(r['qualified_requests'],47)
        for i in (0,2,49):self.assertEqual(b.members[f'{i:03d}.request.private'],b'');self.assertNotIn(f'{i:03d}.body.private',b.members);self.assertEqual(r['transport']['rows'][i]['classification'],'no_target')
        self.assertEqual(r['aggregate']['accounting_complete_selections'],50);self.assertEqual(r['aggregate']['no_target_rows'],3)
    def test_POST_empty_blocks_missing_request_and_index_gaps(self):
        b=Bundle('POST',list(range(4))+list(range(20,24))+[48,49]);r=b.audit();self.assertTrue(r['whole_complete'],r);self.assertEqual(r['qualified_requests'],10)
        for i in (0,5,12):self.assertNotIn(f'{i:03d}.request.private',b.members);self.assertNotIn(f'{i:03d}.body.private',b.members)
        self.assertEqual(r['aggregate']['accounting_complete_batches'],10);self.assertEqual(r['aggregate']['no_selection_batches'],3)
    def test_all_no_targets_whole_complete_zero_candidates(self):
        for profile in ('GET','POST'):
            b=Bundle(profile,range(50));r=b.audit();self.assertTrue(r['whole_complete'],r);self.assertEqual(r['qualified_requests'],0)
            self.assertTrue(all(x['status'] in ('no_target','no_selection') for x in b.finalrows))
    def test_POST_hash_order_original_indices_not_sorted(self):
        b=Bundle('POST');self.assertGreater(b.plan['rows'][0]['original_event_index'],b.plan['rows'][1]['original_event_index']);self.assertTrue(b.audit()['valid'])
    def test_unknown_metadata_does_not_suppress_POST(self):
        b=Bundle('POST');self.assertEqual(b.plan['rows'][0]['metadata_status'],'unknown');self.assertIn(0,b.plan['batches'][0]['requested_row_indices']);self.assertTrue(b.audit()['whole_complete'])
    def test_partial_halts_retains_nontargets_qualifies_zero(self):
        for profile in ('GET','POST'):
            missing=[8,9,10,11];b=Bundle(profile,missing,incomplete_at=0);r=b.audit();self.assertTrue(r['valid'],r);self.assertFalse(r['whole_complete']);self.assertEqual(r['qualified_requests'],0);self.assertIsNone(r['transport'])
    def test_empty_framedHTTP200_and_errors_complete_not_candidates(self):
        for profile in ('GET','POST'):
            b=Bundle(profile);b.response(0,200,b'',framing='fixed');b.response(1,404,b'error',framing='eof');r=b.audit();self.assertTrue(r['whole_complete'],r);self.assertEqual(r['qualified_requests'],b.meta['count']-2)
    def test_HTTP204_representationCL_zeroentity(self):
        for profile in ('GET','POST'):
            b=Bundle(profile);b.response(0,204,b'',framing='no_body');r=b.audit();self.assertTrue(r['whole_complete'],r)
    def test_chunk_syntax_associated_with_body_lengths(self):
        for profile in ('GET','POST'):
            b=Bundle(profile);b.response(0,200,b'abcde','chunked',b'2\r\n\r\n3\r\n\r\n0\r\nX:ok\r\n\r\n');self.assertTrue(b.audit()['whole_complete'])
    def test_chunk_malformed_partial_and_excess_rejected(self):
        for syntax in (b'5\r\n\r\n0\n\n',b'6\r\n\r\n0\r\n\r\n',b'5\r\n\r\n0\r\n\r\nx',b'5\r\n\r\n0\r\n folded\r\n\r\n'):
            b=Bundle('GET');b.response(0,200,b'abcde','chunked',syntax);self.assertFalse(b.audit()['valid'])
    def test_duplicate_headers_ambiguousCL_TE_rejected(self):
        for pairs in ([['Content-Length','5'],['Content-Length','5']],[['Content-Length','5'],['Transfer-Encoding','chunked']],[['Content-Length',' 5']],[['Transfer-Encoding','gzip, chunked']]):
            b=Bundle('POST');h=json.loads(b.members['000.headers.private.json']);h['fields']=pairs;hb=raw(h);b.members['000.headers.private.json']=hb;b.finalrows[0]['headers']=pin('000.headers.private.json',hb);b.refresh();self.assertFalse(b.audit()['valid'])
    def test_header_parser_constant_changed_rejected(self):
        b=Bundle('GET');h=json.loads(b.members['000.headers.private.json']);h['parser_limits']['header_count']=101;hb=raw(h);b.members['000.headers.private.json']=hb;b.finalrows[0]['headers']=pin('000.headers.private.json',hb);b.refresh();self.assertFalse(b.audit()['valid'])
    def test_body_mutation_or_swapped_body_detected_after_metadata(self):
        for profile in ('GET','POST'):
            b=Bundle(profile);b.members['000.body.private']=b'wrong';self.assertFalse(b.audit()['valid'])
            b=Bundle(profile);b.members['000.body.private']=b.members['001.body.private'];self.assertFalse(b.audit()['valid'])
    def test_missing_extra_members_and_old17_namespace_rejected(self):
        for change in (lambda b:b.members.pop('000.request.private'),lambda b:b.members.update({'999.body.private':b'x'}),lambda b:b.members.update({'016.batch.private.json':b'{}'})):
            b=Bundle('POST');change(b);b.repin_manifest();self.assertFalse(b.audit()['valid'])
    def test_empty_POST_request_fabrication_rejected(self):
        b=Bundle('POST',range(4));b.members['000.request.private']=b'';b.repin_manifest();self.assertFalse(b.audit()['valid'])
    def test_GET_missing_nulltarget_request_rejected(self):
        b=Bundle('GET',[0]);b.members.pop('000.request.private');b.repin_manifest();self.assertFalse(b.audit()['valid'])
    def test_journal_controller_disagreement_rejected(self):
        b=Bundle('GET');r=json.loads(b.members['000.selection.private.json']);r['HTTP200_candidate']=False;b.members['000.selection.private.json']=raw(r);b.repin_manifest();self.assertFalse(b.audit()['valid'])
    def test_provisional_saved_aggregate_cannot_promote(self):
        b=Bundle('POST');a=json.loads(b.members['public_aggregate.json']);a['whole_complete']=True;a['qualified_batches']=13;b.members['public_aggregate.json']=raw(a);b.repin_manifest();self.assertFalse(b.audit()['valid'])
    def test_stop_clock_spacing_overlap_false_flags_rejected(self):
        for field,value in [('worker_group_stop_confirmed',False),('worker_exit_confirmed',False),('connected_at',112.),('headers_at',125.),('first_body_at',125.),('end',125.)]:
            b=Bundle('GET');b.finalrows[0][field]=value;b.refresh();self.assertFalse(b.audit()['valid'])
        b=Bundle('POST');b.finalrows[1]['start']=101.2;b.refresh();self.assertFalse(b.audit()['valid'])
    def test_bool_alias_on_group_index_aggregate_rejected(self):
        for field in ('request_index','worker_group','observed_bytes'):
            b=Bundle('GET');b.finalrows[0][field]=True;b.refresh();self.assertFalse(b.audit()['valid'])
    def test_registration_skip_queryable_slot_rejected_no_read(self):
        for profile in ('GET','POST'):
            b=Bundle(profile);s=json.loads(b.summary);key=b.key;s['registered_attempts'][0][key]=1;self._summary(b,s);r=b.audit();self.assertFalse(r['valid']);self.assertEqual(b.calls,[])
    def test_duplicate_groups_rejected(self):
        b=Bundle('POST');b.finalrows[1]['worker_group']=b.finalrows[0]['worker_group'];b.refresh();self.assertFalse(b.audit()['valid'])
    def test_limits_or_fixture_changed_rejected_before_body(self):
        for key,value in [('fixture',True),('limits',dict(plans.GET_LIMITS,request_s=21.))]:
            b=Bundle('GET');c=json.loads(b.members['controller_summary.private.json']);c[key]=value;b.members['controller_summary.private.json']=raw(c);b.repin_manifest();r=b.audit();self.assertFalse(r['valid']);self.assertFalse(any(n.endswith('.body.private') for n in b.calls))
    def test_GET_whole_boundary_strict_POST_inclusive(self):
        for profile,valid in [('GET',False),('POST',True)]:
            b=Bundle(profile);s=json.loads(b.summary);s['elapsed_s']=b.meta['limits']['whole_s'];s['returned_at']=100.+s['elapsed_s'];self._summary(b,s);self.assertEqual(b.audit()['valid'],valid)
    def test_sparse_accounting_no_reader_nullbytes_uppercharge(self):
        for profile in ('GET','POST'):
            b=Bundle(profile,[0]);s=json.loads(b.summary);a=s['public_aggregate'];a.update(accounting_known=False,whole_complete=False,retained_response_bytes=None,overflow_probe_bytes=None,consumption_upper=len(s['registered_attempts'])*(b.meta['limits']['body_bytes']+1))
            if profile=='GET':a.update(no_target_rows=None,unattempted_selections=50-a['attempted_selections'],accounting_complete_selections=0,HTTP200_candidate_documents=0,qualified_documents=0)
            else:a.update(accounting_complete_batches=0,HTTP200_candidate_batches=0,qualified_batches=0)
            s.update(complete=False,reason='deadline',manifest_sha256=None,receipt_sha256=None);self._summary(b,s);b.manifest=None;r=b.audit();self.assertFalse(r['valid']);self.assertTrue(r['registered_setup_accounting_verified']);self.assertEqual(b.calls,[]);self.assertEqual(r['qualified_requests'],0)
    def test_overflow_probe_wrong_position_rejected(self):
        b=Bundle('POST',incomplete_at=0);b.finalrows[0].update(outcome='overflow',overflow_probe_bytes=1,consumed_upper=6);b.refresh();self.assertFalse(b.audit()['valid'])
    def test_unknown_consumption_requires_full_conservative_charge(self):
        b=Bundle('GET',incomplete_at=0);b.finalrows[0].update(consumption_exact=False,consumed_upper=5);b.refresh();self.assertFalse(b.audit()['valid'])
        b.finalrows[0]['consumed_upper']=4194305;b.refresh();self.assertTrue(b.audit()['valid'])
    def test_pub_no_transport_private_pins_or_rows(self):
        r=Bundle('GET').audit();p=engine.public_summary(r);self.assertFalse(any(k in p for k in ('transport','aggregate','rows','body_sha256','plan_sha256','worker_group','begin')))
    def test_malformed_summary_pin_no_member_reads(self):
        b=Bundle('POST');b.summarypin['sha256']='0'*64;self.assertFalse(b.audit()['valid']);self.assertEqual(b.calls,[])
    def test_response_headers_required_even_empty(self):
        b=Bundle('GET');b.response(0,200,b'');b.finalrows[0]['headers']=None;b.members.pop('000.headers.private.json');b.refresh();self.assertFalse(b.audit()['valid'])
    def test_plan_old_identity_TEST_wrongglobal_and_duplicates_no_read(self):
        for change in (lambda p:p.update(study_id='geonet-original-TRAINDEV65-prefix3-native-POST-v2'),lambda p:p['rows'][0].update(partition='DEV'),lambda p:p['rows'][0].update(global_ordinal=0),lambda p:p['rows'][1].update(event_id=p['rows'][0]['event_id'])):
            b=Bundle('POST');change(b.plan);b.planbytes=raw(b.plan);self.assertFalse(b.audit()['valid']);self.assertEqual(b.calls,[])
    def test_canonical_time_blankloc_and_format(self):
        p=plan('POST');entity=p['batches'][0]['request_body'];self.assertTrue(entity.startswith('format=miniseed\n'));self.assertIn('\nNZ ',entity)
        self.assertIn(' -- HH? 2000-01-01T00:00:',entity);self.assertIn('.123456789Z',entity)
        b=Bundle('POST');b.plan['batches'][0]['request_body']=entity.replace('miniseed','mseed');b.planbytes=raw(b.plan);self.assertFalse(b.audit()['valid']);self.assertEqual(b.calls,[])
    def test_POST_requested_subset_no_dedup_or_mutated_null_clock(self):
        b=Bundle('POST',[0]);b.plan['batches'][0]['requested_row_indices']=[1,2];b.planbytes=raw(b.plan);self.assertFalse(b.audit()['valid'])
        b=Bundle('POST',[0]);b.plan['rows'][0]['station']='FAKE';b.planbytes=raw(b.plan);self.assertFalse(b.audit()['valid'])
    def test_GET_canonical_URL_level_and_namespace_no_READ(self):
        b=Bundle('GET');b.plan['selections'][0]['request_url']=b.plan['selections'][0]['request_url'].replace('level=channel','level=response');b.planbytes=raw(b.plan);self.assertFalse(b.audit()['valid']);self.assertEqual(b.calls,[])
    def test_duplicate_nonfinite_deepJSON_and_hostile_byte_types(self):
        for value in (b'{"protocol":1,"protocol":2}',b'{"a":NaN}',b'['*40+b'0'+b']'*40,bytearray(b'{}')):
            with self.assertRaises(Invalid):decode(value,131072,'invented')
    def test_callback_missing_oversize_and_foreign_return_types(self):
        b=Bundle('GET')
        for callback in (lambda n,c:bytearray(b.members[n]),lambda n,c:b'X'*(c+1),lambda n,c:(_ for _ in ()).throw(FileNotFoundError('invented'))):
            r=get_audit.audit(b.planbytes,b.manifest,callback,execution_summary_bytes=b.summary,execution_summary_pin=b.summarypin);self.assertFalse(r['valid'])
    def test_header_and_chunk_combined_byte_cap(self):
        b=Bundle('POST');b.response(0,200,b'abcde','chunked',b'5\r\n\r\n0\r\n\r\n');h=json.loads(b.members['000.headers.private.json']);h['fields'].append(['X','a'*70000]);hb=raw(h);b.members['000.headers.private.json']=hb;b.finalrows[0]['headers']=pin('000.headers.private.json',hb);syntax=b'5;'+b'a'*65000+b'\r\n\r\n0\r\n\r\n';b.members['000.framing.private']=syntax;b.finalrows[0]['framing_evidence']=pin('000.framing.private',syntax);b.refresh();self.assertFalse(b.audit()['valid'])
    def test_annotations_not_receipt_family_decisions(self):
        b=Bundle('POST');c=json.loads(b.members['controller_summary.private.json']);c['row_annotations']['nominal_ENZ_rows']+=1;b.members['controller_summary.private.json']=raw(c);b.repin_manifest();self.assertFalse(b.audit()['valid'])
    def test_complete_GET_private_projection_order_and_error_hashes(self):
        b=Bundle('GET',[2]);b.response(1,404,b'error','eof');r=b.audit();self.assertTrue(r['whole_complete'])
        t=r['transport'];self.assertEqual([x['row_index'] for x in t['rows']],list(range(50)))
        self.assertEqual(t['rows'][1]['classification'],'nonpositive');self.assertEqual(t['rows'][1]['body_sha256'],hashlib.sha256(b'error').hexdigest())
        self.assertEqual(t['rows'][2]['body_bytes'],None);self.assertEqual(t['rows'][2]['http_status'],None)
    def test_omitted_phases_on_failure_allowed_not_complete(self):
        b=Bundle('POST',incomplete_at=0);r=b.finalrows[0];r.update(connected_at=None,headers_at=None,first_body_at=None)
        b.refresh();result=b.audit();self.assertTrue(result['valid'],result);self.assertFalse(result['whole_complete'])
    def test_pre_response_failure_has_no_fabricated_response_metadata(self):
        for profile in ('GET','POST'):
            for field,value in ((None,None),('http_status',200),('framing','fixed'),('declared',0)):
                b=Bundle(profile,incomplete_at=0);r=b.finalrows[0]
                r.update(headers=None,http_status=None,framing='unknown',declared=None,body=None,observed_bytes=0,consumed_upper=0,connected_at=None,headers_at=None,first_body_at=None,outcome='connection_deadline')
                b.members.pop('000.headers.private.json');b.members.pop('000.body.private')
                if field is not None:r[field]=value
                b.refresh();result=b.audit()
                if field is None:self.assertTrue(result['valid'],result);self.assertFalse(result['whole_complete']);self.assertEqual(result['qualified_requests'],0)
                else:self.assertFalse(result['valid'],(profile,field,result));self.assertIn('pre_response_metadata',result['issues'])
    def test_empty_POST_late_headers_before_request_end_still_incomplete(self):
        b=Bundle('POST',incomplete_at=0);b.response(0,200,b'');r=b.finalrows[0];r.update(outcome='framed_complete',headers_at=162.,end=163.,HTTP200_candidate=False)
        b.refresh();result=b.audit();self.assertTrue(result['valid'],result);self.assertFalse(result['whole_complete'])
    def test_cross_profile_manifest_never_read(self):
        g=Bundle('GET');p=Bundle('POST');r=post_audit.audit(p.planbytes,g.manifest,p.read,execution_summary_bytes=p.summary,execution_summary_pin=p.summarypin)
        self.assertFalse(r['valid']);self.assertEqual(p.calls,[])
    def test_valid_capped_overflow_is_retained_incomplete(self):
        b=Bundle('GET',incomplete_at=0);body=b'Z'*4194304;b.response(0,200,body);r=b.finalrows[0]
        r.update(outcome='overflow',overflow_probe_bytes=1,consumed_upper=4194305,HTTP200_candidate=False)
        b.refresh();result=b.audit();self.assertTrue(result['valid'],result);self.assertEqual(result['qualified_requests'],0)
    def test_return_elapsed_nonfinite_or_nonexact_rejected(self):
        b=Bundle('POST');s=json.loads(b.summary);s['elapsed_s']+=.25;self._summary(b,s);self.assertFalse(b.audit()['valid'])
    def test_strict_bool_pin_and_duplicate_manifest_rejected(self):
        b=Bundle('GET');man=json.loads(b.manifest);man['members'][0]['bytes']=False;b.manifest=raw(man);summ=json.loads(b.summary);summ['manifest_sha256']=hashlib.sha256(b.manifest).hexdigest();self._summary(b,summ);self.assertFalse(b.audit()['valid'])
        b=Bundle('POST');man=json.loads(b.manifest);man['members'].append(man['members'][0]);b.manifest=raw(man);summ=json.loads(b.summary);summ['manifest_sha256']=hashlib.sha256(b.manifest).hexdigest();self._summary(b,summ);self.assertFalse(b.audit()['valid'])
    def test_rootproposal_and_prereq_tamper_no_callback(self):
        for key,val in [('proposal_sha256','0'*64),('prerequisites',{})]:
            b=Bundle('GET');b.plan[key]=val;b.planbytes=raw(b.plan);self.assertFalse(b.audit()['valid']);self.assertEqual(b.calls,[])
    def test_integer_UTC_negative_ns_exact(self):
        self.assertEqual(plans.utc_ns(-1),'1969-12-31T23:59:59.999999999Z')
        with self.assertRaises(Invalid):plans.utc_ns(True)
    def _summary(self,b,s):
        b.summary=raw(s);b.summarypin={'bytes':len(b.summary),'sha256':hashlib.sha256(b.summary).hexdigest()}


if __name__=='__main__':unittest.main()
