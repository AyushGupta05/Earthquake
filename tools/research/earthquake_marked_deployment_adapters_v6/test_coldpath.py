"""Genuine cold search-path fixtures; no real vendor/scientific data imports."""
import base64
import hashlib
import importlib.util
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import fixtures as fx
import secure_io as io
import source_binding as sb
import vendor_inventory as vi


class ColdPath(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        generated,inventory,_=fx.generated(self.root/'fallback');self.inventory=inventory
        self.prefix=self.root/'prefix';(self.prefix/'venv').mkdir(parents=True)
        self.runtime=dict(directory=str(self.prefix),manifest=fx.put(self.root/'manifest',io.canonical(dict(files={}))),critical={},regular_mode=0o444,
                          python=sys.executable,vendor_inventory=inventory,generated_source=generated,metadata_finder=fx.metadata(inventory))
        self.site=io.json_read(Path(inventory['path']).read_bytes())['roots'][0];sb.sysconfig.get_path('stdlib')
    def tearDown(self):self.tmp.cleanup()
    def vendor(self,name,body):
        doc=io.json_read(Path(self.inventory['path']).read_bytes());rid=next(iter(doc['records']));record=doc['records'][rid]
        file=fx.put(Path(self.site)/name,body,0o644);digest=base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip('=')
        record=fx.put(Path(record['path']),Path(record['path']).read_bytes()+(name+',sha256='+digest+','+str(len(body))+'\n').encode(),record['mode']);doc['records'][rid]=record
        doc['files'][file['path']]=dict(file['pin'],mode=file['mode'],record_id=rid,record_path=name)
        self.inventory=fx.put(Path(self.inventory['path']),io.canonical(doc));self.runtime['vendor_inventory']=self.inventory;return file
    def prefix_file(self,name,body):
        file=fx.put(self.prefix/'venv'/name,body,0o444);doc=io.json_read(Path(self.runtime['manifest']['path']).read_bytes());doc['files']['venv/'+name]=file['pin']
        self.runtime['manifest']=fx.put(Path(self.runtime['manifest']['path']),io.canonical(doc));return file
    @contextmanager
    def cold(self,paths=None):
        # No fallback append here: the operative guard must discover it itself.
        initial=[str(self.prefix/'venv')] if paths is None else paths
        with patch.object(sb,'interpreter_check'),patch.dict(sys.modules,{'sys':sys},clear=True),patch.object(sys,'path',initial):yield initial
    def test_cold_fallback_discovered_only_after_verified_setup(self):
        self.vendor('cold_dependency.py',b'VALUE=73\n')
        with self.cold() as initial:
            self.assertNotIn(self.site,sys.path);self.assertIsNone(importlib.util.find_spec('cold_dependency'))
            with sb.vendor_guard(self.runtime,{},(),lambda:None):
                self.assertEqual(sys.path,[*initial,self.site]);self.assertEqual(__import__('cold_dependency').VALUE,73)
            self.assertIs(sys.path,initial)
    def test_existing_prefix_has_precedence_and_existing_root_not_duplicated(self):
        self.prefix_file('collision.py',b'VALUE="prefix"\n');self.vendor('collision.py',b'VALUE="fallback"\n')
        with self.cold() as initial:
            with sb.vendor_guard(self.runtime,{},(),lambda:None):self.assertEqual(__import__('collision').VALUE,'prefix')
            self.assertIs(sys.path,initial)
        with self.cold([str(self.prefix/'venv'),self.site]) as initial:
            with sb.vendor_guard(self.runtime,{},(),lambda:None):self.assertEqual(sys.path.count(self.site),1)
            self.assertIs(sys.path,initial)
    def test_bound_root_does_not_authorize_unlisted_module(self):
        fx.put(Path(self.site)/'unlisted.py',b'raise AssertionError("unbound execution")\n')
        with self.cold() as initial:
            with sb.vendor_guard(self.runtime,{},(),lambda:None):
                with self.assertRaisesRegex(ValueError,'import_outside_verified_runtime'):__import__('unlisted')
            self.assertIs(sys.path,initial)
    def test_missing_optional_and_actual_import_remain_safe(self):
        with self.cold():
            with sb.vendor_guard(self.runtime,{},(),lambda:None):
                self.assertIsNone(importlib.util.find_spec('absent_dependency'))
                with self.assertRaises(ModuleNotFoundError):__import__('absent_dependency')
    def test_unbound_inventory_root_tampering_never_changes_path(self):
        doc=io.json_read(Path(self.inventory['path']).read_bytes());doc['roots'].append(str(self.root/'unbound'))
        fx.put(Path(self.inventory['path']),io.canonical(doc))  # deliberately keep old positive pin
        with self.cold() as initial:
            with self.assertRaisesRegex(ValueError,'file_pin'):
                with sb.vendor_guard(self.runtime,{},(),lambda:None):self.fail('unbound inventory entered')
            self.assertIs(sys.path,initial)
    def test_symlink_root_rejected_before_search_path_mutation(self):
        alias=self.root/'alias';alias.symlink_to(self.site,target_is_directory=True)
        doc=io.json_read(Path(self.inventory['path']).read_bytes());doc['roots'].append(str(alias));self.runtime['vendor_inventory']=fx.put(Path(self.inventory['path']),io.canonical(doc))
        with self.cold() as initial:
            with self.assertRaises(OSError):
                with sb.vendor_guard(self.runtime,{},(),lambda:None):self.fail('symlink root entered')
            self.assertIs(sys.path,initial)
    def test_validated_root_return_preserves_existing_load_api(self):
        old=vi.load(self.inventory,lambda:None);bindings,roots=vi.load(self.inventory,lambda:None,include_roots=True)
        self.assertEqual(bindings,old);self.assertEqual(roots,(self.site,));self.assertIsInstance(old,dict)
        with self.assertRaisesRegex(ValueError,'include_roots_flag'):vi.load(self.inventory,lambda:None,include_roots=1)
    def test_cold_scientific_modules_binds_full_invented_core_without_path_help(self):
        self.prefix_file('numpy.py',b'__version__="invented-numpy"\n');self.prefix_file('scipy.py',b'__version__="invented-scipy"\n')
        self.vendor('torch.py',b'__version__="invented-torch"\nthreads=0\ndef set_num_threads(n):\n    global threads\n    threads=n\ndef get_num_threads():\n    return threads\nclass Cuda:\n    @staticmethod\n    def is_initialized():\n        return False\ncuda=Cuda()\n')
        raw={'native':{'marked_native.py':b'import numpy as np\n','packet_io.py':b'import numpy as np\nimport marked_native as m\n'},
             'gaussian':{'gaussian_operator.py':b'import numpy as np\nimport torch\n','reference_core.py':b'import numpy as np\n'},
             'processor':{'numeric_state.py':b'import numpy as np\n','processor.py':b'import numpy as np\nimport torch\nimport numeric_state as ns\n'}}
        for ref,role,name in [('reference/gaussian_operator.py','gaussian','gaussian_operator.py'),('reference/reference_core.py','gaussian','reference_core.py'),('reference/marked_native.py','native','marked_native.py'),('reference/native_packet_io.py','native','packet_io.py')]:raw['processor'][ref]=raw[role][name]
        specs={}
        for role,files in raw.items():
            directory=self.root/role
            for name,body in files.items():fx.put(directory/name,body)
            specs[role]=dict(directory=str(directory),files={name:io.pin(body) for name,body in files.items()})
        self.runtime['versions']=dict(python='.'.join(map(str,sys.version_info[:3])),numpy='invented-numpy',scipy='invented-scipy',torch='invented-torch')
        with self.cold() as initial:
            self.assertNotIn(self.site,sys.path)
            try:
                native,gaussian,processor=sb.scientific_modules(specs,raw,self.runtime,'cold_fixture',extra_sources=(),check=lambda:None)
                self.assertEqual(sys.path,[*initial,self.site]);self.assertEqual(gaussian['gaussian_operator'].torch.__version__,'invented-torch')
                self.assertIs(processor['processor'].torch,gaussian['gaussian_operator'].torch);self.assertIs(native['packet_io'].m,native['marked_native'])
                self.assertIs(processor['processor'].np,native['marked_native'].np)
            finally:
                if hasattr(sb,'_ACTIVE_VENDOR_GUARD'):
                    sb._ACTIVE_VENDOR_GUARD.__exit__(None,None,None);del sb._ACTIVE_VENDOR_GUARD
            self.assertIs(sys.path,initial)
        self.assertNotIn('torch',sys.modules)


if __name__=='__main__':unittest.main()
