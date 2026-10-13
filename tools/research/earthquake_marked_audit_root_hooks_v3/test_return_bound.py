"""Invented ROOT metadata boundaries; no scientific/provider/actual streams."""
import os
from pathlib import Path
import tempfile
import sys
import types
import unittest
from unittest.mock import patch
import fixtures

BASE=Path(__file__).parent
CAP=1048576


class ReturnBound(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name).resolve();self.path=self.directory/'stage_00.private.json'
        self.io=fixtures.load('return_bound_secure_io',BASE/'reference/reference/secure_io.py')
        self.hooks=fixtures.load('return_bound_hooks',BASE/'hooks.py')
    def put(self,raw):
        self.path.write_bytes(raw);self.path.chmod(0o400)
    def test_permitted_fullstreams_complete_metadata(self):
        def stream(data):
            return dict(retained_hex=data.hex(),retained_pin=self.io.pin(data),truncated=False),dict(original_bytes=len(data),original_sha256=self.io.pin(data)['sha256'],retained_bytes=len(data),truncated=False,complete_observation=True)
        stdout,sm=stream(b's'*65536);stderr,em=stream(b'e'*131072)
        manager=dict(code=0,timeout=False,streams_complete=True,exception=None,stdout=stdout,stderr=stderr,stream_custody=dict(stdout=sm,stderr=em))
        inventory={'record_%03d.json'%i:self.io.pin(b'{}') for i in range(66)}
        inventory.update({name:self.io.pin(b'{}') for name in ('bootstrap.json','dispatch.json','claim.json','return.json','raw_report_000.json','child_report.json','manager_return.json','post.json','closed.json')})
        value=dict(schema='root-seven-audit-last-return-v1',stage=0,config_pin=self.io.pin(b'inventedconfig'),directory=str(self.directory),files={key:self.io.pin(b'{}') for key in ('claim','return','report','closed')},inventory=inventory,last_return=dict(status='complete'),root_observation=dict(result='success',active_state='inactive',control_group=''),root_manager=manager)
        raw=self.io.canonical(value);self.assertGreater(len(raw),262144);self.assertLess(len(raw),CAP);self.put(raw)
        self.assertEqual(self.hooks.known_root_return(self.io,str(self.path)),value)
    def test_control_stage2_fullstream_writer_reader_roundtrip(self):
        # Exact copied public stage2 producer fixture, no process or cloud dispatch.
        names=('custody','runner','control_fullstream_fixture');saved={name:sys.modules.get(name) for name in names}
        try:
            controls=BASE/'reference/controls_stage2'
            custody=fixtures.load('custody',controls/'custody.py')
            fixtures.load('runner',controls/'runner.py')
            other=fixtures.load('control_fullstream_fixture',controls/'test_controls.py')
            f=other.Fixture();self.addCleanup(f.close)
            manager=f.values['manager_return.json']
            for key,count in (('stdout',65536),('stderr',131072)):
                data=b'x'*count;manager[key]=dict(retained_hex=data.hex(),retained_pin=custody.pin(data),truncated=False);manager['stream_custody'][key]=dict(original_bytes=count,original_sha256=custody.pin(data)['sha256'],retained_bytes=count,truncated=False,complete_observation=True)
            f.write();held=f.verify();self.assertEqual(len(held['inventory']),75)
            evidence=f.base/'evidence';evidence.mkdir(mode=0o700);spec=custody.durable(other.IO(),str(evidence),'stage_00.private.json',held)
            self.assertGreater(spec['pin']['bytes'],262144);self.assertLessEqual(spec['pin']['bytes'],CAP)
            self.assertEqual(self.hooks.known_root_return(self.io,spec['path']),held)
        finally:
            for name,value in saved.items():
                if value is None:sys.modules.pop(name,None)
                else:sys.modules[name]=value

    def test_exact_one_mib_valid_json_boundary(self):
        # Generic reader capacity, not receipt-schema authorization.
        empty=self.io.canonical(dict(padding=''));value=dict(padding='x'*(CAP-len(empty)));raw=self.io.canonical(value);self.assertEqual(len(raw),CAP);self.put(raw)
        self.assertEqual(self.hooks.known_root_return(self.io,str(self.path)),value)
    def test_above_one_mib_rejected_before_parse(self):
        self.put(b' '* (CAP+1))
        with self.assertRaisesRegex(ValueError,'root_return_file'):self.hooks.known_root_return(self.io,str(self.path))
    def test_wrong_mode_and_hardlink_denied(self):
        self.put(b'{}');self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'root_return_file'):self.hooks.known_root_return(self.io,str(self.path))
        self.path.chmod(0o400);os.link(self.path,self.directory/'second.json')
        with self.assertRaisesRegex(ValueError,'root_return_file'):self.hooks.known_root_return(self.io,str(self.path))
    def test_symlink_denied(self):
        target=self.directory/'target.json';target.write_bytes(b'{}');target.chmod(0o400);os.symlink(target,self.path)
        with self.assertRaises(OSError):self.hooks.known_root_return(self.io,str(self.path))
    def test_stability_denied(self):
        self.put(b'{}');original=os.fstat;seen={}
        def observed(fd):
            result=original(fd)
            if result.st_size==2:
                if fd in seen:
                    return types.SimpleNamespace(st_size=result.st_size,st_mtime_ns=result.st_mtime_ns+1,st_ctime_ns=result.st_ctime_ns)
                seen[fd]=True
            return result
        with patch.object(self.hooks.os,'fstat',side_effect=observed):
            with self.assertRaisesRegex(ValueError,'root_return_stable'):self.hooks.known_root_return(self.io,str(self.path))


if __name__=='__main__':unittest.main()
