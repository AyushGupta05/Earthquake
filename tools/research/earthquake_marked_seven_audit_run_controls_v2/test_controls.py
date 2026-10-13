"""Invented filesystem/manager metadata only; never root/AWS inputs or models."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import custody as c
import runner

CANONICAL_TEMP=str(Path(tempfile.gettempdir()).resolve())

class IO:
    directory=staticmethod(runner.directory)
    file_sync=staticmethod(os.fsync)
    @staticmethod
    def read_at(fd,name,cap,mode,expected=None):
        f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            s=os.fstat(f);c.need(stat.S_ISREG(s.st_mode)and stat.S_IMODE(s.st_mode)==mode and s.st_nlink==1 and s.st_size<=cap,'fixture_file');raw=os.read(f,cap+1);c.need(len(raw)==s.st_size,'fixture_size')
        finally:os.close(f)
        if expected is not None:c.need(c.pin(raw)==expected,'fixture_pin')
        return raw
    @staticmethod
    def read_file(spec):
        raw=runner.read_private(spec['path'],16*1024*1024);c.need(c.pin(raw)==spec['pin']and spec['mode']==0o400,'fixture_spec');return raw

class J:
    def __init__(self,path):self.path=Path(path)
    def inventory(self):return {p.name:(sum(q.stat().st_size for q in p.iterdir()),0,0,len(list(p.iterdir())))for p in self.path.iterdir()if p.is_dir()}

class Fixture:
    def __init__(self,index=0):
        self.temp=tempfile.TemporaryDirectory(dir=CANONICAL_TEMP);self.base=Path(self.temp.name);os.chmod(self.base,0o700);self.store=self.base/'store';self.store.mkdir(mode=0o700);self.root=self.store/('stage_%02d'%index);self.root.mkdir(mode=0o700);self.index=index;self.io=IO();self.j=J(self.store);self.cfg=dict(audit_id='invented-v2',study='invented-study',wrapper_binding_sha256='1'*64,whole_begin=0.,store_directory=str(self.store));self.cp=c.pin(c.plain(self.cfg));self.unit='eew-marked-invented-v2-%02d.service'%index
        self.bundle=dict(stages=[{}for _ in range(14)]);self.predictions=[dict(source={'invented_value':i})for i in range(66)]
        source=self.base/'score.private.json';source.write_bytes(c.plain(dict(predictions=self.predictions)));source.chmod(0o400);self.source_spec=dict(path=str(source),pin=c.pin(source.read_bytes()),mode=0o400)
        if index<6:self.bundle['stages'][2*index+2]={'result.json':self.source_spec}
        self.bundlepath=self.base/'bundle.private.json';self.bundlepath.write_bytes(c.plain(self.bundle));self.bundlepath.chmod(0o400);self.bs=dict(path=str(self.bundlepath),pin=c.pin(self.bundlepath.read_bytes()),mode=0o400)
        self.dispatch=dict(schema='marked-seven-audit-request-v1',config_pin=self.cp,stage=dict(index=index,unit=self.unit,source_seconds=900,manager_seconds=960,limits=dict(memory=2147483648,swap=0,tasks=64,cpu_weight=10,threads=1,cuda_hidden=True,kill_mode='control-group',stop_seconds=5)),dispatch_begin=0.,previous=[],bundle_spec=self.bs)
        self.claim=dict(schema='marked-sixfit-audit-wrapper-claim-v1',study=self.cfg['study'],stage=index,seed=c.PAIRS[index][0]if index<6 else None,arm=c.PAIRS[index][1]if index<6 else None,inputs_sha256='2'*64,binding_sha256='1'*64,whole_begin=0.)
        advance=dict(pass_all=False,checks=[],additional=[])
        if index<6:
            self.report=dict(schema='marked-sixfit-independent-audit-v1',status='pass',seed=c.PAIRS[index][0],arm=c.PAIRS[index][1],checked=66,records=[dict(invented_record=i)for i in range(66)],advance=advance)
            records=[dict(position=i,status='pass',fresh=self.report['records'][i],source_sha256=c.pin(c.plain(p['source']))['sha256'])for i,p in enumerate(self.predictions)]
        else:self.report=dict(schema='marked-sixfit-independent-aggregate-v1',status='pass',checked=396,fits=[{}]*6,stronger=[{}]*8,advance=advance);records=[self.report]
        self.values={'bootstrap.json':dict(schema='marked-seven-audit-launch-v1',request=self.dispatch,config=self.cfg,expected_config_pin=self.cp),'dispatch.json':self.dispatch,'claim.json':self.claim,'raw_report_000.json':self.report}
        self.values.update({'record_%03d.json'%i:v for i,v in enumerate(records)})
        retained=sum(len(c.plain(v))for v in records)+len(c.plain(self.report));rp=c.pin(c.plain(self.report));claimpin=c.pin(c.plain(self.claim))
        self.returned=dict(schema='marked-sixfit-audit-wrapper-return-v1',status='complete',stage=index,seed=self.claim['seed'],arm=self.claim['arm'],binding_sha256='1'*64,input_sha256='2'*64,report_pin=rp,claim_sha256=claimpin['sha256'],retained_count=len(records)+1,attempted_count=len(records)+1,retained_bytes=retained,attempted_bytes=retained,advance=advance)
        child=dict(schema='marked-seven-audit-child-report-v1',status='complete',stage=index,config_pin=self.cp,request_pin=c.pin(c.plain(self.dispatch)),return_pin=c.pin(c.plain(self.returned)),report_pin=rp,claim_pin=claimpin,within_source=True)
        self.actual=dict(schema='marked-seven-audit-manager-return-v1',status='complete',stage=index,unit=self.unit,config_pin=self.cp,cleanup_verified=True,child_report_pin=c.pin(c.plain(child)),return_pin=child['return_pin'],report_pin=rp,errors=[],no_retry=True)
        clip=dict(retained_hex='',retained_pin=c.pin(b''),truncated=False);meta=dict(original_bytes=0,original_sha256=c.pin(b'')['sha256'],retained_bytes=0,truncated=False,complete_observation=True)
        self.post=dict(unit=self.unit,result='success',active_state='inactive',control_group='')
        self.values.update({'return.json':self.returned,'child_report.json':child,'closed.json':self.actual,'post.json':self.post,'manager_return.json':dict(code=0,timeout=False,streams_complete=True,exception=None,stdout=clip,stderr=copy.deepcopy(clip),stream_custody=dict(stdout=meta,stderr=copy.deepcopy(meta)))})
        self.write()
    def write(self):
        for n,v in self.values.items():
            p=self.root/n
            if p.exists():p.chmod(0o600)
            p.write_bytes(c.plain(v));p.chmod(0o400)
    def verify(self,observe=None):return c.complete_closure(self.cfg,self.index,self.actual,self.j,self.io,observe if observe is not None else lambda u,t:dict(self.post),bundle_spec=self.bs)
    def close(self):self.temp.cleanup()

class Tests(unittest.TestCase):
    def fixture(self,index=0):f=Fixture(index);self.addCleanup(f.close);return f
    def test_fit_complete_exact75(self):f=self.fixture();self.assertEqual(len(f.verify()['inventory']),75)
    def test_aggregate_complete_negative_gate10(self):f=self.fixture(6);self.assertEqual(len(f.verify()['inventory']),10);self.assertFalse(f.report['advance']['pass_all'])
    def test_provisional_closed_differs_actual_return(self):
        f=self.fixture();f.actual=dict(f.actual,errors=['late_finalization'],status='incomplete')
        with self.assertRaisesRegex(ValueError,'actual_return'):f.verify()
    def test_wrong_closed_bytes(self):
        f=self.fixture();f.values['closed.json']=dict(f.actual,status='incomplete');f.write()
        with self.assertRaisesRegex(ValueError,'final_return_agreement'):f.verify()
    def test_unknown_late_member(self):
        f=self.fixture();p=f.root/'late_or_failed.json';p.write_bytes(b'{}');p.chmod(0o400)
        with self.assertRaisesRegex(ValueError,'exact_success_inventory'):f.verify()
    def test_fresh_cgroup_nonempty(self):
        f=self.fixture()
        with self.assertRaisesRegex(ValueError,'fresh_owned_cleanup'):f.verify(lambda u,t:dict(f.post,control_group='/invented'))
    def test_persisted_post_differs_live(self):
        f=self.fixture();f.values['post.json']=dict(f.post,result='failure');f.write()
        with self.assertRaisesRegex(ValueError,'fresh_owned_cleanup'):f.verify()
    def test_manager_truncated(self):
        f=self.fixture();f.values['manager_return.json']['stdout']['truncated']=True;f.write()
        with self.assertRaisesRegex(ValueError,'raw_stream_custody'):f.verify()
    def test_manager_timeout(self):
        f=self.fixture();f.values['manager_return.json']['timeout']=True;f.write()
        with self.assertRaisesRegex(ValueError,'raw_manager_complete'):f.verify()
    def test_originalstream_wrong_hash(self):
        f=self.fixture();f.values['manager_return.json']['stream_custody']['stderr']['original_sha256']='0'*64;f.write()
        with self.assertRaisesRegex(ValueError,'raw_stream_custody'):f.verify()
    def test_manager_boolean_zero(self):
        f=self.fixture();f.values['manager_return.json']['code']=False;f.write()
        with self.assertRaisesRegex(ValueError,'integer'):f.verify()
    def test_reordered_callback(self):
        f=self.fixture();f.values['record_021.json']['fresh']=dict(invented_record=20);f.write()
        with self.assertRaisesRegex(ValueError,'record_order_source'):f.verify()
    def test_wrong_source_callback_hash(self):
        f=self.fixture();f.values['record_000.json']['source_sha256']='0'*64;f.write()
        with self.assertRaisesRegex(ValueError,'record_order_source'):f.verify()
    def test_aggregate_record_must_equal_rawreport(self):
        f=self.fixture(6);f.values['record_000.json']=dict(f.report,status='fail');f.write()
        with self.assertRaisesRegex(ValueError,'aggregate_report'):f.verify()
    def test_child_hash_substitution(self):
        f=self.fixture();f.values['child_report.json']['request_pin']={'bytes':1,'sha256':'0'*64};f.write()
        with self.assertRaisesRegex(ValueError,'child_custody'):f.verify()
    def test_count_bool_denied(self):
        f=self.fixture();f.values['return.json']['retained_count']=True;f.write();f.values['child_report.json']['return_pin']=c.pin(c.plain(f.values['return.json']));f.actual['return_pin']=f.values['child_report.json']['return_pin'];f.actual['child_report_pin']=c.pin(c.plain(f.values['child_report.json']));f.write()
        with self.assertRaisesRegex(ValueError,'integer'):f.verify()
    def test_durable_no_overwrite_and_mode(self):
        with tempfile.TemporaryDirectory(dir=CANONICAL_TEMP)as d:
            spec=c.durable(IO(),d,'stage_00.private.json',{'invented':1});self.assertEqual(IO.read_file(spec),b'{"invented":1}');self.assertEqual(Path(spec['path']).stat().st_mode&0o777,0o400)
            with self.assertRaises(FileExistsError):c.durable(IO(),d,'stage_00.private.json',{'invented':2})
    def test_durable_nonfinite_fails_before_write(self):
        with tempfile.TemporaryDirectory(dir=CANONICAL_TEMP)as d:
            with self.assertRaises(ValueError):c.durable(IO(),d,'stage_00.private.json',{'invented':float('nan')})
            self.assertEqual(os.listdir(d),[])
    def test_durable_oversize_before_write(self):
        with tempfile.TemporaryDirectory(dir=CANONICAL_TEMP)as d:
            with self.assertRaisesRegex(ValueError,'metadata_cap'):c.durable(IO(),d,'stage_00.private.json',{'invented':'x'*100},cap=10)
            self.assertEqual(os.listdir(d),[])
    def test_local_intent_exclusive(self):
        with tempfile.TemporaryDirectory(dir=CANONICAL_TEMP)as d:
            p=str(Path(d)/'intent.private.json');runner.exclusive(p,b'{}')
            with self.assertRaises(FileExistsError):runner.exclusive(p,b'new')
            self.assertEqual(runner.read_private(p),b'{}')
    def test_local_symlink_read_denied(self):
        with tempfile.TemporaryDirectory(dir=CANONICAL_TEMP)as d:
            p=Path(d)/'real';p.write_bytes(b'{}');p.chmod(0o400);(Path(d)/'link').symlink_to(p)
            with self.assertRaises(OSError):runner.read_private(str(Path(d)/'link'))
    def test_bounded_transport_retains_observed_hash(self):
        answer=runner.transport([sys.executable,'-c','import sys;sys.stdout.buffer.write(b"x"*1200000)'],b'{}',timeout=5);s=answer['streams']['stdout'];self.assertEqual(s['original_bytes'],1200000);self.assertEqual(s['original_sha256'],hashlib.sha256(b'x'*1200000).hexdigest());self.assertTrue(s['truncated']);self.assertTrue(s['complete_observation']);self.assertEqual(s['retained_pin']['bytes'],runner.CAP)
    def test_transport_timeout_no_retry(self):
        answer=runner.transport([sys.executable,'-c','import time;time.sleep(1)'],b'{}',timeout=.01);self.assertTrue(answer['timeout']);self.assertTrue(answer['no_retry'])
    def test_large_output_receipt_private_readback(self):
        with tempfile.TemporaryDirectory(dir=CANONICAL_TEMP)as d:
            p=str(Path(d)/'transport.private.json');raw=b'x'*(runner.CAP+1000);runner.exclusive(p,raw);self.assertEqual(runner.read_private(p,5*runner.CAP),raw)
    def test_driver_no_actual_execution_on_import(self):
        t=ast.parse(Path(runner.__file__).read_text());self.assertTrue(any(isinstance(n,ast.If)and '__name__'in ast.dump(n.test)for n in t.body));ast.parse(runner.REMOTE)
    def test_setup_return_requires_actual_outer_success(self):
        with tempfile.TemporaryDirectory(dir=CANONICAL_TEMP)as d:
            p=Path(d)/'prep';q=Path(d)/'runner';p.write_bytes(c.plain(dict(schema='root-marked-seven-audit-control-preparation-v2',status='prepared',no_audit_invoked=True)));q.write_bytes(b'{}');p.chmod(0o400);q.chmod(0o400)
            with self.assertRaisesRegex(ValueError,'preparation_transport'):runner.main(['0',str(p),str(q),str(Path(d)/'out')])
    def test_remote_setup_failure_and_config_python_bind_source(self):
        self.assertIn('setup_failure.private.json',runner.REMOTE);self.assertIn("r['remote_python']==config['runtime']['python']",runner.REMOTE);self.assertIn('preparation_receipt.private.json',runner.REMOTE)
    def test_full_permitted_manager_streams_publish_root_evidence(self):
        f=self.fixture();manager=f.values['manager_return.json']
        for key,count in(('stdout',65536),('stderr',131072)):
            data=b'x'*count;manager[key]={'retained_hex':data.hex(),'retained_pin':c.pin(data),'truncated':False};manager['stream_custody'][key]={'original_bytes':count,'original_sha256':c.pin(data)['sha256'],'retained_bytes':count,'truncated':False,'complete_observation':True}
        f.write();held=f.verify();self.assertGreater(len(c.plain(held)),262144);evidence=f.base/'evidence';evidence.mkdir(mode=0o700);spec=c.durable(IO(),str(evidence),'stage_00.private.json',held);self.assertLess(spec['pin']['bytes'],1048576);self.assertEqual(c.schema(IO.read_file(spec)),held)
    def test_eof_before_process_exit_uses_remaining_deadline(self):
        answer=runner.transport([sys.executable,'-c','import os,time;os.close(1);os.close(2);time.sleep(5.15)'],b'{}',timeout=8);self.assertEqual(answer['code'],0);self.assertFalse(answer['timeout']);self.assertGreater(answer['elapsed_s'],5.);self.assertTrue(all(s['complete_observation']for s in answer['streams'].values()))
    def test_failed_before_link_reserved_destination_cannot_retry(self):
        with tempfile.TemporaryDirectory(dir=CANONICAL_TEMP)as d:
            with patch.object(IO,'file_sync',side_effect=OSError('invented_sync_failure')):
                with self.assertRaisesRegex(OSError,'invented_sync_failure'):c.durable(IO(),d,'stage_00.private.json',{'first':1})
            pending=Path(d)/'.tmp-stage_00.private.json';self.assertTrue(pending.exists());self.assertEqual(pending.read_bytes(),b'{"first":1}');self.assertEqual(pending.stat().st_mode&0o777,0o400);self.assertEqual(pending.stat().st_nlink,1)
            with self.assertRaises(FileExistsError):c.durable(IO(),d,'stage_00.private.json',{'second':2})
            self.assertFalse((Path(d)/'stage_00.private.json').exists());self.assertEqual(os.listdir(d),['.tmp-stage_00.private.json']);self.assertEqual(pending.read_bytes(),b'{"first":1}')
    def test_broken_buffered_stdin_close_still_drains_and_reaps(self):
        class BrokenInput:
            def write(self,v):return len(v)
            def flush(self):raise BrokenPipeError('invented_remote_closed_stdin')
            def close(self):raise BrokenPipeError('invented_close_reflush')
        class Process:
            def __init__(self):
                self.stdin=BrokenInput();self.waited=0;self.killed=0
                out,wout=os.pipe();err,werr=os.pipe();os.write(werr,b'invented_auth_failure');os.close(wout);os.close(werr);self.stdout=os.fdopen(out,'rb');self.stderr=os.fdopen(err,'rb')
            def wait(self,timeout):self.waited+=1;return 255
            def kill(self):self.killed+=1
        p=Process()
        with patch.object(runner.subprocess,'Popen',return_value=p):answer=runner.transport(['invented'],b'{}',timeout=1)
        self.assertEqual(answer['code'],255);self.assertEqual(answer['exception'],'BrokenPipeError');self.assertEqual(bytes.fromhex(answer['streams']['stderr']['retained_hex']),b'invented_auth_failure');self.assertEqual(answer['streams']['stderr']['original_sha256'],hashlib.sha256(b'invented_auth_failure').hexdigest());self.assertTrue(answer['streams']['stderr']['complete_observation']);self.assertGreater(p.waited,0);self.assertEqual(p.killed,0)
    def test_duplicate_json_denied(self):
        with self.assertRaisesRegex(ValueError,'duplicate_key'):c.schema(b'{"a":1,"a":2}')

if __name__=='__main__':unittest.main()
