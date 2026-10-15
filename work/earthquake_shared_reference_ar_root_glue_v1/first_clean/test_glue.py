"""Invented source integration; never actual authority or scientific evidence."""
import ast
import copy
from contextlib import ExitStack
import hashlib
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import bootstrap
import comparator_population as population
import fixtures as f
import root_glue as g


class IntegrationTests(unittest.TestCase):
 def execute(self,x,index):
  request=x.request(index)
  return g.execute_child(x.held,request,expected_pin=x.root_pin,root_spec=x.root_spec,modules=x.modules,primitives=x.primitives,custody=x.custody,journal=x.journal,systemd=x.sd,source_begin=1000.,clock=lambda:1000.)
 def test_real_frozen_child_bridge_admission_comparator_and_cold_exit(self):
  x=f.Fixture();out=self.execute(x,0)
  self.assertEqual(out['status'],'complete');self.assertEqual(out['failure'],None);self.assertEqual(x.runtime.calls,['producer']);self.assertEqual(x.runtime.extra,1);self.assertEqual(x.runtime.exits,1)
  self.assertFalse(x.runtime.active);self.assertEqual(len(out['callbacks']),3)
  self.assertTrue(all(active for i,n,active in x.journal.events if n in('result.json','child_report.json')))
  self.assertEqual(out['result_pin'],x.io.pin(x.journal.read(0,'result.json')))
 def test_real_child_dependency_failure_retained_inside_cold_stack(self):
  x=f.Fixture();x.fail_science=True;out=self.execute(x,0)
  self.assertEqual(out['status'],'incomplete');self.assertEqual(out['failure']['reason'],'invented dependency failure')
  self.assertIn((0,'child_report.json'),x.journal.saved);self.assertTrue(x.journal.events[-1][2]);self.assertEqual(x.runtime.exits,1)
 def test_real_child_independent_two_fits_and_aggregate_no_producer_or_torch(self):
  self.assertNotIn('torch',sys.modules)
  for i in(6,7,8):
   x=f.Fixture();out=self.execute(x,i)
   self.assertEqual(out['status'],'complete',out['failure']);self.assertEqual(x.runtime.calls,['independent']);self.assertEqual(x.runtime.extra,0);self.assertNotIn('torch',sys.modules)
   self.assertTrue(all(active for _,name,active in x.journal.events if name in('audit_report.json','result.json','child_report.json')))
   self.assertEqual(sum(v['name'].startswith('record_')for v in out['callbacks']),66 if i<8 else 0)
 def test_raw_provenance_rejection_prevents_loader_and_native_decode(self):
  x=f.Fixture();request=x.request(0);x.primitives.reject='inputs'
  out=g.execute_child(x.held,request,expected_pin=x.root_pin,root_spec=x.root_spec,modules=x.modules,primitives=x.primitives,custody=x.custody,journal=x.journal,systemd=x.sd,source_begin=1000.,clock=lambda:1000.)
  self.assertEqual(out['status'],'incomplete');self.assertNotIn('native_decode',x.events);self.assertEqual(x.runtime.calls,[])
 def test_previous_custody_rejection_precedes_frozen_child_numeric_decode(self):
  x=f.Fixture();request=x.request(6);x.primitives.reject='prior'
  out=g.execute_child(x.held,request,expected_pin=x.root_pin,root_spec=x.root_spec,modules=x.modules,primitives=x.primitives,custody=x.custody,journal=x.journal,systemd=x.sd,source_begin=1000.,clock=lambda:1000.)
  self.assertEqual(out['status'],'incomplete');self.assertNotIn('native_decode',x.events);self.assertEqual(x.runtime.exits,1)
 def test_failed_current_resource_or_financial_primitive_never_authorizes(self):
  x=f.Fixture();root=x.root();scope=f.f.c.scope(x.g,f.f.c.spec(x.g,0),'parent');x.primitives.reject='current'
  with self.assertRaisesRegex(ValueError,'current rejected'):root.authorize(scope,root.documents(scope),1000.)
  self.assertEqual(root.issued,{})
 def test_boolean_or_wrong_subject_primitive_is_not_authority(self):
  for result in(True,False,{'schema':'root-L-primitive-verification-v1'}):
   x=f.Fixture();root=x.root();x.primitives.current=lambda *args:result;scope=f.f.c.scope(x.g,f.f.c.spec(x.g,0),'parent')
   with self.assertRaisesRegex(ValueError,'primitive_attestation'):root.authorize(scope,root.documents(scope),1000.)
 def test_wrong_external_root_pin_and_nonreadonly_subject_reject(self):
  x=f.Fixture();bad=x.io.pin(b'unheld')
  with self.assertRaises(ValueError):g.Root(x.held,expected_pin=bad,root_spec=x.root_spec,io=x.io,control=f.f.c,projection=f.projection,population=population,primitives=x.primitives,custody=x.custody,journal=x.journal,modules=x.modules,clock=lambda:1000.)
  x.root_spec['mode']=0o600
  with self.assertRaisesRegex(ValueError,'readonly_spec'):x.root()
 def test_changed_requested_source_clock_or_stage_cannot_be_self_pinned(self):
  x=f.Fixture();request=x.request(6);root=x.root();scope=root._input_scope(request['stage']);scope['source_begin']=999.
  with self.assertRaisesRegex(ValueError,'held_input_scope'):root.authenticate_raw(scope,x.raw(),dict(reused_scores=[x.io.read_file(v['spec'],2*1024*1024)for v in x.history['reused_scores']],stronger_envelope=x.io.read_file(x.history['stronger_envelope'],16*1024*1024)),1000.)
 def test_original_closure_and_history_packet_are_not_relabelled(self):
  x=f.Fixture();request=x.request(6);root=x.root();root.active=request
  with ExitStack()as stack:
   adapter=g.compose(root,bridge=f.bridge,runtime=x.runtime,systemd=x.sd,stack=stack);bound=adapter.bind(request,x.raw())
   self.assertEqual(bound['strong_results'][0]['historical_packet_sha256'] if 'historical_packet_sha256'in bound['strong_results'][0]else bound['strong_results'][0]['historical_closure']['packet_sha256'],'e'*64)
   self.assertEqual(bound['origins'][6]['packet_sha256'],'e'*64);self.assertEqual(bound['strong_results'][0]['packet_sha256'],x.packet_sha)
   authority=adapter.audit_authority(request,[dict(stage=n,result_pin=v['result_pin'])for n,v in enumerate(request['previous'])],bound)
   self.assertEqual(authority['original_execution_closure_sha256'],'c'*64);self.assertEqual(authority['score_sha256'],x.io.pin(x.previous[2])['sha256'])
 def test_audit_verification_rejection_retains_child_failure_and_no_report(self):
  x=f.Fixture();request=x.request(6);x.primitives.reject='audit'
  out=g.execute_child(x.held,request,expected_pin=x.root_pin,root_spec=x.root_spec,modules=x.modules,primitives=x.primitives,custody=x.custody,journal=x.journal,systemd=x.sd,source_begin=1000.,clock=lambda:1000.)
  self.assertEqual(out['status'],'incomplete');self.assertNotIn((6,'audit_report.json'),x.journal.saved);self.assertEqual(x.runtime.exits,1)
 def test_prior_closed_binds_exact_known_return_and_new_manager_identity(self):
  x=f.Fixture();root=x.root();snap=x.custody.snapshots[0];raw=x.io.read_file(snap['files']['closed.json'],16*1024*1024);closed=x.io.json_read(raw)
  result=root.prior_closed(x.g,0,closed,snap['inventory']);self.assertEqual(result['known_return_pin'],snap['known_pin']);self.assertEqual(result['result_pin'],x.io.pin(x.previous[0]))
  closed['unit']='foreign.service'
  with self.assertRaises(ValueError):root.prior_closed(x.g,0,closed,snap['inventory'])
 def test_known_metadata_pin_alone_cannot_bypass_independent_custody_verifier(self):
  x=f.Fixture();root=x.root();x.primitives.reject='prior';snap=x.custody.snapshots[0];closed=x.io.json_read(x.io.read_file(snap['files']['closed.json'],16*1024*1024))
  with self.assertRaisesRegex(ValueError,'prior rejected'):root.prior_closed(x.g,0,closed,snap['inventory'])
 def test_exact_frozen_population_source_spans_and_old_arm_only(self):
  source=(f.BASE/'reference/projection/public_contracts/l_processor.py').read_text();tree=ast.parse(source);current=Path(population.__file__).read_text()
  self.assertEqual(population.SOURCE_PROCESSOR_PIN,dict(bytes=len(source.encode()),sha256=hashlib.sha256(source.encode()).hexdigest()))
  for node in tree.body:
   if isinstance(node,ast.FunctionDef)and node.name in population.VALIDATOR_FUNCTION_PINS:
    span='\n'.join(source.splitlines()[node.lineno-1:node.end_lineno])+'\n';self.assertIn(span,current);self.assertEqual(population.VALIDATOR_FUNCTION_PINS[node.name],dict(bytes=len(span.encode()),sha256=hashlib.sha256(span.encode()).hexdigest()))
  for arm in('L','X'):
   with self.assertRaisesRegex(ValueError,'historical_comparator_only'):population.validate_comparators([],{},20261012,arm)

class LaunchTests(unittest.TestCase):
 def launch(self,x,root,index=0):
  request=x.request(index);scope=f.f.c.scope(x.g,request['stage'],'parent');request['parent_authority']=root.authorize(scope,root.documents(scope),1000.);x.journal.saved[index,'dispatch.json']=x.io.canonical(request)
  return request,root.launch(request)
 def test_immutable_launch_exact_held_request_only_once(self):
  x=f.Fixture();root=x.root(None);request,launch=self.launch(x,root)
  self.assertEqual(launch['request_pin'],x.io.pin(x.io.canonical(request)));self.assertEqual(launch['code_pin'],x.io.pin(launch['code'].encode()));compile(launch['code'],'inline','exec')
  self.assertIn('SOURCE_BEGIN=time.monotonic()',launch['code']);self.assertLess(len(launch['code'].encode()),262144)
  value=x.io.json_read(x.journal.read(0,'bootstrap.json'));self.assertEqual(value['root_spec'],x.root_spec);self.assertEqual(value['request'],request)
  with self.assertRaisesRegex(ValueError,'launch_once'):root.launch(request)
 def test_launch_rejects_unissued_parent_authority(self):
  x=f.Fixture();root=x.root(None);request=x.request(0)
  with self.assertRaisesRegex(ValueError,'locally_issued_parent_authority'):root.launch(request)
 def test_actual_inline_bootstrap_read_captures_clock_and_pinned_launch(self):
  x=f.Fixture()
  with tempfile.TemporaryDirectory(dir='/private/tmp')as directory:
   path=Path(directory)/'bootstrap.py';raw=b"raise RuntimeError(str((type(SOURCE_BEGIN).__name__,LAUNCH_PATH,LAUNCH_PIN['bytes'])))\n";path.write_bytes(raw);path.chmod(0o400)
   spec=dict(path=str(path),pin=x.io.pin(raw),mode=0o400);x.io.raw[str(path)]=raw;x.held['launch']['bootstrap']=spec;x.root_spec=x.io.spec('held_root',x.io.canonical(x.held));x.root_pin=x.root_spec['pin'];root=x.root(None);request,launch=self.launch(x,root)
   with self.assertRaisesRegex(RuntimeError,"float.*fake/journal/stage_00/bootstrap.json"):exec(launch['code'],{})
 def test_bootstrap_reader_rejects_link_mode_mutation_and_hash_change(self):
  with tempfile.TemporaryDirectory(dir='/private/tmp')as directory:
   path=Path(directory)/'source.py';path.write_bytes(b'invented source');path.chmod(0o400);raw=path.read_bytes();spec=dict(path=str(path),pin=f.f.IO.pin(raw),mode=0o400)
   self.assertEqual(bootstrap.read(spec,1024),raw)
   link=Path(directory)/'link.py';link.symlink_to(path)
   with self.assertRaises(OSError):bootstrap.read(dict(spec,path=str(link)),1024)
   path.chmod(0o600)
   with self.assertRaisesRegex(ValueError,'bootstrap_member'):bootstrap.read(spec,1024)
   path.write_bytes(b'changed content');path.chmod(0o400)
   with self.assertRaises(ValueError):bootstrap.read(spec,1024)

class ParentTests(unittest.TestCase):
 def parent(self,x,retain,clock=lambda:1000.):
  x.journal.saved={}
  def run(argv,timeout,unit):
   request=x.io.json_read(x.journal.read(0,'bootstrap.json'))['request']
   result=g.execute_child(x.held,request,expected_pin=x.root_pin,root_spec=x.root_spec,modules=x.modules,primitives=x.primitives,custody=x.custody,journal=x.journal,systemd=x.sd,source_begin=1000.,clock=clock)
   raw=x.io.canonical({'invented_summary':result['status']});streams={k:dict(original_bytes=len(v),original_sha256=x.io.pin(v)['sha256'],retained_bytes=len(v),truncated=False,complete_observation=True)for k,v in dict(stdout=raw,stderr=b'').items()}
   return dict(code=0 if result['status']=='complete'else 1,timeout=False,stdout=raw,stderr=b'',streams_complete=True,stream_custody=streams,exception=None)
  x.sd.run=run;x.sd.live=lambda s:dict(unit=s['unit'],active=True,limits=s['limits'],runtime_max_seconds=s['manager_seconds']);x.sd.inspect=lambda unit,t:dict(unit=unit,result='success',active_state='inactive',control_group='')
  return g.run_parent(x.held,0,expected_pin=x.root_pin,root_spec=x.root_spec,modules=x.modules,primitives=x.primitives,custody=x.custody,journal=x.journal,systemd=x.sd,retain_return=retain,clock=clock)
 def test_real_parent_child_bridge_retains_exact_streams_actual_return_and_request(self):
  x=f.Fixture();seen=[]
  def retain(index,result,inventory,answer,request):
   self.assertEqual(result['status'],'complete');self.assertEqual(x.io.json_read(x.journal.read(0,'closed.json')),result);self.assertTrue(answer['streams_complete']);self.assertEqual(answer['code'],0);self.assertEqual(request,x.io.json_read(x.journal.read(0,'dispatch.json')));seen.append(result)
   return dict(schema='root-L-last-return-retention-v1',stage=index,return_pin=x.io.pin(x.io.canonical(result)),proof_pin=x.io.pin(b'invented durable actual return'))
  out=self.parent(x,retain);self.assertEqual(out['status'],'complete');self.assertEqual(len(seen),1);self.assertEqual(x.runtime.exits,1)
 def test_real_parent_also_retains_failed_science_without_retry(self):
  x=f.Fixture();x.fail_science=True;seen=[]
  def retain(index,result,inventory,answer,request):
   seen.append(result['status']);return dict(schema='root-L-last-return-retention-v1',stage=index,return_pin=x.io.pin(x.io.canonical(result)),proof_pin=x.io.pin(b'invented retained failure'))
  out=self.parent(x,retain);self.assertEqual(out['status'],'incomplete');self.assertEqual(seen,['incomplete']);self.assertEqual(x.runtime.calls,['producer']);self.assertIn((0,'late_or_failed.json'),x.journal.saved)
 def test_late_ROOT_last_return_retention_cannot_leave_complete_advance(self):
  x=f.Fixture();now=[1000.]
  def retain(index,result,inventory,answer,request):
   now[0]=8401.;return dict(schema='root-L-last-return-retention-v1',stage=index,return_pin=x.io.pin(x.io.canonical(result)),proof_pin=x.io.pin(b'invented late retained return'))
  with self.assertRaisesRegex(ValueError,'root_retention_deadline'):self.parent(x,retain,lambda:now[0])
  marker=x.io.json_read(x.journal.read(0,'late_or_failed.json'));self.assertEqual(marker['status'],'incomplete');self.assertIn('late_root_retention',marker['errors'])

if __name__=='__main__':unittest.main()
