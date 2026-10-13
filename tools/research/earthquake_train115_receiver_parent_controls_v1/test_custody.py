import ast,unittest,tempfile,json,os,subprocess,hashlib
from unittest.mock import patch
from pathlib import Path
class Custody(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name);tree=ast.parse(Path('fit_child.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='put');self.ns=dict(out=self.out,json=json,os=os,output_bytes=0,output_members=0);exec(compile(ast.Module(body=[node],type_ignores=[]),'put','exec'),self.ns)
 def tearDown(self):self.tmp.cleanup()
 def test_private_durable_closed_member(self):
  self.ns['put']('result.private.json',{'status':'incomplete','advance':False},1024);p=self.out/'result.private.json';self.assertEqual(p.stat().st_mode&0o777,0o400);self.assertFalse(json.loads(p.read_bytes())['advance'])
 def test_duplicate_preserves_old_checkpoint(self):
  self.ns['put']('checkpoint.private.npz',b'old',10)
  with self.assertRaises(FileExistsError):self.ns['put']('checkpoint.private.npz',b'new',10)
  self.assertEqual((self.out/'checkpoint.private.npz').read_bytes(),b'old')
 def test_permember_cap_beforewrite(self):
  with self.assertRaises(AssertionError):self.ns['put']('oversized.private',b'123',2)
  self.assertFalse((self.out/'oversized.private').exists())
 def test_whole_custody_cap_beforewrite(self):
  self.ns['output_bytes']=268435455
  with self.assertRaises(AssertionError):self.ns['put']('oversized.private',b'12',2)
  self.assertFalse((self.out/'oversized.private').exists())
 def test_closed_member_budget_beforewrite(self):
  self.ns['output_members']=64
  with self.assertRaises(AssertionError):self.ns['put']('excess.private',b'1',1)
  self.assertFalse((self.out/'excess.private').exists())
 def test_nonfinite_scalar_not_exported(self):
  with self.assertRaises(ValueError):self.ns['put']('bad.private.json',{'x':float('nan')},100)
  self.assertFalse((self.out/'bad.private.json').exists())

 def test_directory_fsync_before_acknowledgement(self):
  import stat
  seen=[];original=os.fsync
  def record(fd):seen.append(stat.S_ISDIR(os.fstat(fd).st_mode));return original(fd)
  with patch.object(os,'fsync',side_effect=record):self.ns['put']('checkpoint.private.npz',b'complete',100)
  self.assertIn(True,seen);self.assertTrue(seen[-1])
class Transport(unittest.TestCase):
 def setUp(self):
  tree=ast.parse(Path('controller.py').read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in('bounded_stream','transport')];ns={'subprocess':subprocess,'json':json,'hashlib':hashlib};exec(compile(ast.Module(body=nodes,type_ignores=[]),'transport','exec'),ns);self.transport=ns['transport']
 def test_timeout_keeps_partial_evidence_without_retry(self):
  failure=subprocess.TimeoutExpired(['invented'],7,output=b'partial evidence',stderr=b'connection lost')
  with patch.object(subprocess,'run',side_effect=failure)as mock:result=self.transport(['invented'],b'synthetic',7)
  self.assertEqual(mock.call_count,1);self.assertIsNone(result['ssh_exit']);self.assertEqual(result['stdout'],'partial evidence');self.assertEqual(result['status'],'incomplete');self.assertTrue(result['no_retry'])
 def test_timeout_partial_output_bounded(self):
  failure=subprocess.TimeoutExpired(['invented'],7,output=b'x'*200000)
  with patch.object(subprocess,'run',side_effect=failure):result=self.transport(['invented'],b'synthetic',7)
  self.assertLessEqual(result['stream_custody']['stdout']['retained_serialized_bytes'],61440);self.assertTrue(result['stream_custody']['stdout']['truncated']);self.assertLess(len(json.dumps(result).encode()),262144);self.assertEqual(result['stderr'],'')

 def test_two_escaped_unicode_streams_fit_durable_receipt(self):
  failure=subprocess.TimeoutExpired(['invented'],7,output=('😀\n'*100000).encode(),stderr=('😀\t'*100000).encode())
  with patch.object(subprocess,'run',side_effect=failure):result=self.transport(['invented'],b'synthetic',7)
  self.assertLessEqual(len(json.dumps(result).encode()),262144);self.assertTrue(result['stream_custody']['stdout']['truncated']);self.assertTrue(result['stream_custody']['stderr']['truncated'])
class History(unittest.TestCase):
 def test_first_history_durable_private_and_second_uses_open_fd(self):
  import stat
  with tempfile.TemporaryDirectory()as temp:
   tree=ast.parse(Path('fit_child.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='history');ns=dict(out=Path(temp),json=json,os=os,historyfiles={},historycounts={});exec(compile(ast.Module(body=[node],type_ignores=[]),'history','exec'),ns);seen=[];original=os.fsync
   def record(fd):seen.append(stat.S_ISDIR(os.fstat(fd).st_mode));return original(fd)
   try:
    with patch.object(os,'fsync',side_effect=record):ns['history'](20261012,'C',{'update':1})
    path=Path(temp)/'history_20261012_C.private.jsonl';self.assertEqual(path.stat().st_mode&0o777,0o400);self.assertTrue(seen[-1]);ns['history'](20261012,'C',{'update':2});self.assertEqual(len(path.read_text().splitlines()),2)
   finally:
    for stream in ns['historyfiles'].values():stream.close()

class RemoteManager(unittest.TestCase):
 def test_timeout_marker_and_partial_survive_stop_failure(self):
  import io,types,contextlib,sys
  tree=ast.parse(Path('controller.py').read_text());remote=next(n.value.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='remote'for t in n.targets));child='invented never executed';pin={'bytes':len(child.encode()),'sha256':hashlib.sha256(child.encode()).hexdigest()};payload={'child':child,'gate':{'source_commit':'0'*40,'reviewed_child_pin':pin},'runtime':{}}
  with tempfile.TemporaryDirectory()as temp:
   source=remote.replace('/home/ec2-user',temp);output=io.StringIO()
   def observed(args,**kwargs):return b'0000000000000000000000000000000000000000\n'if args[0]=='git'else 'Result=success\nActiveState=inactive\nControlGroup=\n'
   failure=subprocess.TimeoutExpired(['invented-manager'],3520,output=b'last diagnostic',stderr=b'last traceback');stopfail=subprocess.TimeoutExpired(['invented-stop'],10)
   with patch.object(sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode()))),patch.object(subprocess,'check_output',side_effect=observed),patch.object(subprocess,'run',side_effect=[failure,stopfail])as run,contextlib.redirect_stdout(output):exec(compile(source,'invented-remote','exec'),{})
   self.assertEqual(run.call_count,2);directory=Path(temp)/'eew-train115-receiver-renewal-fits-v2';marker=json.loads((directory/'manager_timeout.private.json').read_bytes());result=json.loads((directory/'parent_return.private.json').read_bytes());self.assertEqual(marker['stdout'],'last diagnostic');self.assertEqual(marker['stderr'],'last traceback');self.assertTrue(result['manager_timeout']);self.assertEqual(result['stop_evidence']['exception_type'],'TimeoutExpired');self.assertEqual((directory/'manager_timeout.private.json').stat().st_mode&0o777,0o400)

 def test_verbose_normal_return_keeps_bounded_diagnostics(self):
  import io,types,contextlib,sys
  tree=ast.parse(Path('controller.py').read_text());remote=next(n.value.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='remote'for t in n.targets));child='invented never executed';pin={'bytes':len(child.encode()),'sha256':hashlib.sha256(child.encode()).hexdigest()};payload={'child':child,'gate':{'source_commit':'0'*40,'reviewed_child_pin':pin},'runtime':{}}
  with tempfile.TemporaryDirectory()as temp:
   source=remote.replace('/home/ec2-user',temp);output=io.StringIO()
   def observed(args,**kwargs):return b'0000000000000000000000000000000000000000\n'if args[0]=='git'else 'Result=success\nActiveState=inactive\nControlGroup=\n'
   complete=subprocess.CompletedProcess(['invented-manager'],0,stdout='x'*70000,stderr='last diagnostic')
   with patch.object(sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode()))),patch.object(subprocess,'check_output',side_effect=observed),patch.object(subprocess,'run',return_value=complete)as run,contextlib.redirect_stdout(output):exec(compile(source,'invented-remote','exec'),{})
   self.assertEqual(run.call_count,1);directory=Path(temp)/'eew-train115-receiver-renewal-fits-v2';result=json.loads((directory/'parent_return.private.json').read_bytes());self.assertEqual(result['unit_exit'],0);self.assertEqual(result['manager_status'],'incomplete');self.assertTrue(result['manager_output_limited']);self.assertEqual(result['manager_stream_custody']['stdout']['original_bytes'],70000);self.assertEqual(result['stderr'],'last diagnostic');self.assertLessEqual(len(json.dumps(result['stdout']).encode()),61440)

 def test_manager_evidence_precedes_failed_state_query(self):
  import io,types,contextlib,sys
  tree=ast.parse(Path('controller.py').read_text());remote=next(n.value.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='remote'for t in n.targets));child='invented never executed';pin={'bytes':len(child.encode()),'sha256':hashlib.sha256(child.encode()).hexdigest()};payload={'child':child,'gate':{'source_commit':'0'*40,'reviewed_child_pin':pin},'runtime':{}}
  with tempfile.TemporaryDirectory()as temp:
   source=remote.replace('/home/ec2-user',temp);output=io.StringIO();complete=subprocess.CompletedProcess(['invented-manager'],1,stdout='final trace',stderr='failure details')
   def observed(args,**kwargs):
    if args[0]=='git':return b'0000000000000000000000000000000000000000\n'
    raise RuntimeError('invented state-query failure')
   with patch.object(sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode()))),patch.object(subprocess,'check_output',side_effect=observed),patch.object(subprocess,'run',return_value=complete)as run,contextlib.redirect_stdout(output):
    with self.assertRaises(RuntimeError):exec(compile(source,'invented-remote','exec'),{})
   self.assertEqual(run.call_count,1);path=Path(temp)/'eew-train115-receiver-renewal-fits-v2/manager_return.private.json';journal=json.loads(path.read_bytes());self.assertEqual(journal['stdout'],'final trace');self.assertEqual(journal['stderr'],'failure details');self.assertEqual(journal['status'],'incomplete_pending_control_group_verification');self.assertEqual(path.stat().st_mode&0o777,0o400)

 def test_invalid_utf8_is_hashed_before_replacement_decoding(self):
  import io,types,contextlib,sys
  tree=ast.parse(Path('controller.py').read_text());remote=next(n.value.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='remote'for t in n.targets));child='invented never executed';pin={'bytes':len(child.encode()),'sha256':hashlib.sha256(child.encode()).hexdigest()};payload={'child':child,'gate':{'source_commit':'0'*40,'reviewed_child_pin':pin},'runtime':{}}
  with tempfile.TemporaryDirectory()as temp:
   source=remote.replace('/home/ec2-user',temp);output=io.StringIO();invalid=b'raw \xff diagnostic';complete=subprocess.CompletedProcess(['invented-manager'],1,stdout=invalid,stderr=b'trace \xfe')
   def observed(args,**kwargs):return b'0000000000000000000000000000000000000000\n'if args[0]=='git'else 'Result=success\nActiveState=inactive\nControlGroup=\n'
   with patch.object(sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode()))),patch.object(subprocess,'check_output',side_effect=observed),patch.object(subprocess,'run',return_value=complete)as run,contextlib.redirect_stdout(output):exec(compile(source,'invented-remote','exec'),{})
   self.assertNotIn('text',run.call_args.kwargs);directory=Path(temp)/'eew-train115-receiver-renewal-fits-v2';journal=json.loads((directory/'manager_return.private.json').read_bytes());self.assertEqual(journal['manager_stream_custody']['stdout']['original_sha256'],hashlib.sha256(invalid).hexdigest());self.assertEqual(journal['manager_stream_custody']['stdout']['original_bytes'],len(invalid));self.assertIn('diagnostic',journal['stdout'])

 def test_timeout_receipts_preserve_raw_oversized_invalid_bytes(self):
  import io,types,contextlib,sys
  tree=ast.parse(Path('controller.py').read_text());remote=next(n.value.value for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='remote'for t in n.targets));child='invented never executed';pin={'bytes':len(child.encode()),'sha256':hashlib.sha256(child.encode()).hexdigest()};payload={'child':child,'gate':{'source_commit':'0'*40,'reviewed_child_pin':pin},'runtime':{}}
  with tempfile.TemporaryDirectory()as temp:
   source=remote.replace('/home/ec2-user',temp);output=io.StringIO();raw=b'\xff'*70000;failure=subprocess.TimeoutExpired(['invented-manager'],3520,output=raw,stderr=b'\xfe');stopped=subprocess.CompletedProcess(['invented-stop'],0,stdout='',stderr='')
   def observed(args,**kwargs):return b'0000000000000000000000000000000000000000\n'if args[0]=='git'else 'Result=success\nActiveState=inactive\nControlGroup=\n'
   with patch.object(sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode()))),patch.object(subprocess,'check_output',side_effect=observed),patch.object(subprocess,'run',side_effect=[failure,stopped]),contextlib.redirect_stdout(output):exec(compile(source,'invented-remote','exec'),{})
   directory=Path(temp)/'eew-train115-receiver-renewal-fits-v2';marker=json.loads((directory/'manager_timeout.private.json').read_bytes())
   for name in('manager_return.private.json','parent_return.private.json'):
    result=json.loads((directory/name).read_bytes());custody=result['manager_stream_custody']['stdout'];self.assertEqual(custody,marker['stream_custody']['stdout']);self.assertEqual(custody['original_sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(custody['original_bytes'],70000);self.assertTrue(custody['truncated']);self.assertTrue(result['manager_output_limited'])
