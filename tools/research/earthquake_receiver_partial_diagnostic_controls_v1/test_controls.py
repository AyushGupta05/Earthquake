"""AST-only authored definitions and synthetic custody; no actual inputs/jobs."""
import ast
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
SOURCE=(ROOT/'wrapper.py').read_text();TREE=ast.parse(SOURCE)
EMBEDDED={n.targets[0].id:ast.literal_eval(n.value) for n in TREE.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('child','remote')}

def primitive(domain,out):
    tree=TREE if domain=='parent' else ast.parse(EMBEDDED[domain]);name='private_put' if domain=='parent' else 'put'
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    g={'os':os,'json':json,'out':out};exec(compile(ast.Module(body=[node],type_ignores=[]),'<synthetic-function-only>','exec'),g)
    return (lambda name,value,cap=16777216:g['private_put'](out,name,value,cap)) if domain=='parent' else g['put']

class CustodyTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.out=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_AST_extraction_no_top_level_import(self):
        for name,text in EMBEDDED.items():compile(text,name,'exec');self.assertEqual(text,(ROOT/(name+'.py')).read_text())
        self.assertEqual(set(EMBEDDED),{'child','remote'})
        with patch.object(Path,'read_bytes',side_effect=AssertionError('actual read')),patch.object(subprocess,'run',side_effect=AssertionError('network/job')):
            for domain in ('parent','child','remote'):self.assertTrue(callable(primitive(domain,self.out)))
    def test_all_three_puts_strict_JSON_private(self):
        for domain in ('parent','child','remote'):
            primitive(domain,self.out)(domain+'.private.json',{'invented':[1,None,True]});p=self.out/(domain+'.private.json')
            self.assertEqual(p.stat().st_mode&0o777,0o400);self.assertEqual(json.loads(p.read_bytes()),{'invented':[1,None,True]})
    def test_no_overwrite_preserves_bytes(self):
        for domain in ('parent','child','remote'):
            put=primitive(domain,self.out);name=domain+'.private.json';put(name,{'value':1});before=(self.out/name).read_bytes()
            with self.assertRaises(FileExistsError):put(name,{'value':2})
            self.assertEqual((self.out/name).read_bytes(),before)
    def test_nonfinite_nested_before_any_write(self):
        for domain in ('parent','child','remote'):
            for value in (math.nan,math.inf,-math.inf):
                with self.assertRaises(ValueError):primitive(domain,self.out)(domain+'.private.json',{'nested':[value]})
                self.assertFalse((self.out/(domain+'.private.json')).exists())
    def test_byte_cap_before_any_write(self):
        for domain in ('parent','child','remote'):
            with self.assertRaisesRegex(ValueError,'payload_cap'):primitive(domain,self.out)(domain+'.private.json',{'x':'é'*10},cap=16)
            self.assertFalse((self.out/(domain+'.private.json')).exists())
    def test_invalid_cap_and_name_before_creation(self):
        for domain in ('parent','child','remote'):
            for cap in (True,0,-1,math.inf,math.nan,16777217):
                with self.assertRaises(ValueError):primitive(domain,self.out)(domain+'.private.json',{},cap=cap)
            for name in ('','..','.','../elsewhere','nested/file','nested\\file',None):
                with self.assertRaises(ValueError):primitive(domain,self.out)(name,{})
        self.assertEqual(list(self.out.iterdir()),[])
    def test_file_then_directory_fsync_private_before_flush(self):
        original=os.fsync;seen=[]
        def fsync(fd):
            info=os.fstat(fd);seen.append('dir' if stat.S_ISDIR(info.st_mode) else 'file')
            if stat.S_ISREG(info.st_mode):self.assertEqual(info.st_mode&0o777,0o400)
            return original(fd)
        for domain in ('parent','child','remote'):
            seen.clear()
            with patch.object(os,'fsync',side_effect=fsync):primitive(domain,self.out)(domain+'.private.json',{})
            self.assertEqual(seen,['file','dir'])
    def test_symlink_target_and_directory_denied(self):
        target=self.out/'target';target.write_bytes(b'preserve');link=self.out/'alias';link.symlink_to(target)
        for domain in ('parent','child','remote'):
            with self.assertRaises(FileExistsError):primitive(domain,self.out)('alias',{})
        self.assertEqual(target.read_bytes(),b'preserve');real=self.out/'real';real.mkdir();linked=self.out/'linked';linked.symlink_to(real,target_is_directory=True)
        for domain in ('parent','child','remote'):
            with self.assertRaises(OSError):primitive(domain,linked)('new.private.json',{})
        self.assertEqual(list(real.iterdir()),[])
    def test_umask_cannot_change_private_mode(self):
        for domain in ('parent','child','remote'):
            mask=os.umask(0o777)
            try:primitive(domain,self.out)(domain+'.private.json',{})
            finally:os.umask(mask)
            self.assertEqual((self.out/(domain+'.private.json')).stat().st_mode&0o777,0o400)
    def test_failed_fsync_preserves_private_partial_no_overwrite(self):
        for domain in ('parent','child','remote'):
            put=primitive(domain,self.out);name=domain+'.private.json'
            with patch.object(os,'fsync',side_effect=OSError('invented-fsync')):
                with self.assertRaises(OSError):put(name,{'invented':1})
            p=self.out/name;self.assertTrue(p.exists());self.assertEqual(p.stat().st_mode&0o777,0o400);before=p.read_bytes()
            with self.assertRaises(FileExistsError):put(name,{'invented':2})
            self.assertEqual(p.read_bytes(),before)
    def remote_tail(self):
        tree=ast.parse(EMBEDDED['remote']);start=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Try))
        return compile(ast.Module(body=tree.body[start:],type_ignores=[]),'<synthetic-manager-tail-only>','exec')
    def globals(self,mock):return dict(out=self.out,put=primitive('remote',self.out),subprocess=mock,unit='invented.service',args=['invented'],json=json,hashlib=hashlib)
    def test_manager_and_stop_timeout_retains_partial_and_return(self):
        primitive('remote',self.out)('score_000.private.json',{'status':'agree'})
        mock=types.SimpleNamespace(TimeoutExpired=subprocess.TimeoutExpired,run=lambda *a,**kw:(_ for _ in ()).throw(subprocess.TimeoutExpired('invented',980,output=b'partial')),check_output=lambda *a,**kw:'Result=timeout\nControlGroup=\nActiveState=failed\n')
        with contextlib.redirect_stdout(io.StringIO()):exec(self.remote_tail(),self.globals(mock))
        manager=json.loads((self.out/'manager_return.private.json').read_bytes());self.assertIsNone(manager['unit_exit']);self.assertTrue(manager['stop_timeout']);self.assertEqual(manager['stdout'],'partial')
        parent=json.loads((self.out/'parent_return.private.json').read_bytes());self.assertIn('score_000.private.json',parent['files']);self.assertIn('manager_timeout.private.json',parent['files'])
    def test_stop_OS_failure_retains_manager(self):
        calls=[0]
        def run(*a,**kw):
            calls[0]+=1
            if calls[0]==1:raise subprocess.TimeoutExpired('invented',980)
            raise OSError('invented-stop')
        mock=types.SimpleNamespace(TimeoutExpired=subprocess.TimeoutExpired,run=run,check_output=lambda *a,**kw:'ControlGroup=\nActiveState=failed\nResult=timeout\n')
        with contextlib.redirect_stdout(io.StringIO()):exec(self.remote_tail(),self.globals(mock))
        receipt=json.loads((self.out/'manager_return.private.json').read_bytes());self.assertEqual(receipt['stop_error_type'],'OSError');self.assertFalse(receipt['stop_timeout'])
    def test_legal_partial_inventory_above200_retained(self):
        put=primitive('remote',self.out)
        for i in range(198):put('score_%03d.private.json'%i,{'index':i})
        for n in ('parent_gate','live_controls','complete_study_rejection','checkpoint_forward','diagnostic_result'):put(n+'.private.json',{})
        mock=types.SimpleNamespace(TimeoutExpired=subprocess.TimeoutExpired,run=lambda *a,**kw:types.SimpleNamespace(returncode=0,stdout=b'ok',stderr=b''),check_output=lambda *a,**kw:'Result=success\nControlGroup=\nActiveState=inactive\n')
        with contextlib.redirect_stdout(io.StringIO()):exec(self.remote_tail(),self.globals(mock))
        receipt=json.loads((self.out/'parent_return.private.json').read_bytes());self.assertEqual(receipt['unit_exit'],0);self.assertEqual(len(receipt['files']),204)
    def test_active_group_refuses_clean_return_retains_manager(self):
        mock=types.SimpleNamespace(TimeoutExpired=subprocess.TimeoutExpired,run=lambda *a,**kw:types.SimpleNamespace(returncode=1,stdout=b'',stderr=b''),check_output=lambda *a,**kw:'Result=exit-code\nControlGroup=/owned\nActiveState=active\n')
        with self.assertRaises(AssertionError),contextlib.redirect_stdout(io.StringIO()):exec(self.remote_tail(),self.globals(mock))
        self.assertTrue((self.out/'manager_return.private.json').exists());self.assertFalse((self.out/'parent_return.private.json').exists())
    def test_transport_timeout_no_retry_without_SSH(self):
        node=next(n for n in TREE.body if isinstance(n,ast.Try));code=compile(ast.Module(body=[node],type_ignores=[]),'<synthetic-transport-only>','exec')
        mock=types.SimpleNamespace(TimeoutExpired=subprocess.TimeoutExpired,run=lambda *a,**kw:(_ for _ in ()).throw(subprocess.TimeoutExpired('invented',1000)))
        g=dict(subprocess=mock,json=json,shlex=__import__('shlex'),remote='invented',child='invented',gate={});exec(code,g)
        self.assertEqual(g['receipt'],dict(ssh_exit=None,reason='transport_timeout',no_retry=True))
    def test_prior_auditor_source_pins_checked_before_import(self):
        tree=ast.parse(EMBEDDED['child']);definitions=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in('bound','sourcecheck')]
        node=next(n for n in tree.body if isinstance(n,ast.Assign)and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='source')
        start=tree.body.index(node);stop=next(i for i in range(start,len(tree.body))if isinstance(tree.body[i],ast.Assert))
        code=compile(ast.Module(body=definitions+tree.body[start:stop+1],type_ignores=[]),'<synthetic-source-pin-boundary-only>','exec')
        names=('eew-train115-receiver-renewal-source-v2-frozen','eew-train115-receiver-renewal-score-audit-source-v2');pins=[]
        for name in names:
            d=self.out/name;d.mkdir();put=primitive('parent',d);raw=b'invented public code\n';p=d/'invented.py';p.write_bytes(raw);p.chmod(0o400)
            z={'invented.py':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}};put('parent_upload_manifest.private.json',z);pins.append(z)
        gate={'fit_proof':{'source_pins':pins[0]},'audit_source_pins':pins[1]}
        g=dict(root=self.out,gate=gate,json=json,hashlib=hashlib);exec(code,g)
        gate['audit_source_pins']={'invented.py':{'bytes':1,'sha256':'0'*64}}
        with self.assertRaises(AssertionError):exec(code,g)
    def test_bound_reader_reads_only_cap_plus_one(self):
        tree=ast.parse(EMBEDDED['child']);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='bound');g=dict(json=json,hashlib=hashlib)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<synthetic-bounded-reader-only>','exec'),g)
        read_sizes=[]
        class Stream(io.BytesIO):
            def read(self,size=-1):read_sizes.append(size);return super().read(size)
        class Fake:
            def is_file(self):return True
            def is_symlink(self):return False
            def stat(self):return types.SimpleNamespace(st_size=1,st_mode=0o400)
            def open(self,*a):return Stream(b'0123456789')
        with self.assertRaises(AssertionError):g['bound'](Fake(),{'bytes':1,'sha256':'0'*64},cap=4)
        self.assertEqual(read_sizes,[5])
    def test_new_directory_parent_fsync_before_launch(self):
        tree=ast.parse(EMBEDDED['remote']);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='make_output_directory');g={'os':os};exec(compile(ast.Module(body=[node],type_ignores=[]),'<synthetic-directory-only>','exec'),g)
        out=self.out/'new';original=os.fsync;seen=[]
        def fsync(fd):
            self.assertTrue(out.is_dir());self.assertEqual(os.fstat(fd).st_ino,self.out.stat().st_ino);seen.append('parent');return original(fd)
        with patch.object(os,'fsync',side_effect=fsync):g['make_output_directory'](out)
        self.assertEqual(seen,['parent']);self.assertEqual(out.stat().st_mode&0o777,0o700)
        with self.assertRaises(FileExistsError):g['make_output_directory'](out)
    def test_new_directory_parent_fsync_failure_blocks_launch(self):
        tree=ast.parse(EMBEDDED['remote']);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='make_output_directory');g={'os':os};exec(compile(ast.Module(body=[node],type_ignores=[]),'<synthetic-directory-only>','exec'),g)
        out=self.out/'new'
        with patch.object(os,'fsync',side_effect=OSError('invented-parent-fsync')):
            with self.assertRaises(OSError):g['make_output_directory'](out)
        self.assertEqual(list(out.iterdir()),[])
    def bindings(self):
        tree=ast.parse(EMBEDDED['child']);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='validate_saved_records');g={'math':math};exec(compile(ast.Module(body=[node],type_ignores=[]),'<synthetic-record-bindings-only>','exec'),g)
        rows=[];records=[]
        for i in range(22):
            c=[0.]*35;c[9:12]=[float(i),10.,20.];c[15 if i%2==0 else 16]=1.;rows.append(dict(mw=4.,group=i,initial=dict(context=c),horizons=[dict(rate=[100,1])for h in(1,3,5)]))
            for h in(1,3,5):records.append(dict(ordinal=i,horizon=h,target=4.,group=i,receiver=list(c[9:12]),family='ENZ'if i%2==0 else'12Z',rate=[100,1]))
        return g['validate_saved_records'],dict(rows=rows),dict(DEV=list(range(22))),records
    def test_full_B_F_and_exact_H_prefix_bindings(self):
        validate,packet,roles,records=self.bindings()
        for arm in('B','F'):validate(packet,roles,dict(arm=arm,predictions=records))
        for n in(0,1,46,66):validate(packet,roles,dict(arm='H',predictions=records[:n]))
    def test_duplicate_subset_and_wrong_order_not_promoted(self):
        validate,packet,roles,records=self.bindings()
        for arm,data in [('B',records[:-1]),('F',records[::-1]),('H',records[1:47]),('H',[records[0]]*46),('H',records+[records[0]])]:
            with self.assertRaises(AssertionError):validate(packet,roles,dict(arm=arm,predictions=data))
    def test_all_saved_identity_fields_and_bool_roles_reject(self):
        validate,packet,roles,records=self.bindings()
        for k,value in [('ordinal',True),('horizon',True),('target',True),('target',5.),('group',True),('group',3),('receiver',[0.,10.,21.]),('receiver',[0.,10.,math.nan]),('family','12Z'),('rate',[True,1]),('rate',[200,2]),('rate',[50,1])]:
            data=[dict(r)for r in records];data[0][k]=value
            with self.assertRaises(AssertionError):validate(packet,roles,dict(arm='B',predictions=data))
    def test_explicit_no_refit_and_deadlines(self):
        child=EMBEDDED['child'];self.assertNotIn('optimizer.step',child);self.assertIn('with torch.no_grad()',child);self.assertIn('time.monotonic()-begin<900',child)
        remote=EMBEDDED['remote'];self.assertIn('RuntimeMaxSec=960',remote);self.assertIn('TimeoutStopSec=5',remote);self.assertIn('KillMode=control-group',remote);self.assertIn('timeout=980',remote)

if __name__=='__main__':unittest.main()
