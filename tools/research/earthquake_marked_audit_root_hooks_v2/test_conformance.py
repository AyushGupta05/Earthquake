"""Read only positively pinned PUBLIC frozen code packets, never scientific inputs."""
import ast
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import types
import unittest
import fixtures

BASE=Path(__file__).parent
PROFILE=json.loads((BASE/'PUBLIC_SOURCE_CONFORMANCE_PROFILE.json').read_text())


def origin(role):
    parent=os.environ.get('EEW_PUBLIC_CONFORMANCE_ROOT')
    return Path(parent)/role if parent else Path(PROFILE['roles'][role]['local_directory'])


class Conformance(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.io=fixtures.load('conformance_secure_io',BASE/'reference/reference/secure_io.py')
        self.hooks=fixtures.load('conformance_hooks',BASE/'hooks.py')
        path=origin('v6')/'source_binding.py';raw=path.read_bytes()
        self.assertEqual(self.io.pin(raw),PROFILE['roles']['v6']['files']['source_binding.py'])
        tree=ast.parse(raw)
        chosen=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('inventory','source')]
        counts=[node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='COUNTS' for target in node.targets)]
        self.sb=types.ModuleType('frozen_public_source_conformance')
        self.sb.__dict__.update(io=self.io,os=os,stat=stat,Path=Path)
        exec(compile(ast.Module(body=counts+chosen,type_ignores=[]),str(path),'exec'),self.sb.__dict__)
        self.assertEqual(len(chosen),2)
    def spec(self,role):
        data=PROFILE['roles'][role];source=origin(role);target=Path(self.temp.name).resolve()/role;target.mkdir()
        for name,pin in data['files'].items():
            raw=(source/name).read_bytes();self.assertEqual(self.io.pin(raw),pin)
            output=target/name;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(raw);output.chmod(0o400)
        mf=data['manifest']
        return dict(directory=str(target),files=data['files'],manifest=dict(path=str(target/mf),pin=data['files'][mf],mode=0o400),upload_manifest=None)
    def test_exact_real_six_public_manifest_formats(self):
        counts={'v6':45,'native':22,'auditor':31,'wrapper':21,'input_adapter':17,'harness':31}
        for role,count in counts.items():
            spec=self.spec(role);self.assertEqual(len(spec['files']),count)
            if role in ('v6','native'):raw=self.sb.source(spec,'adapters' if role=='v6' else 'native',lambda:None)
            else:raw=self.hooks.closed_source(self.io,self.sb,spec,lambda:None)
            self.assertEqual(set(raw),{n for n in spec['files'] if n.endswith('.py')})
    def test_previous_unknownrole_manifest_failures_are_reproduced(self):
        for role in ('auditor','wrapper','input_adapter','harness'):
            spec=self.spec(role)
            with self.assertRaisesRegex(ValueError,'unmanifested_source'):self.sb.source(spec,role,lambda:None)
            self.hooks.closed_source(self.io,self.sb,spec,lambda:None)
    def test_new_closed_source_no_missing_extra_or_mode_relaxation(self):
        spec=self.spec('input_adapter');directory=Path(spec['directory']);checksum=directory/'CHECKSUMS.sha256'
        checksum.rename(directory/'extra.txt')
        with self.assertRaisesRegex(ValueError,'source_closed'):self.hooks.closed_source(self.io,self.sb,spec,lambda:None)
        (directory/'extra.txt').rename(checksum);checksum.chmod(0o644)
        with self.assertRaises(ValueError):self.hooks.closed_source(self.io,self.sb,spec,lambda:None)
        checksum.chmod(0o400);self.hooks.closed_source(self.io,self.sb,spec,lambda:None)


if __name__=='__main__':unittest.main()
