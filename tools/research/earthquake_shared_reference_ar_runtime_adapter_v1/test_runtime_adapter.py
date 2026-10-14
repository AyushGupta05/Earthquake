"""Cold invented module/temp-FS tests, no actual vendor/models/scientific inputs."""
import base64,copy,hashlib,importlib.util,os,sys,tempfile,types,unittest
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'reference'))
import secure_io as io,source_binding as sb,fixtures as fx
COUNTS=dict(processor=33,gaussian=34,native=22,reference=13,kernel=20,auditor=35,original_auditor=31)
ENV=dict(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')

def profile(root,bodies,count=None,plain=False):
 bodies=dict(bodies);count=count or len(bodies)+1
 for i in range(count-len(bodies)-1):bodies['doc_%03d.txt'%i]=b'Invented source-only proof\n'
 files={n:io.pin(v)for n,v in bodies.items()};bodies['MANIFEST.json']=io.canonical(files if plain else dict(files=files))
 for n,b in bodies.items():fx.put(root/n,b)
 return dict(directory=str(root),files={n:io.pin(b)for n,b in bodies.items()},manifest=dict(path=str(root/'MANIFEST.json'),pin=io.pin(bodies['MANIFEST.json']),mode=0o400),upload_manifest=None)

def sources(root):
 np=b'import numpy as np\n';torch=np+b'import torch\n';math=np+b'def need(x,why):\n    if not x:raise ValueError(why)\narray=need\nsummaries=need\n'
 old={'math_core.py':math,'transport.py':np+b'from math_core import need\n','packet_digest.py':np+b'from math_core import need\n','packet.py':np+b'from math_core import need,array,summaries\n','metrics.py':np+b'from math_core import need\n','fixtures.py':b'"""Unexecuted invented fixture."""\n','auditor.py':np+b'import math_core as core\nimport packet as pkt\nimport transport as tx\nimport packet_digest\nimport metrics\n'}
 ref={'proper_core.py':math,'ar_core.py':np+b'import proper_core as p\n','L_PROTOCOL.md':b'fixed invented L protocol\n'}
 native={'marked_native.py':np,'packet_io.py':np+b'import marked_native as m\n'};gaussian={'gaussian_operator.py':torch,'reference_core.py':np};kernel={'kernel.py':torch}
 proc={'numeric_state.py':np,'l_math.py':torch,'descriptive.py':np,'processor.py':torch+b'import numeric_state as ns\nimport l_math as lm\nimport descriptive as desc\n','reference/PROTOCOL.md':ref['L_PROTOCOL.md']}
 for dest,d,n in [('gaussian_operator.py',gaussian,'gaussian_operator.py'),('reference_core.py',gaussian,'reference_core.py'),('marked_native.py',native,'marked_native.py'),('native_packet_io.py',native,'packet_io.py'),('level_kernel.py',kernel,'kernel.py'),('proper_core.py',ref,'proper_core.py'),('ar_core.py',ref,'ar_core.py')]:proc['reference/'+dest]=d[n]
 audit=dict(old,**ref);audit['l_auditor.py']=np+b'import auditor as old\nimport math_core as core\nimport ar_core as ar\nimport packet as pkt\nimport packet_digest\nimport transport as tx\nimport metrics\n'
 groups=dict(native=native,gaussian=gaussian,reference=ref,kernel=kernel,processor=proc,auditor=audit,original_auditor=old,adapter={'runtime_adapter.py':(HERE/'runtime_adapter.py').read_bytes()},executor={'control.py':b'"""Unexecuted invented controller."""\n'},v6={n:(HERE/'reference'/n).read_bytes()for n in('secure_io.py','source_binding.py','vendor_inventory.py','generated_source.py','metadata_finder.py')})
 specs={g:profile(root/g,b,COUNTS.get(g),plain=g=='auditor')for g,b in groups.items()}
 roles={k:copy.deepcopy(specs[v]['manifest'])for k,v in dict(operator='gaussian',native_validator='native',reference='reference',kernel='kernel',processor='processor').items()}
 for role,name in [('protocol','reference/PROTOCOL.md'),('numeric_state','numeric_state.py')]:roles[role]=dict(path=specs['processor']['directory']+'/'+name,pin=specs['processor']['files'][name],mode=0o400)
 original={k:copy.deepcopy(roles[k]['pin'])if k in('operator','native_validator')else io.pin(b'original '+k.encode())for k in('operator','native_validator','reference','processor','protocol')}
 return specs,roles,original

class ColdLoader(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.specs,self.roles,self.old=sources(self.root/'sources')
  raw={n+'.py':Path(self.specs['v6']['directory'],n+'.py').read_bytes()for n in('secure_io','vendor_inventory','generated_source','metadata_finder','source_binding')}
  group=sb.load_group(self.specs['v6'],raw,tuple(n[:-3]for n in raw),'test_v6_'+self.root.name.replace('-','_'));self.io=group['secure_io'];self.sb=group['source_binding']
  self.a=sb.load_group(self.specs['adapter'],{'runtime_adapter.py':(HERE/'runtime_adapter.py').read_bytes()},('runtime_adapter',),'test_adapter_'+self.root.name.replace('-','_'))['runtime_adapter']
  generated,inventory,_=fx.generated(self.root/'fallback');self.inventory=inventory;self.prefix=self.root/'prefix';(self.prefix/'venv').mkdir(parents=True)
  self.runtime=dict(directory=str(self.prefix),manifest=fx.put(self.root/'manifest',io.canonical(dict(files={}))),critical={},regular_mode=0o444,python=sys.executable,vendor_inventory=inventory,generated_source=generated,metadata_finder=fx.metadata(inventory),versions=dict(python='.'.join(map(str,sys.version_info[:3])),numpy='invented-numpy',scipy='invented-scipy',torch='invented-torch'))
  self.site=io.json_read(Path(inventory['path']).read_bytes())['roots'][0]
  self.prefix_file('numpy.py',b'__version__="invented-numpy"\n');self.prefix_file('scipy.py',b'__version__="invented-scipy"\n')
  self.vendor('torch.py',b'__version__="invented-torch"\nthreads=0\ndef set_num_threads(n):\n    global threads\n    threads=n\ndef get_num_threads():\n    return threads\nclass Cuda:\n    @staticmethod\n    def is_initialized():\n        return False\ncuda=Cuda()\n');self.vendor('lazy_bound.py',b'VALUE=87\n')
  self.config=dict(sources=self.specs,runtime=self.runtime,role_subjects=self.roles,original_source_pins=self.old);self.runtime_calls=[];self.sb.sysconfig.get_path('stdlib')
 def tearDown(self):self.tmp.cleanup()
 def prefix_file(self,name,body):
  file=fx.put(self.prefix/'venv'/name,body,0o444);doc=io.json_read(Path(self.runtime['manifest']['path']).read_bytes());doc['files']['venv/'+name]=file['pin'];self.runtime['manifest']=fx.put(Path(self.runtime['manifest']['path']),io.canonical(doc))
 def vendor(self,name,body):
  doc=io.json_read(Path(self.inventory['path']).read_bytes());rid=next(iter(doc['records']));record=doc['records'][rid];file=fx.put(Path(self.site)/name,body,0o644);digest=base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip('=')
  doc['records'][rid]=fx.put(Path(record['path']),Path(record['path']).read_bytes()+(name+',sha256='+digest+','+str(len(body))+'\n').encode(),record['mode']);doc['files'][file['path']]=dict(file['pin'],mode=file['mode'],record_id=rid,record_path=name);self.inventory=fx.put(Path(self.inventory['path']),io.canonical(doc));self.runtime['vendor_inventory']=self.inventory
 def fixture_runtime(self,spec,check):
  # Only the10112-member/runtime-interpreter proof is mocked for invented files.
  # Real source inventories/load_group/vendor_guard execute unchanged. ROOT tests real runtime separately.
  self.assertIs(spec,self.runtime);self.runtime_calls.append('verified');check()
 @contextmanager
 def cold(self,aliases=None):
  previous=[str(self.prefix/'venv')]
  with patch.object(self.sb,'runtime',side_effect=self.fixture_runtime),patch.object(self.sb,'interpreter_check'),patch.dict(sys.modules,dict({'sys':sys},**(aliases or{})),clear=True),patch.object(sys,'path',previous),patch.dict(os.environ,ENV):yield previous
 def load(self,mode='producer',pin=None,check=lambda:None):return self.a.load(mode,self.config,expected_config_pin=io.pin(io.canonical(self.config))if pin is None else pin,io=self.io,sb=self.sb,check=check,prefix='eew_l_invented')
 def test_cold_producer_and_lazy_guard(self):
  with self.cold()as oldpath:
   self.assertNotIn(self.site,sys.path)
   with self.load()as v:
    self.assertEqual(set(v['groups']),{'native','gaussian','reference','kernel','processor'});self.assertEqual(__import__('lazy_bound').VALUE,87);p=v['groups']['processor'];self.assertEqual(p['processor'].torch.get_num_threads(),1);self.assertIs(p['processor'].ns,p['numeric_state']);self.assertEqual(v['source_pins']['operator'],self.old['operator']);self.assertEqual(self.runtime_calls,['verified'])
   self.assertIs(sys.path,oldpath)
 def test_cold_independent_no_producer(self):
  with self.cold():
   with self.load('independent')as v:
    self.assertEqual(set(v['groups']),{'native','auditor'});self.assertNotIn('torch',sys.modules);self.assertNotIn('torch',v['observed_versions']);a=v['groups']['auditor'];self.assertIs(a['l_auditor'].ar,a['ar_core']);self.assertIs(a['ar_core'].p,a['proper_core']);self.assertFalse(any('_processor_'in n or'_gaussian_'in n or'_kernel_'in n for n in sys.modules))
 def test_aliases_restored(self):
  sentinel=types.ModuleType('marked_native')
  with self.cold({'marked_native':sentinel}):
   with self.load()as v:self.assertIs(sys.modules['marked_native'],sentinel);self.assertIsNot(v['groups']['native']['packet_io'].m,sentinel)
 def test_lazy_unlisted_rejected(self):
  fx.put(Path(self.site)/'unlisted.py',b'raise AssertionError("no execution")\n')
  with self.cold():
   with self.load():
    with self.assertRaisesRegex(ValueError,'import_outside_verified_runtime'):__import__('unlisted')
 def test_config_pin(self):
  with self.cold():
   with self.assertRaisesRegex(ValueError,'adapter_config_pin'):
    with self.load(pin=io.pin(b'unbound')):pass
   self.assertNotIn('numpy',sys.modules)
 def test_extra_file(self):
  fx.put(Path(self.specs['processor']['directory'])/'extra.py',b'raise AssertionError()\n')
  with self.cold():
   with self.assertRaisesRegex(ValueError,'source_closed'):
    with self.load():pass
  self.assertEqual(self.runtime_calls,[])
 def test_wrong_bytes(self):
  fx.put(Path(self.specs['kernel']['directory'])/'kernel.py',b'bad=1\n')
  with self.cold():
   with self.assertRaises(ValueError):
    with self.load():pass
   self.assertNotIn('torch',sys.modules)
 def test_wrong_mode(self):
  Path(self.specs['native']['directory'],'marked_native.py').chmod(0o600)
  with self.cold():
   with self.assertRaises(ValueError):
    with self.load():pass
 def test_symlink_directory(self):
  alias=self.root/'alias';alias.symlink_to(self.specs['native']['directory'],target_is_directory=True);self.specs['native']['directory']=str(alias)
  with self.cold():
   with self.assertRaisesRegex(ValueError,'canonical_source_directory'):
    with self.load():pass
 def test_external_role_subject(self):
  self.roles['protocol']=fx.put(self.root/'external',b'fixed invented L protocol\n')
  with self.cold():
   with self.assertRaisesRegex(ValueError,'subject_outside'):
    with self.load():pass
 def test_manifest_role_not_module(self):
  s=self.specs['gaussian'];self.roles['operator']=dict(path=s['directory']+'/gaussian_operator.py',pin=s['files']['gaussian_operator.py'],mode=0o400)
  with self.cold():
   with self.assertRaisesRegex(ValueError,'role_manifest_subject'):
    with self.load():pass
 def test_historical_pin_preserved(self):
  self.old['operator']=io.pin(b'new false old pin')
  with self.cold():
   with self.assertRaisesRegex(ValueError,'unchanged_original_role'):
    with self.load():pass
 def test_cross_copy_mismatch(self):
  s=self.specs['processor'];b={n:Path(s['directory'],n).read_bytes()for n in s['files']if n!='MANIFEST.json'};b['reference/level_kernel.py']+=b'\nDIFFERENT=1\n';self.specs['processor']=profile(Path(s['directory']),b,33);self.roles['processor']=self.specs['processor']['manifest']
  with self.cold():
   with self.assertRaisesRegex(ValueError,'frozen_copy_mismatch'):
    with self.load():pass
 def test_manifest_cannot_omit_code(self):
  s=self.specs['kernel'];m=io.json_read(Path(s['manifest']['path']).read_bytes());del m['files']['kernel.py'];file=fx.put(Path(s['manifest']['path']),io.canonical(m));s['manifest']=file;s['files']['MANIFEST.json']=file['pin'];self.roles['kernel']=file
  with self.cold():
   with self.assertRaisesRegex(ValueError,'unmanifested_source'):
    with self.load():pass
 def test_protocol_mismatch_with_positive_file_pins(self):
  s=self.specs['reference'];b={n:Path(s['directory'],n).read_bytes()for n in s['files']if n!='MANIFEST.json'};b['L_PROTOCOL.md']=b'different fixed protocol\n';self.specs['reference']=profile(Path(s['directory']),b,13);self.roles['reference']=self.specs['reference']['manifest']
  with self.cold():
   with self.assertRaisesRegex(ValueError,'protocol_bytes'):
    with self.load():pass
 def test_group_import_failure_restores_aliases(self):
  s=self.specs['processor'];b={n:Path(s['directory'],n).read_bytes()for n in s['files']if n!='MANIFEST.json'};b['processor.py']+=b'raise RuntimeError("invented import failure")\n';self.specs['processor']=profile(Path(s['directory']),b,33);self.roles['processor']=self.specs['processor']['manifest'];sentinel=types.ModuleType('numeric_state')
  with self.cold({'numeric_state':sentinel})as oldpath:
   with self.assertRaisesRegex(RuntimeError,'invented import failure'):
    with self.load():pass
   self.assertIs(sys.modules['numeric_state'],sentinel);self.assertIs(sys.path,oldpath)
 def test_unsupported_profile(self):
  self.specs['ambient']=self.specs['native']
  with self.cold():
   with self.assertRaisesRegex(ValueError,'source_groups'):
    with self.load():pass
 def test_injected_helper_identity(self):
  with self.cold(),patch.object(self.sb.vi,'io',io):
   with self.assertRaisesRegex(ValueError,'injected_dependency_identity'):
    with self.load():pass
 def test_version_mismatch(self):
  self.runtime['versions']['numpy']='wrong'
  with self.cold():
   with self.assertRaisesRegex(ValueError,'vendor_versions'):
    with self.load():pass
 def test_science_failure_guard_cleanup(self):
  with self.cold()as oldpath:
   with self.assertRaisesRegex(RuntimeError,'invented science'):
    with self.load():raise RuntimeError('invented science')
   self.assertIs(sys.path,oldpath)
 def test_late_check(self):
  late=[False]
  def check():
   if late[0]:raise ValueError('invented deadline')
  with self.cold()as oldpath:
   with self.assertRaisesRegex(ValueError,'invented deadline'):
    with self.load(check=check):late[0]=True
   self.assertIs(sys.path,oldpath)
 def test_dependency_mutation(self):
  with self.cold():
   with self.assertRaisesRegex(ValueError,'processor_alias'):
    with self.load()as v:v['groups']['processor']['processor'].ns=object()
 def test_independent_preloaded_producer_rejected(self):
  m=types.ModuleType('invented');m.__file__=self.specs['processor']['directory']+'/processor.py'
  with self.cold({'invented':m}):
   with self.assertRaisesRegex(ValueError,'independent_producer_import'):
    with self.load('independent'):pass
 def test_independent_late_producer_rejected(self):
  with self.cold():
   with self.assertRaisesRegex(ValueError,'independent_producer_import'):
    with self.load('independent'):
     m=types.ModuleType('invented');m.__file__=self.specs['processor']['directory']+'/processor.py';sys.modules['invented']=m
 def test_cpu_env_no_silent_repair(self):
  with self.cold(),patch.dict(os.environ,CUDA_VISIBLE_DEVICES='0'):
   with self.assertRaisesRegex(ValueError,'cpu_environment'):
    with self.load():pass
   self.assertEqual(os.environ['CUDA_VISIBLE_DEVICES'],'0')
 def test_no_retry(self):
  with self.cold():
   with self.assertRaises(ValueError):
    with self.load(pin=io.pin(b'wrong')):pass
   with self.assertRaisesRegex(ValueError,'runtime_adapter_once'):
    with self.load():pass
 def test_preloaded_vendor_rejected(self):
  with self.cold({'numpy':types.ModuleType('numpy')}):
   with self.assertRaisesRegex(ValueError,'preloaded_vendor'):
    with self.load():pass
 def test_no_actual_vendors(self):self.assertFalse({'numpy','scipy','torch'}&set(sys.modules))

if __name__=='__main__':unittest.main()
