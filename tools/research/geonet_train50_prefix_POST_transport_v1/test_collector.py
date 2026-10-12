"""Invented strict50 TRAIN plans and numeric-loopback POST transport only."""
from contextlib import contextmanager
from dataclasses import asdict,replace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import copy,io,json,os,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import collector as c
FAST=c.Limits(connection_s=.4,first_body_s=.8,request_s=1.2,start_spacing_s=0,processing_s=8,whole_s=10,term_s=.1,kill_s=.1,body_bytes=64,total_retained_bytes=832,total_consumption_upper=845)
def document(study='invented-post'):
 rows=[{'row_index':i,'global_ordinal':65+i,'original_event_index':149-i,'original_target_index':0,'event_id':'INVENTED%d'%i,'partition':'TRAIN','network':'ZZ','station':'TEST','location':'' if i%2==0 else '10','prefix':'HH','t0_ns':-1 if i==0 else i*10**9,'pick_ns':i*10**9,'metadata_status':'unknown' if i>=40 else 'known','nominal_family':None if i>=40 else 'ENZ' if i<30 else '12Z'} for i in range(50)]
 batches=[]
 for i in range(13):
  indices=list(range(4*i,min(4*i+4,50)));raw=c.entity([rows[j] for j in indices])
  batches.append({'batch_index':i,'row_indices':indices,'requested_row_indices':indices,'request_body':raw.decode(),'request_sha256':c.sha(raw)})
 return {'protocol':c.PROTOCOL,'study_id':study,'proposal_sha256':c.PROPOSAL_SHA,'rows':rows,'batches':batches,'prerequisites':{k:'a'*64 for k in c.PREREQUISITES}}

def no_targets(d,indices):
 for i in indices:
  d['rows'][i].update(original_target_index=None,network=None,station=None,location=None,prefix=None,pick_ns=None,metadata_status='no_target',nominal_family=None)
 for b in d['batches']:
  b['requested_row_indices']=[i for i in b['row_indices'] if d['rows'][i]['original_target_index'] is not None]
  raw=c.entity([d['rows'][i] for i in b['row_indices']])
  b.update(request_body=raw.decode() if raw is not None else None,request_sha256=c.sha(raw) if raw is not None else None)
 return d

def plan(doc=None):return c.validate_plan(c.encode(document() if doc is None else doc))
def gate(p):return c.Authority(plan_sha256=p.sha256,source_files=c.source_pins(),source_manifest_sha256='a'*64,review_receipt_sha256='b'*64,test_proof_sha256='c'*64,pushed_source_commit='d'*40,authorization_reference='invented assertion',runtime_path=str(Path(sys.executable).resolve()),runtime_sha256=c.sha(Path(sys.executable).resolve().read_bytes()),python_version=sys.version,processing_begin=time.monotonic(),prerequisites=json.loads(p.source_bytes)['prerequisites'],**{k:True for k in c.ASSERTIONS})
@contextmanager
def server(body=b'abc',status=200,mode='fixed',delay=0,header_value=None,duplicate=False):
 requests=[]
 class Handler(BaseHTTPRequestHandler):
  protocol_version='HTTP/1.1'
  def log_message(self,*args):pass
  def do_POST(self):
   raw=self.rfile.read(int(self.headers['Content-Length']));requests.append((self.path,raw,dict(self.headers)))
   try:
    self.send_response(status)
    if mode in ('fixed','partial','large'):
     self.send_header('Content-Length',str(len(body) if mode=='fixed' else 200 if mode=='large' else len(body)+20) if header_value is None else header_value)
     if duplicate:self.send_header('Content-Length',str(len(body)))
    if mode.startswith('chunk'):self.send_header('Transfer-Encoding','chunked')
    if status==302:self.send_header('Location','http://127.0.0.1:1/no-follow')
    self.send_header('Connection','close');self.end_headers();time.sleep(delay)
    if mode=='chunk_bad':self.wfile.write(b'99\r\npartial')
    elif mode=='chunk_unclosed':self.wfile.write(b'3\r\nabc\r\n0\r\n')
    elif mode=='chunk_delimiter':self.wfile.write(b'3\r\nabcXX0\r\n\r\n')
    elif mode=='chunk_trailer':self.wfile.write(b'3\r\nabc\r\n0\r\nBad trailer\r\n\r\n')
    elif mode=='chunked':self.wfile.write(('%x\r\n'%len(body)).encode()+body+b'\r\n0\r\n\r\n')
    else:self.wfile.write(body)
    self.wfile.flush()
   except (BrokenPipeError,ConnectionResetError):pass
   finally:self.close_connection=True
 httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler);httpd.daemon_threads=True;thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
 try:yield 'http://127.0.0.1:%d'%httpd.server_port,requests
 finally:httpd.shutdown();httpd.server_close();thread.join()
def run(endpoint,limits=FAST,doc=None):
 td=tempfile.TemporaryDirectory();root=Path(td.name).resolve()/'output';summary=c.collect_fixture(plan(doc),str(root),endpoint,limits);return td,root,summary
class InputTests(unittest.TestCase):
 def test_fixed50_train13_final2_blank_exact_negative_ns(self):
  d=json.loads(plan().source_bytes);self.assertEqual(len(d['rows']),50);self.assertEqual(len(d['batches']),13);self.assertEqual(d['batches'][-1]['row_indices'],[48,49]);self.assertEqual(d['rows'][-1]['global_ordinal'],114);self.assertTrue(d['batches'][0]['request_body'].startswith('format=miniseed\n'));self.assertIn(' -- HH? ',d['batches'][0]['request_body']);self.assertIn('1969-12-31T23:59:56.999999999Z',d['batches'][0]['request_body']);self.assertEqual(c.utc_ns(-1),'1969-12-31T23:59:59.999999999Z')
 def test_all_order_types_partitions_annotations_reject(self):
  changes=[lambda d:d['rows'][0].update(row_index=True),lambda d:d['rows'][0].update(global_ordinal=True),lambda d:d['rows'][1].update(original_event_index=149),lambda d:d['rows'][1].update(event_id='INVENTED0'),lambda d:d['rows'][0].update(original_target_index=0.0),lambda d:d['rows'][0].update(partition='DEV'),lambda d:d['rows'][0].update(partition='TEST'),lambda d:d['rows'][0].update(t0_ns=float('inf')),lambda d:d['rows'][0].update(pick_ns=True),lambda d:d['rows'][49].update(metadata_status='known',nominal_family=None),lambda d:d['batches'][0].update(row_indices=[True,1,2,3]),lambda d:d['batches'][0].update(batch_index=0.0),lambda d:d['rows'].pop(),lambda d:d['batches'].reverse(),lambda d:d['batches'][0].update(requested_row_indices=[0,1,2])]
  for change in changes:
   d=document();change(d)
   with self.subTest(change=change),self.assertRaises(ValueError):plan(d)
 def test_ns_endpoints_identity_and_entity_whitespace_reconstruction(self):
  for k,v in (('network','Z Z'),('station','TEST\nX'),('location','--'),('prefix','HH?'),('t0_ns',-2**63),('t0_ns',2**63-1)):
   d=document();d['rows'][0][k]=v
   with self.assertRaises(ValueError):plan(d)
  for k,v in (('request_body','format=mseed\n'),('request_sha256','0'*64),('EXTRA','private')):
   d=document();d['batches'][0][k]=v
   with self.assertRaises(ValueError):plan(d)
 def test_json_duplicates_nonfinite_extra_and_byte_cap(self):
  for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'x'*(c.PLAN_CAP+1)):
   with self.assertRaises(ValueError):c.validate_plan(raw)
  d=document();d['EXTRA']=True
  with self.assertRaises(ValueError):plan(d)
 def test_hostile_objects_reject_before_comparison(self):
  class Hostile:
   def __eq__(self,other):raise AssertionError('hostile comparison')
   def __hash__(self):return 1
  with self.assertRaises(ValueError):c.text(Hostile(),'.*')
  with self.assertRaises(ValueError):c.fields({Hostile():1},('x',))
  p=plan(document(c.STUDY));a=gate(p)
  with self.assertRaises(ValueError):replace(a,plan_sha256=Hostile()).check(p)
 def test_actual_authority_fixtures_assertions_and_pins(self):
  p=plan(document(c.STUDY));a=gate(p);a.check(p)
  for key in c.ASSERTIONS:
   for bad in (False,1):
    with self.assertRaises(ValueError):replace(a,**{key:bad}).check(p)
  for key in ('runtime_sha256','source_manifest_sha256','review_receipt_sha256','pushed_source_commit'):
   with self.assertRaises(ValueError):replace(a,**{key:''}).check(p)
  with self.assertRaises(ValueError):gate(plan()).check(plan())
 def test_parent_processing_begin_is_required_finite_original_and_bound(self):
  p=plan(document(c.STUDY));a=gate(p)
  for bad in (True,float('nan'),-1,time.monotonic()+100,time.monotonic()-2200):
   with self.assertRaises(ValueError):replace(a,processing_begin=bad).check(p)
  arg={'plan':p.source_bytes.decode(),'fixture':False,'limits':asdict(c.DEFAULT),'endpoint':c.ENDPOINT,'authority':asdict(a),'begin':a.processing_begin+1}
  with self.assertRaisesRegex(ValueError,'parent processing clock binding'):c.check_context(arg)
 def test_changed_controls_immutable_plan_and_no_actual_hook(self):
  for k,v in (('body_bytes',True),('probe_bytes',2),('processing_s',float('nan')),('total_retained_bytes',0),('request_s',121)):
   d=asdict(FAST);d[k]=v
   with self.assertRaises(ValueError):c.checked_limits(d,True)
  with self.assertRaises(ValueError):c.checked_limits(asdict(FAST),False)
  with patch.object(c,'spawn') as sp,tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError):c.collect(plan(),str(Path(td)/'out'),None)
   with self.assertRaises(ValueError):c.collect_fixture(replace(plan(),sha256='0'*64),str(Path(td)/'out'),'http://127.0.0.1:1',FAST)
   sp.assert_not_called()
 def test_exact_header_framing_nobody_parser_contract(self):
  self.assertEqual(c.header_framing(204,[]),('no_body',None));self.assertEqual(c.header_framing(304,[('Content-Length','9')]),('no_body',9));self.assertEqual(c.header_framing(200,[('Transfer-Encoding','Chunked')]),('chunked',None))
  for items in ([('Content-Length','1'),('Content-Length','1')],[('Content-Length','1'),('Transfer-Encoding','chunked')],[('Content-Length','1 ')],[('Content-Length','+1')],[('Transfer-Encoding','chunked ')],[('Transfer-Encoding','gzip')]):
   with self.assertRaises(ValueError):c.header_framing(200,items)
  for status in (101,103):
   with self.assertRaises(ValueError):c.header_framing(status,[])
 def test_chunk_evidence_delimiters_trailers_caps_and_payload_association(self):
  def read(raw,cap=131072):
   with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'proof';reader=c.ChunkReader(io.BytesIO(raw),p,cap);body=b''
    try:
     while True:
      part=reader.read1(2)
      if not part:break
      body+=part
     self.assertTrue(reader.complete)
    finally:reader.close()
    return body,p.read_bytes()
  body,evidence=read(b'2;tag=x\r\nab\r\n1\r\nc\r\n0\r\nX-Test: yes\r\n\r\n')
  self.assertEqual(body,b'abc');self.assertEqual(evidence,b'2;tag=x\r\n\r\n1\r\n\r\n0\r\nX-Test: yes\r\n\r\n')
  for raw,cap in ((b'3\r\nabcXX0\r\n\r\n',131072),(b'3\r\nabc\r\n0\r\n',131072),(b'0\r\nBad trailer\r\n\r\n',131072),(b'0\r\n'+b'X: a\r\n'*100+b'\r\n',131072),(b'0\r\n\r\n',4),(b'f'*17+b'\r\n',131072),(b'0'+b';x'*(32768)+b'\r\n',131072)):
   with self.subTest(raw_length=len(raw),cap=cap),self.assertRaises(ValueError):read(raw,cap)
class ProfileTests(unittest.TestCase):
 def test_no_target_null_unknown_family_and_unsorted_roster(self):
  d=no_targets(document(),[0,1,48,49]);d['rows'][0]['t0_ns']=None
  p=plan(d);self.assertEqual(json.loads(p.source_bytes)['batches'][-1]['request_body'],None)
  self.assertEqual(d['batches'][0]['requested_row_indices'],[2,3]);self.assertEqual(len(d['batches'][0]['request_body'].splitlines()),3)
  self.assertIn('INVENTED49',p.source_bytes.decode())
  for key,value in [('station','X'),('pick_ns',0),('original_target_index',False)]:
   bad=copy.deepcopy(d);bad['rows'][0][key]=value
   with self.assertRaises(ValueError):plan(bad)
 def test_unknown_family_queryable_is_never_suppressed(self):
  d=document();self.assertEqual(len(d['batches'][-1]['requested_row_indices']),2)
  self.assertEqual(d['rows'][49]['metadata_status'],'unknown')
  self.assertIn('HH?',d['batches'][-1]['request_body'])
 def test_long_station_literal_not_truncated(self):
  d=document();d['rows'][0]['station']='ABCDEFGH';raw=c.entity(d['rows'][:4]);d['batches'][0].update(request_body=raw.decode(),request_sha256=c.sha(raw))
  plan(d);self.assertIn(' ABCDEFGH ',d['batches'][0]['request_body'])
  d['rows'][0]['station']='ABCDEFGHI'
  with self.assertRaises(ValueError):plan(d)
 def test_old_profile_not_accepted(self):
  d=document();d['study_id']='geonet-original-TRAINDEV65-prefix3-native-POST-v2'
  with self.assertRaises(ValueError):plan(d)
  d=document();d['rows']+=copy.deepcopy(d['rows'][:15])
  with self.assertRaises(ValueError):plan(d)
 def test_no_selection_cannot_emit_format_only_request(self):
  d=no_targets(document(),range(4));self.assertIsNone(c.entity(d['rows'][:4]))
  for field,value in [('request_body','format=miniseed\n'),('request_sha256','a'*64),('requested_row_indices',[0])]:
   bad=copy.deepcopy(d);bad['batches'][0][field]=value
   with self.assertRaises(ValueError):plan(bad)
 def test_unknown_controller_counts_include_no_selection(self):
  d=no_targets(document(),range(4));p=c.public({},False,[{'batch_index':1,'worker_group':1}],FAST,c.annotations(d))
  self.assertEqual((p['attempted_batches'],p['unattempted_batches'],p['no_selection_batches']),(1,11,1))
  self.assertEqual(p['consumption_upper'],65);self.assertIsNone(p['retained_response_bytes'])
 def test_all_no_targets_have_no_requests_but_fifty_slots(self):
  d=no_targets(document(),range(50))
  td,root,out=run('http://127.0.0.1:1',doc=d);self.addCleanup(td.cleanup)
  self.assertTrue(out['complete'],out);self.assertEqual(out['registered_attempts'],[])
  self.assertEqual(out['public_aggregate']['no_selection_batches'],13)
  self.assertEqual(out['public_aggregate']['qualified_batches'],0)
  self.assertEqual(len(list(root.glob('*.request.private'))),0)
  summary=json.loads((root/'controller_summary.private.json').read_bytes())
  self.assertTrue(all(r['status']=='no_selection' and r['request'] is None and 'http_status' not in r for r in summary['batches']))
 def test_no_selection_gap_registration_and_final2_absent(self):
  d=no_targets(document(),list(range(4))+[48,49])
  with server() as (endpoint,requests):
   td,root,out=run(endpoint,doc=d);self.addCleanup(td.cleanup)
   self.assertTrue(out['complete'],out);self.assertEqual(len(requests),11)
   self.assertEqual([r['batch_index'] for r in out['registered_attempts']],list(range(1,12)))
   self.assertFalse((root/'000.request.private').exists());self.assertFalse((root/'012.request.private').exists())
   self.assertEqual(out['public_aggregate']['no_selection_batches'],2)
 def test_partial_halt_still_retains_no_selection_logical_blocks(self):
  d=no_targets(document(),[48,49])
  with server(mode='partial') as (endpoint,requests):
   td,root,out=run(endpoint,doc=d);self.addCleanup(td.cleanup)
   self.assertFalse(out['complete']);self.assertEqual(len(requests),1)
   summary=json.loads((root/'controller_summary.private.json').read_bytes())
   self.assertEqual(summary['batches'][-1]['status'],'no_selection')
   self.assertEqual(out['public_aggregate']['qualified_batches'],0)

class TransportTests(unittest.TestCase):
 def test_13_binary_posts_exact_entities_groups_and_closed_manifest(self):
  with server(body=b'\x00\xffbinary') as (endpoint,requests):
   td,root,result=run(endpoint);self.addCleanup(td.cleanup);self.assertTrue(result['complete'],result);self.assertEqual(len(requests),13);self.assertEqual([r[1] for r in requests],[b['request_body'].encode() for b in document()['batches']]);self.assertEqual(result['public_aggregate']['qualified_batches'],13)
   manifest=json.loads((root/'manifest.private.json').read_bytes());self.assertEqual(len(manifest['members']),57)
   saved=json.loads((root/'public_aggregate.json').read_bytes());self.assertFalse(saved['whole_complete']);self.assertEqual(saved['qualified_batches'],0);self.assertEqual({k:v for k,v in saved.items() if k not in ('whole_complete','qualified_batches')},{k:v for k,v in result['public_aggregate'].items() if k not in ('whole_complete','qualified_batches')})
   for p in manifest['members']:
    raw=(root/p['name']).read_bytes();self.assertEqual(len(raw),p['bytes']);self.assertEqual(c.sha(raw),p['sha256'])
   summary=json.loads((root/'controller_summary.private.json').read_bytes());self.assertEqual(len(set(summary['worker_groups'])),13);self.assertTrue(all(not c.group_exists(pid) for pid in summary['worker_groups']));self.assertNotIn('Authorization',requests[0][2]);self.assertEqual(requests[0][2]['Accept-Encoding'],'identity')
 def test_204_error_redirect_empty_account_all_qualify0(self):
  for status,body in ((204,b''),(404,b'error'),(302,b'redirect'),(200,b'')):
   with self.subTest(status=status),server(status=status,body=body) as (endpoint,requests):
    td,root,result=run(endpoint);self.addCleanup(td.cleanup);self.assertTrue(result['complete'],result);self.assertEqual(len(requests),13);self.assertEqual(result['public_aggregate']['qualified_batches'],0)
 def test_partial_deadline_bad_framing_halt_all13_promote0(self):
  for kwargs in ({'mode':'partial'},{'mode':'chunk_bad'},{'duplicate':True},{'header_value':'bad'},{'delay':1.5}):
   with self.subTest(kwargs=kwargs),server(**kwargs) as (endpoint,requests):
    td,root,result=run(endpoint);self.addCleanup(td.cleanup);self.assertFalse(result['complete']);self.assertEqual(result['public_aggregate']['qualified_batches'],0);self.assertEqual(len(requests),1);summary=json.loads((root/'controller_summary.private.json').read_bytes());self.assertEqual(len(summary['batches']),13);self.assertTrue(all(r['reason']=='halted_after_incomplete' for r in summary['batches'][1:]))
 def test_fixed_chunked_eof_exactcap_and_one_probe_overflow(self):
  for mode,body,complete,probe in (('fixed',b'x'*64,True,0),('chunked',b'x'*64,True,0),('eof',b'x'*64,True,0),('eof',b'x'*65,False,1),('large',b'x'*64,False,0)):
   with self.subTest(mode=mode,size=len(body)),server(mode=mode,body=body) as (endpoint,requests):
    td,root,result=run(endpoint);self.addCleanup(td.cleanup);self.assertEqual(result['complete'],complete,result);self.assertEqual(result['public_aggregate']['overflow_probe_bytes'],probe);self.assertLessEqual(result['public_aggregate']['retained_response_bytes'],1088);self.assertLessEqual(result['public_aggregate']['consumption_upper'],1105)
    if mode=='chunked':
     summary=json.loads((root/'controller_summary.private.json').read_bytes());row=summary['batches'][0];self.assertTrue(row['framing_evidence_complete']);self.assertEqual((root/row['framing_evidence']['name']).read_bytes(),b'40\r\n\r\n0\r\n\r\n');self.assertLessEqual(row['headers']['bytes']+row['framing_evidence']['bytes'],FAST.header_diagnostic_bytes)
 def test_malformed_terminal_chunks_and_informational_final_halt(self):
  for kwargs in ({'mode':'chunk_unclosed'},{'mode':'chunk_delimiter'},{'mode':'chunk_trailer'},{'mode':'eof','status':101,'body':b''},{'mode':'eof','status':103,'body':b''}):
   with self.subTest(kwargs=kwargs),server(**kwargs) as (endpoint,requests):
    td,root,result=run(endpoint);self.addCleanup(td.cleanup);self.assertFalse(result['complete']);self.assertEqual(len(requests),1);self.assertEqual(result['public_aggregate']['qualified_batches'],0);rows=json.loads((root/'controller_summary.private.json').read_bytes())['batches'];self.assertFalse(rows[0]['attempt_accounting_complete']);self.assertTrue(all(r['reason']=='halted_after_incomplete' for r in rows[1:]))
 def test_absent_trusted_controller_summary_charges_registered_allowances(self):
  original=c.read_regular
  def rejected(path,cap):
   if path.endswith('/controller_summary.private.json'):raise ValueError('invented summary loss')
   return original(path,cap)
  with server() as (endpoint,requests),patch.object(c,'read_regular',side_effect=rejected):
   td,root,result=run(endpoint);self.addCleanup(td.cleanup);self.assertFalse(result['complete']);p=result['public_aggregate'];self.assertFalse(p['accounting_known']);self.assertEqual(p['attempted_batches'],13);self.assertEqual(p['consumption_upper'],13*65);self.assertIsNone(p['retained_response_bytes']);self.assertIsNone(p['overflow_probe_bytes']);self.assertEqual(p['qualified_batches'],0);self.assertEqual([r['batch_index'] for r in result['registered_attempts']],list(range(13)));self.assertIsNone(result['manifest_sha256']);self.assertFalse((root/'manifest.private.json').exists())
 def test_launch_cutoff_never_implies_unseen_incomplete_attempt(self):
  with tempfile.TemporaryDirectory() as td,patch.object(c.time,'monotonic',return_value=8.1),patch.object(c,'emit'),patch.object(c,'request') as request:
   p=plan();arg={'plan':p.source_bytes.decode(),'root':str(Path(td).resolve()),'begin':0,'fixture':True,'limits':asdict(FAST),'endpoint':'http://127.0.0.1:1','authority':None};c.controller(arg);summary=json.loads((Path(td)/'controller_summary.private.json').read_bytes());self.assertEqual(summary['attempts'],0);self.assertTrue(all(r['reason']=='launch_cutoff' for r in summary['batches']));request.assert_not_called()
 def test_existing_symlink_output_no_fallback(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td).resolve();out=root/'out';out.mkdir();(out/'unrelated').write_bytes(b'preserve')
   with self.assertRaises(FileExistsError):c.collect_fixture(plan(),str(out),'http://127.0.0.1:1',FAST)
   link=root/'link';link.symlink_to(out)
   with self.assertRaises(FileExistsError):c.collect_fixture(plan(),str(link),'http://127.0.0.1:1',FAST)
   self.assertEqual((out/'unrelated').read_bytes(),b'preserve')
   for endpoint in (c.ENDPOINT,'http://localhost:1','http://u:p@127.0.0.1:1','http://127.0.0.1:1?query'):
    with self.assertRaises(ValueError):c.collect_fixture(plan(),str(root/'never'),endpoint,FAST)
 def test_receipt_replacement_closed_names_and_public_privacy(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td).resolve()/'receipt';owned=c.write_new(p,b'own');other=p.parent/'other';other.write_bytes(b'unrelated');os.replace(other,p)
   with self.assertRaises(ValueError):c.finalize_receipt(p,owned,{})
   self.assertEqual(p.read_bytes(),b'unrelated')
  for bad in ('013.body.private','017.body.private','../000.body.private','000.extra.body.private','source.txt'):
   with self.assertRaises(ValueError):c.member_cap(bad,FAST)
  for token in ('INVENTED','event_id','t0_ns','worker_group','sha256','body_path'):self.assertNotIn(token,json.dumps(c.public({},False,row_annotations=c.annotations(document()))))
 def test_spacing_and_group_failure_whole_veto(self):
  with server() as (endpoint,requests):
   td,root,result=run(endpoint,replace(FAST,start_spacing_s=.08));self.addCleanup(td.cleanup);self.assertTrue(result['complete'],result);rows=json.loads((root/'controller_summary.private.json').read_bytes())['batches'];self.assertTrue(all(b['start']-a['start']>=.08 for a,b in zip(rows,rows[1:])))
  with server() as (endpoint,requests),patch.object(c,'stop_group',return_value=False):
   td,root,result=run(endpoint);self.addCleanup(td.cleanup);self.assertFalse(result['complete']);self.assertEqual(result['public_aggregate']['qualified_batches'],0)
 def test_stalled_launch_retains_failure_and_never_releases_request(self):
  original=c.spawn
  def stalled(mode):time.sleep(.25);return original(mode)
  limits=replace(FAST,connection_s=.05,first_body_s=.1,request_s=.15,processing_s=.2,whole_s=.6,term_s=.05,kill_s=.05)
  with server() as (endpoint,requests),patch.object(c,'spawn',side_effect=stalled):
   td,root,result=run(endpoint,limits);self.addCleanup(td.cleanup);self.assertFalse(result['complete']);self.assertEqual(requests,[]);self.assertTrue(result['controller_group_stop_confirmed'])
 def test_final_return_timestamp_after_deadline_never_promotes(self):
  original_read=c.read_regular;original_time=time.monotonic;pending={'remaining':None}
  def read(path,cap):
   value=original_read(path,cap)
   if Path(path).name=='receipt.private.json':pending['remaining']=2
   return value
  def clock():
   now=original_time()
   if pending['remaining'] is not None and pending['remaining']>0:
    pending['remaining']-=1
    if pending['remaining']==0:return now+FAST.whole_s+1
   return now
  with server() as (endpoint,requests),patch.object(c,'read_regular',side_effect=read),patch.object(c.time,'monotonic',side_effect=clock):
   td,root,out=run(endpoint);self.addCleanup(td.cleanup)
   self.assertFalse(out['complete']);self.assertEqual(out['reason'],'deadline')
   self.assertGreater(out['elapsed_s'],FAST.whole_s)
   self.assertEqual(out['public_aggregate']['qualified_batches'],0)
 def test_final_receipt_failure_preserves_fail_closed_result(self):
  original=c.finalize_receipt
  def failed(path,owned,value):
   if value.get('complete'):raise OSError('invented finalization failure')
   return original(path,owned,value)
  with server() as (endpoint,requests),patch.object(c,'finalize_receipt',side_effect=failed):
   td,root,result=run(endpoint);self.addCleanup(td.cleanup);self.assertFalse(result['complete']);self.assertEqual(result['public_aggregate']['qualified_batches'],0);self.assertFalse(json.loads((root/'receipt.private.json').read_bytes())['complete'])
   saved=json.loads((root/'public_aggregate.json').read_bytes());self.assertFalse(saved['whole_complete']);self.assertEqual(saved['qualified_batches'],0)
if __name__=='__main__':unittest.main()
