"""Invented temp-module semantics and public vendor-source derivation; no Torch import."""
import ast
import copy
import hashlib
import importlib.machinery
import importlib.util
import importlib._bootstrap_external
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import generated_source as gs
import vendor_inventory as vi
import source_binding as sb
import secure_io as io
import fixtures as fx


class Generated(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.root.chmod(0o700)
        self.spec,self.inv,self.body=fx.generated(self.root/'generated')
        self.temp=tempfile.TemporaryDirectory(dir=self.spec['temp_parent']['path'])
        self.path=Path(self.temp.name)/gs.BASENAME;fx.put(self.path,self.body,self.spec['file_mode'])
        self.modules={}
        for role,name in gs.SOURCES.items():
            file=self.spec['generator_sources'][role];loader=vi.VerifiedSourceLoader(name,file['path'],file['path'],dict(pin=file['pin'],mode=file['mode']),lambda:None)
            module=types.ModuleType(name);module.__file__=file['path'];module.__loader__=loader;module.__spec__=importlib.util.spec_from_loader(name,loader)
            self.modules[name]=module
        inst=self.modules[gs.SOURCES['instantiator']];inst.INSTANTIATED_TEMPLATE_DIR_PATH=self.temp.name;inst._TEMP_DIR=self.temp
        self.patcher=patch.dict(sys.modules,self.modules);self.patcher.start()
    def tearDown(self):self.patcher.stop();self.temp.cleanup();self.tmp.cleanup()
    def module_spec(self,name=gs.MODULE,path=None):return importlib.util.spec_from_file_location(name,str(self.path if path is None else path))
    def test_exact_private_source_compiles_and_executes(self):
        gs.validate(self.spec,vi.load(self.inv,lambda:None),lambda:None)
        spec=gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None);namespace={};exec(spec.loader.get_code(gs.MODULE),namespace)
        self.assertEqual(namespace['VALUE'],7);self.assertEqual(spec.origin,str(self.path))
    def test_wrong_body_and_changed_body_before_compile_rejected(self):
        spec=gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None)
        fx.put(self.path,b'VALUE = 8\n',self.spec['file_mode'])
        with self.assertRaisesRegex(ValueError,'generated_body_pin'):spec.loader.get_code(gs.MODULE)
        with self.assertRaisesRegex(ValueError,'generated_body_pin'):gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None)
    def test_cached_bytecode_cannot_replace_exact_generated_source(self):
        evil=b'VALUE = 8\n';cached=Path(importlib.util.cache_from_source(str(self.path)));cached.parent.mkdir()
        raw=importlib._bootstrap_external._code_to_timestamp_pyc(compile(evil,str(self.path),'exec'),int(self.path.stat().st_mtime),len(self.body));cached.write_bytes(raw)
        namespace={};exec(importlib.machinery.SourceFileLoader(gs.MODULE,str(self.path)).get_code(gs.MODULE),namespace);self.assertEqual(namespace['VALUE'],8)
        spec=gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None);namespace={};exec(spec.loader.get_code(gs.MODULE),namespace);self.assertEqual(namespace['VALUE'],7)
    def test_unknown_module_basename_and_scriptable_branch_rejected(self):
        for name in ('_remote_module_other','_remote_module_scriptable','unrelated'):
            with self.assertRaisesRegex(ValueError,'generated_module_spec'):gs.bind(self.module_spec(name),name,self.spec,lambda:None)
        other=self.path.with_name('different.py');fx.put(other,self.body,0o644)
        with self.assertRaisesRegex(ValueError,'generated_path'):gs.bind(self.module_spec(path=other),gs.MODULE,self.spec,lambda:None)
    def test_other_private_temp_is_not_generator_directory(self):
        with tempfile.TemporaryDirectory(dir=self.spec['temp_parent']['path']) as alternate:
            file=Path(alternate)/gs.BASENAME;fx.put(file,self.body,0o644)
            with self.assertRaisesRegex(ValueError,'generated_path'):gs.bind(self.module_spec(path=file),gs.MODULE,self.spec,lambda:None)
    def test_private_mode_and_file_mode_are_exact(self):
        Path(self.temp.name).chmod(0o755)
        with self.assertRaisesRegex(ValueError,'generated_private_directory'):gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None)
        Path(self.temp.name).chmod(0o700);self.path.chmod(0o600)
        with self.assertRaisesRegex(ValueError,'generated_regular_file'):gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None)
    def test_symlink_file_and_hardlink_rejected(self):
        actual=self.path.with_name('real.py');self.path.rename(actual);self.path.symlink_to(actual)
        with self.assertRaises(OSError):gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None)
        self.path.unlink();os.link(actual,self.path)
        with self.assertRaisesRegex(ValueError,'generated_regular_file'):gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None)
    def test_symlink_private_directory_rejected(self):
        original=Path(self.temp.name);replacement=original.with_name('other-owned');original.rename(replacement);original.symlink_to(replacement,target_is_directory=True)
        try:
            with self.assertRaises(OSError):gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None)
        finally:original.unlink();replacement.rename(original)
    def test_wrong_owner_or_temp_parent_metadata_rejected(self):
        bad=copy.deepcopy(self.spec);bad['owner_uid']=os.geteuid()+1
        with self.assertRaisesRegex(ValueError,'generated_modes'):gs.validate(bad,vi.load(self.inv,lambda:None),lambda:None)
        bad=copy.deepcopy(self.spec);bad['temp_parent']['uid']+=1
        with self.assertRaisesRegex(ValueError,'generated_parent'):gs.bind(self.module_spec(),gs.MODULE,bad,lambda:None)
    def test_unverified_generator_loader_or_identity_rejected(self):
        inst=self.modules[gs.SOURCES['instantiator']];inst.__loader__=importlib.machinery.SourceFileLoader(inst.__name__,inst.__file__)
        with self.assertRaisesRegex(ValueError,'generated_generator_execution'):gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None)
    def test_unknown_generator_source_inventory_rejected(self):
        with self.assertRaisesRegex(ValueError,'generated_source_inventory'):gs.validate(self.spec,{},lambda:None)
    def test_temporary_object_and_depth_fixed(self):
        inst=self.modules[gs.SOURCES['instantiator']];inst._TEMP_DIR=types.SimpleNamespace(name=self.temp.name)
        with self.assertRaisesRegex(ValueError,'generated_temp_identity'):gs.bind(self.module_spec(),gs.MODULE,self.spec,lambda:None)
        bad=copy.deepcopy(self.spec);bad['max_depth']=2
        with self.assertRaisesRegex(ValueError,'generated_identity'):gs.validate(bad,vi.load(self.inv,lambda:None),lambda:None)
    def test_sourceless_or_package_helper_not_admitted(self):
        spec=importlib.util.spec_from_loader(gs.MODULE,importlib.machinery.SourcelessFileLoader(gs.MODULE,str(self.path)))
        with self.assertRaisesRegex(ValueError,'generated_module_spec'):gs.bind(spec,gs.MODULE,self.spec,lambda:None)
        spec=self.module_spec();spec.submodule_search_locations=[]
        with self.assertRaisesRegex(ValueError,'generated_module_spec'):gs.bind(spec,gs.MODULE,self.spec,lambda:None)
    def test_read_deadline_failure_does_not_compile(self):
        def stop():raise ValueError('invented expired source clock')
        with self.assertRaisesRegex(ValueError,'expired source clock'):gs.bind(self.module_spec(),gs.MODULE,self.spec,stop)
    def test_guard_route_stays_exact_single_module(self):
        prefix=self.root/'prefix';(prefix/'venv').mkdir(parents=True)
        runtime=dict(directory=str(prefix),manifest=fx.put(self.root/'prefix-manifest',io.canonical(dict(files={}))),critical={},regular_mode=0o444,
                     python=sys.executable,vendor_inventory=self.inv,generated_source=self.spec)
        sb.sysconfig.get_path('stdlib')
        # Install the guard before the verified generator becomes loaded, just as
        # the actual import sequence does. Then inject only invented source roles.
        with patch.object(sb,'interpreter_check'),patch.dict(sys.modules,{},clear=True),patch.object(sys,'path',[self.temp.name]):
            with sb.vendor_guard(runtime,{},(),lambda:None):
                sys.modules.update(self.modules)
                module=__import__(gs.MODULE);self.assertEqual(module.VALUE,7)
                other=self.path.with_name('unrelated.py');fx.put(other,b'raise AssertionError("must never execute")\n',0o644)
                with self.assertRaisesRegex(ValueError,'import_outside_verified_runtime'):__import__('unrelated')


class PublicTemplate(unittest.TestCase):
    def test_fixed_author_template_derivation_without_torch_import(self):
        reference=Path(__file__).parent/'reference';tree=ast.parse((reference/'template_source.py').read_bytes());constants={}
        for node in tree.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('_TEMPLATE_PREFIX','_REMOTE_FORWARD_TEMPLATE_ENABLE_MOVING_CPU_TENSORS_TO_CUDA'):
                constants[node.targets[0].id]=ast.literal_eval(node.value)
        format_values=dict(assign_module_interface_cls='module_interface_cls = None',args='*args',kwargs='**kwargs',arg_types='*args, **kwargs',arrow_and_return_type='',arrow_and_future_return_type='',jit_script_decorator='')
        raw=(constants['_TEMPLATE_PREFIX']+constants['_REMOTE_FORWARD_TEMPLATE_ENABLE_MOVING_CPU_TENSORS_TO_CUDA']).format(**format_values).encode('utf8')
        self.assertEqual(raw,(reference/'expected_helper_source.py').read_bytes());self.assertEqual(len(raw),2355)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'8205b16956fb264841ecd8644784a0d157f87df79b17c16825dc1163433ce5d8')
        self.assertNotIn('torch',sys.modules)


if __name__=='__main__':unittest.main()
