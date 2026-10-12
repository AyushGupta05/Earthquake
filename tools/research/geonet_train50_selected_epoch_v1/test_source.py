"""Invented fifty-slot/XML/framing/supervisor fixtures; no provider requests."""
from dataclasses import asdict
import copy
from fractions import Fraction
from decimal import Decimal,localcontext
import hashlib
import http.server
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
import collector as c
import qualifier as q

START=1704067200000000000


def plan(indices=()):
    rows=[]
    for i in range(50):
        target=dict(network='NZ',station='LONG1234',location='',prefix='HH',pick_ns=START+500000000,original_target_index=0) if i in indices else None
        rows.append(dict(row_index=i,global_index=65+i,event_id='invented%02d'%i,partition='TRAIN',t0_ns=START if target else None,selected_target=target,selection_reason=None if target else 'no_accepted_P'))
    p=dict(protocol=c.PROTOCOL,study_id='invented-get50',proposal_sha256=c.PROPOSAL_SHA,rows=rows,selections=[dict(selection_index=i,row_indices=[i],request_url=c.request_url(r),request_sha256=c.sha(c.entity(r))) for i,r in enumerate(rows)],prerequisites={k:'0'*64 for k in c.PREREQUISITES})
    return c.validate_plan(c.encode(p))


def xml(suffixes='EN12Z',rate='100',start='2000-01-01T00:00:00Z',station='LONG1234'):
    channels=''.join('<Channel code="HH%s" locationCode="" startDate="%s"><SampleRate>%s</SampleRate><Azimuth>0</Azimuth><Dip>0</Dip></Channel>'%(s,start,rate) for s in suffixes)
    return ('<FDSNStationXML xmlns="http://www.fdsn.org/xml/station/1" schemaVersion="1.2"><Network code="NZ" startDate="2000-01-01T00:00:00Z"><Station code="%s" startDate="2000-01-01T00:00:00Z">%s</Station></Network></FDSNStationXML>'%(station,channels)).encode()


def qualification(p,raw_by_index):
    projection=c.strict_json(p.source_bytes);docs=[];evidence=[]
    for i,row in enumerate(projection['rows']):
        raw=raw_by_index.get(i);target=row['selected_target']
        docs.append(raw)
        evidence.append(dict(row_index=i,classification='http200' if raw is not None else 'nonpositive' if target else 'no_target',http_status=200 if raw is not None else 204 if target else None,request_sha256=projection['selections'][i]['request_sha256'],body_bytes=len(raw) if raw is not None else 0 if target else None,body_sha256=c.sha(raw) if raw is not None else c.sha(b'') if target else None))
    transport=dict(protocol=c.PROTOCOL,plan_sha256=p.sha256,manifest_sha256='1'*64,receipt_sha256='2'*64,returned_sha256='3'*64,whole_complete=True,rows=evidence)
    return transport,docs


def limits(**updates):
    values=asdict(c.DEFAULT);values.update(connection_s=.8,first_body_s=1.,request_s=1.,processing_s=4.,whole_s=7.,term_s=.3,kill_s=.3,start_spacing_s=0.,body_bytes=65536,total_retained_bytes=50*65536,total_consumption_upper=50*65537);values.update(updates)
    return c.Limits(**values)


class PureTests(unittest.TestCase):
    def test_exact50_global_order_nullable_and_canonical_get(self):
        p=plan((2,));data=c.strict_json(p.source_bytes);self.assertEqual(len(data['rows']),50);self.assertEqual(data['rows'][-1]['global_index'],114)
        self.assertEqual(c.entity(data['rows'][0]),b'');query=parse_qs(urlsplit(data['selections'][2]['request_url']).query)
        self.assertEqual(query['station'],['LONG1234']);self.assertEqual(query['location'],['--']);self.assertEqual(query['channel'],['HH?']);self.assertEqual(query['starttime'],['2023-12-31T23:59:57.000000000Z']);self.assertEqual(query['endtime'],['2024-01-01T00:00:05.000000000Z']);self.assertEqual(query['level'],['channel'])

    def test_schema_bool_test_extra_wrong_url_and_order_rejected(self):
        base=c.strict_json(plan((0,)).source_bytes)
        for field,value in (('row_index',False),('global_index',66),('partition','DEV'),('partition','TEST'),('t0_ns',True)):
            p=copy.deepcopy(base);p['rows'][0][field]=value
            with self.assertRaises(ValueError):c.validate_plan(c.encode(p))
        for mutate in (lambda p:p['rows'].pop(),lambda p:p.update(extra=1),lambda p:p['selections'][0].update(request_url='https://evil.invalid/'),lambda p:p['rows'][0]['selected_target'].update(station='TOOLONG99'),lambda p:p['rows'][0]['selected_target'].update(original_target_index=8)):
            p=copy.deepcopy(base);mutate(p)
            with self.assertRaises(ValueError):c.validate_plan(c.encode(p))
        with self.assertRaises(ValueError):c.strict_json(b'{"x":1,"x":2}')

    def test_control_caps_profiles_and_member_names(self):
        self.assertEqual(c.checked_limits(asdict(c.DEFAULT),False).total_consumption_upper,209715250)
        with self.assertRaises(ValueError):c.checked_limits(asdict(limits()),False)
        with self.assertRaises(ValueError):c.checked_limits(dict(asdict(c.DEFAULT),total_consumption_upper=209715200),False)
        self.assertEqual(c.member_cap('049.body.private',c.DEFAULT),4194304)
        for name in ('050.body.private','../000.body.private','000.unknown'):
            with self.assertRaises(ValueError):c.member_cap(name,c.DEFAULT)

    def test_header_framing_errors_and_no_body(self):
        self.assertEqual(c.header_framing(204,[('Content-Length','99')]),('no_body',99))
        self.assertEqual(c.header_framing(200,[]),('eof',None))
        for status,fields in ((100,[]),(200,[('Content-Length',' 3')]),(200,[('Content-Length','3'),('Transfer-Encoding','chunked')]),(200,[('Transfer-Encoding','gzip, chunked')])):
            with self.assertRaises(ValueError):c.header_framing(status,fields)

    def test_exact_chunk_syntax_evidence_and_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            reader=c.ChunkReader(io.BufferedReader(io.BytesIO(b'3\r\nabc\r\n0\r\nX:y\r\n\r\n')),Path(folder)/'syntax',128)
            self.assertEqual(reader.read1(3),b'abc');self.assertEqual(reader.read1(3),b'');self.assertTrue(reader.complete);reader.close()
            self.assertEqual(Path(folder,'syntax').read_bytes(),b'3\r\n\r\n0\r\nX:y\r\n\r\n')
        for raw in (b'3\nabc',b'0\r\nX:y\n',b'2\r\na'):
            with tempfile.TemporaryDirectory() as folder:
                reader=c.ChunkReader(io.BufferedReader(io.BytesIO(raw)),Path(folder)/'syntax',128)
                try:
                    with self.assertRaises(ValueError):
                        while reader.read1(10):pass
                finally:reader.close()

    def test_metadata50_150_both_families_long_literal_scope(self):
        p=plan((2,));transport,docs=qualification(p,{2:xml()});result=q.qualify(p,transport,docs)
        self.assertEqual(len(result['private_rows']),50);self.assertEqual(sum(len(r['horizons']) for r in result['private_rows']),150)
        row=result['private_rows'][2];self.assertEqual(row['nominal_family'],'ENZ');self.assertEqual(row['nominal_rates'],{k:[100,1] for k in ('HHE','HHN','HHZ')})
        self.assertEqual(row['horizons'][0]['nominal_family_candidates'],{'ENZ':True,'12Z':True})
        self.assertEqual(result['public_counts']['unknown_documents'],49);self.assertTrue(all(v is False for v in result['public_counts']['claims'].values()))
        self.assertNotIn('LONG1234',c.encode(result['public_counts']).decode())

    def test_numbered_family_no_alias_and_missing_sample_rate(self):
        p=plan((0,))
        for body,expected in ((xml('12Z'),'12Z'),(xml('EN'),'unknown'),(xml('ENZ',rate='0'),'unknown')):
            t,d=qualification(p,{0:body});result=q.qualify(p,t,d)
            self.assertEqual(result['private_rows'][0]['nominal_family'] or 'unknown',expected)

    def test_boundary_overlap_dtd_malformed_namespace_unknown(self):
        p=plan((0,));bodies=[xml(start='2023-12-31T23:59:57Z'),xml('EENZ'),b'<!DOCTYPE x><x/>',b'notxml',xml().replace(b'station/1',b'station/3')]
        for raw in bodies:
            t,d=qualification(p,{0:raw});result=q.qualify(p,t,d)
            self.assertIsNone(result['private_rows'][0]['nominal_family'])
            self.assertEqual(len(result['private_rows']),50)

    def test_oversize_does_not_parse_or_erase_other_rows(self):
        p=plan((0,2));t,d=qualification(p,{0:b'x'*131073,2:xml()})
        original=q.core._document_row
        def guard(raw,slot):
            self.assertLessEqual(len(raw),131072);return original(raw,slot)
        with patch.object(q.core,'_document_row',side_effect=guard):result=q.qualify(p,t,d)
        self.assertEqual(result['private_rows'][0]['document']['reason'],'document_byte_cap');self.assertEqual(result['private_rows'][2]['nominal_family'],'ENZ')

    def test_complete_transport_and_exact_body_pin_before_parse(self):
        p=plan((0,));t,d=qualification(p,{0:xml()})
        for mutation in (lambda t:t.update(whole_complete=False),lambda t:t['rows'][0].update(body_sha256='0'*64),lambda t:t['rows'][0].update(request_sha256='0'*64),lambda t:t['rows'][0].update(classification='nonpositive')):
            bad=copy.deepcopy(t);mutation(bad)
            with patch.object(q.core,'_document_row',side_effect=AssertionError('parse')):
                with self.assertRaises(ValueError):q.qualify(p,bad,d)

    def test_xml_depth_node_caps_and_exact_ns_boundary(self):
        p=plan((0,))
        nested=xml().replace(b'</Station>',b'<X>'*40+b'</X>'*40+b'</Station>')
        crowded=xml().replace(b'</Station>',b'<X/>'*4097+b'</Station>')
        for raw in (nested,crowded):
            t,d=qualification(p,{0:raw});out=q.qualify(p,t,d)
            self.assertEqual(out['private_rows'][0]['document']['document_state'],'unknown')
        self.assertEqual(q.core.parse_ns('2024-01-01T00:00:00.000000001Z'),START+1)
        self.assertEqual(q.core.parse_ns('1969-12-31T23:59:59.999999999Z'),-1)

    def test_extreme_rate_exponents_unknown_without_integer_expansion(self):
        p=plan((0,2));original=q.Fraction
        def bounded(value):
            self.assertIsInstance(value,Decimal)
            sign,digits,exponent=value.as_tuple()
            self.assertLessEqual(max(len(digits)+max(exponent,0),1+max(-exponent,0)),1024)
            return original(value)
        for rate in ('1e1000000000','1e-1000000000','1e-1024','-0','+0'):
            t,d=qualification(p,{0:xml('ENZ',rate=rate),2:xml()})
            with patch.object(q,'Fraction',side_effect=bounded):out=q.qualify(p,t,d)
            self.assertIsNone(out['private_rows'][0]['nominal_family']);self.assertEqual(out['private_rows'][2]['nominal_family'],'ENZ');self.assertEqual(len(out['private_rows']),50)
            self.assertEqual(out['private_rows'][0]['document']['channels'][0]['epochs'][0]['sample_rate']['raw'],[rate])

    def test_trailing_zero_normalization_exact_despite_decimal_context(self):
        with localcontext() as context:
            context.prec=2
            self.assertEqual(q._safe_rate({'exact_decimal':'100.'+'0'*1100}),Fraction(100))
            self.assertEqual(q._safe_rate({'exact_decimal':'100.0123456789'}),Fraction(1000123456789,10000000000))
            self.assertEqual(q._safe_rate({'exact_decimal':'0.00125'}),Fraction(1,800))
            self.assertEqual(q._safe_rate({'exact_decimal':'1e-1000'}),Fraction(1,10**1000))
        self.assertIsNone(q._safe_rate({'exact_decimal':'1_000'}))

    def test_complete_nonpositive_retains_unknown_and_output_cap(self):
        p=plan((0,));t,d=qualification(p,{})
        result=q.qualify(p,t,d);self.assertIsNone(result['private_rows'][0]['nominal_family'])
        with patch.object(q,'MAX_PRIVATE',1):
            with self.assertRaises(ValueError):q.qualify(p,t,d)


class SupervisorTests(unittest.TestCase):
    def test_all_no_target_normal_closed_output_no_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            output=str(Path(folder).resolve()/'new');r=c.collect_fixture(plan(),output,'http://127.0.0.1:9',limits())
            self.assertTrue(r['complete']);self.assertEqual(r['registered_attempts'],[])
            self.assertEqual(r['public_aggregate']['no_target_rows'],50);self.assertEqual(r['public_aggregate']['accounting_complete_selections'],50)
            manifest=c.strict_json(Path(output,'manifest.private.json').read_bytes());self.assertEqual(len(manifest['members']),105)
            saved=c.strict_json(Path(output,'public_aggregate.json').read_bytes());self.assertFalse(saved['whole_complete']);self.assertEqual(saved['qualified_documents'],0)
            with self.assertRaises(FileExistsError):c.collect_fixture(plan(),output,'http://127.0.0.1:9',limits())

    def test_sparse_queryable_worker_complete_get_loopback(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.paths.append(self.path);body=xml();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=http.server.HTTPServer(('127.0.0.1',0),Handler);server.paths=[];thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                r=c.collect_fixture(plan((2,)),str(Path(folder).resolve()/'new'),'http://127.0.0.1:%d'%server.server_port,limits())
                self.assertTrue(r['complete']);self.assertEqual([a['selection_index'] for a in r['registered_attempts']],[2]);self.assertEqual(r['public_aggregate']['qualified_documents'],1)
                self.assertEqual(len(server.paths),1);self.assertTrue(server.paths[0].startswith('/fdsnws/station/1/query?'))
                self.assertEqual(r['public_aggregate']['no_target_rows'],49)
        finally:server.shutdown();server.server_close();thread.join()

    def test_later_overflow_halts_remaining_queryable_slots_zero_promotion(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.calls+=1;body=xml() if self.server.calls==1 else b'x'*200000
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers()
                try:self.wfile.write(body)
                except OSError:pass
            def log_message(self,*args):pass
        server=http.server.HTTPServer(('127.0.0.1',0),Handler);server.calls=0;thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                out=str(Path(folder).resolve()/'new');r=c.collect_fixture(plan((2,7,10)),out,'http://127.0.0.1:%d'%server.server_port,limits())
                self.assertFalse(r['complete']);self.assertEqual(r['public_aggregate']['qualified_documents'],0);self.assertEqual(server.calls,2)
                summary=c.strict_json(Path(out,'controller_summary.private.json').read_bytes())
                self.assertEqual(summary['selections'][10]['status'],'unattempted');self.assertEqual(summary['selections'][10]['reason'],'halted_after_incomplete')
                self.assertEqual(summary['selections'][11]['status'],'no_target')
                self.assertTrue(r['request_groups_stop_confirmed']);self.assertTrue(r['controller_group_stop_confirmed'])
        finally:server.shutdown();server.server_close();thread.join()
