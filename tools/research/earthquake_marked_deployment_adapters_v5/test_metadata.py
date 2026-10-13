"""Invented metadata registration and negative authority tests; no Torch import."""
import ast
import copy
import importlib
import importlib.machinery
import importlib.util
import importlib.metadata
import hashlib
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import fixtures as fx
import metadata_finder as mf
import secure_io as io
import source_binding as sb
import vendor_inventory as vi


class Metadata(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        generated,inventory,_=fx.generated(self.root/'vendor');self.spec=fx.metadata(inventory);self.inventory=inventory
        prefix=self.root/'prefix';(prefix/'venv').mkdir(parents=True)
        self.runtime=dict(directory=str(prefix),manifest=fx.put(self.root/'manifest',io.canonical(dict(files={}))),critical={},regular_mode=0o444,
                          python=sys.executable,vendor_inventory=inventory,generated_source=generated,metadata_finder=self.spec)
        self.site=str(Path(self.spec['sources']['package']['path']).parent.parent);sb.sysconfig.get_path('stdlib')
    def tearDown(self):self.tmp.cleanup()
    @contextmanager
    def active(self):
        with patch.object(sb,'interpreter_check'),patch.dict(sys.modules,{'sys':sys,'importlib':importlib,'importlib.metadata':importlib.metadata},clear=True),patch.object(sys,'path',[self.site]):
            with sb.vendor_guard(self.runtime,{},(),lambda:None):yield
    def load(self):
        package=__import__('importlib_metadata');self.assertIsNone(importlib.util.find_spec('invented_absent'))
        self.assertEqual(len(sys.meta_path),2);return package,sys.meta_path[1]
    def test_verified_registration_metadata_discovery_and_absence(self):
        original=sys.meta_path
        with self.active():
            package,finder=self.load();self.assertIs(type(finder),package.MetadataPathFinder)
            self.assertEqual([list(x.find_distributions()) for x in sys.meta_path if hasattr(x,'find_distributions')],[['invented-metadata']])
            self.assertIsNone(importlib.util.find_spec('invented_absent'))
            with self.assertRaises(ModuleNotFoundError):__import__('invented_absent')
            with patch.object(importlib.machinery.PathFinder,'invalidate_caches') as invalidate:
                importlib.invalidate_caches();invalidate.assert_called_once()
        self.assertIs(sys.meta_path,original)
    def test_metadata_presence_never_allows_unknown_code(self):
        with self.active():
            self.load();fx.put(Path(self.site)/'unknown.py',b'raise AssertionError("unverified executed")\n')
            importlib.invalidate_caches()
            with self.assertRaisesRegex(ValueError,'import_outside_verified_runtime'):__import__('unknown')
    def test_missing_source_inventory_and_changed_pin_rejected(self):
        with self.assertRaisesRegex(ValueError,'metadata_source_inventory'):mf.validate(self.spec,{},lambda:None)
        bad=copy.deepcopy(self.spec);bad['sources']['compat']['pin']=io.pin(b'wrong')
        with self.assertRaisesRegex(ValueError,'metadata_source_inventory'):mf.validate(bad,vi.load(self.inventory,lambda:None),lambda:None)
    def test_source_loader_must_prove_actual_verified_execution(self):
        with self.active():
            _,finder=self.load();module=sys.modules['importlib_metadata._compat'];loader=module.__loader__
            module.__loader__=importlib.machinery.SourceFileLoader(module.__name__,module.__file__)
            try:
                with self.assertRaisesRegex(ValueError,'metadata_execution_binding'):mf.live(finder,self.spec,lambda:None)
            finally:module.__loader__=loader
    def test_instance_and_class_find_spec_overrides_rejected(self):
        with self.active():
            package,finder=self.load();finder.find_spec=lambda *args,**kwargs:None
            try:
                with self.assertRaisesRegex(ValueError,'metadata_finder_identity'):mf.live(finder,self.spec,lambda:None)
            finally:del finder.find_spec
            package.MetadataPathFinder.find_spec=staticmethod(lambda *args,**kwargs:None)
            try:
                with self.assertRaisesRegex(ValueError,'metadata_finder_identity'):mf.live(finder,self.spec,lambda:None)
            finally:del package.MetadataPathFinder.find_spec
    def test_null_code_with_side_effect_or_non_none_return_rejected_without_call(self):
        with self.active():
            _,finder=self.load();compat=sys.modules['importlib_metadata._compat'];function=vars(compat.NullFinder)['find_spec'].__func__;original=function.__code__
            for body in ['def find_spec(*args, **kwargs):\n    return 1\n','def find_spec(*args, **kwargs):\n    MUTATIONS.append(1)\n    return None\n']:
                replacement=next(x for x in compile(body,compat.__file__,'exec',dont_inherit=True).co_consts if isinstance(x,types.CodeType));function.__code__=replacement
                try:
                    with self.assertRaisesRegex(ValueError,'metadata_find_spec_not_inert'):mf.live(finder,self.spec,lambda:None)
                finally:function.__code__=original
    def test_verified_metadata_method_binding_required(self):
        with self.active():
            package,finder=self.load();original=vars(package.MetadataPathFinder)['find_distributions'];package.MetadataPathFinder.find_distributions=classmethod(lambda cls:[])
            try:
                with self.assertRaisesRegex(ValueError,'metadata_method_binding'):mf.live(finder,self.spec,lambda:None)
            finally:package.MetadataPathFinder.find_distributions=original
    def test_other_finder_prepend_extra_displaced_guard_rejected(self):
        with self.active():
            _,finder=self.load();original=list(sys.meta_path);guard=original[0]
            for altered in [[finder,guard],[guard,finder,object()],[finder],[object(),finder]]:
                sys.meta_path[:]=altered
                try:
                    with self.assertRaisesRegex(ValueError,'import_guard_changed'):guard.find_spec('invented_absent')
                finally:sys.meta_path[:]=original
    def test_registered_finder_removal_or_replacement_rejected(self):
        with self.active():
            package,finder=self.load();guard=sys.meta_path[0]
            sys.meta_path.pop()
            try:
                with self.assertRaisesRegex(ValueError,'metadata_finder_removed'):guard.find_spec('invented_absent')
            finally:sys.meta_path.append(finder)
            sys.meta_path[1]=package.MetadataPathFinder()
            try:
                with self.assertRaisesRegex(ValueError,'metadata_finder_replaced'):guard.find_spec('invented_absent')
            finally:sys.meta_path[1]=finder
    def test_deadline_rejected_before_live_finder_validation(self):
        with self.active():
            _,finder=self.load()
            def stop():raise ValueError('invented expired clock')
            with self.assertRaisesRegex(ValueError,'expired clock'):mf.live(finder,self.spec,stop)
    def test_validation_does_not_hash_unrelated_vendor_payload(self):
        allowed=vi.load(self.inventory,lambda:None)
        allowed[str(self.root/'unrelated-never-read')]=dict(pin=io.pin(b'not present'),mode=0o444)
        mf.validate(self.spec,allowed,lambda:None)


class PublicContract(unittest.TestCase):
    def test_supplied_primary_source_registers_exact_inert_metadata_finder(self):
        reference=Path(__file__).parent/'reference';compat=(reference/'vendor__compat.py').read_bytes();package=(reference/'vendor___init__.py').read_bytes()
        self.assertEqual(hashlib.sha256(compat).hexdigest(),'542e590cb953f8172c85ab824a174526f30d2e7b4925f67334ad667866be7a7c')
        self.assertEqual(hashlib.sha256(package).hexdigest(),'bbb130e3e524a73358fa46ba93e591903850652d5a9242cc7d6b367849d4986a')
        cls=next(x for x in ast.parse(compat).body if isinstance(x,ast.ClassDef) and x.name=='NullFinder')
        fn=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='find_spec')
        self.assertEqual(ast.dump(fn.decorator_list[0]),"Name(id='staticmethod', ctx=Load())");self.assertEqual(len(fn.body),1)
        self.assertIsInstance(fn.body[0],ast.Return);self.assertIsNone(fn.body[0].value.value)
        cls=next(x for x in ast.parse(package).body if isinstance(x,ast.ClassDef) and x.name=='MetadataPathFinder')
        self.assertEqual([x.id for x in cls.bases],['NullFinder','DistributionFinder']);self.assertEqual([x.id for x in cls.decorator_list],['install'])
        self.assertNotIn('find_spec',[x.name for x in cls.body if isinstance(x,ast.FunctionDef)]);self.assertNotIn('torch',sys.modules)


if __name__=='__main__':unittest.main()
