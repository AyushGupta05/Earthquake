"""One positively bound metadata-only finder; no added code-loading fallback."""
from pathlib import Path
import sys
import types
import secure_io as io
import vendor_inventory as vi

MODULES={'package':'importlib_metadata','compat':'importlib_metadata._compat'}
_CLASS=next(x for x in compile('class NullFinder:\n    @staticmethod\n    def find_spec(*args, **kwargs):\n        return None\n','<inert-contract>','exec',dont_inherit=True).co_consts if isinstance(x,types.CodeType))
INERT=next(x for x in _CLASS.co_consts if isinstance(x,types.CodeType))
CODE_FIELDS=('co_code','co_consts','co_names','co_varnames','co_argcount','co_posonlyargcount','co_kwonlyargcount','co_nlocals','co_stacksize','co_flags','co_freevars','co_cellvars')


def validate(spec,allowed,check):
    check();io.need(type(spec) is dict and set(spec)=={'schema','sources'} and spec['schema']=='importlib-metadata-inert-finder-v1','metadata_spec')
    sources=spec['sources'];io.need(type(sources) is dict and set(sources)==set(MODULES),'metadata_sources')
    for role,file in sources.items():
        check();io.need(type(file) is dict and set(file)=={'path','pin','mode'},'metadata_source_spec')
        io.parts(file['path'],True);io.pin_check(file['pin'],1024*1024)
        io.need(type(file['mode']) is int and 0<=file['mode']<=0o777 and str(Path(file['path']).resolve(strict=True))==file['path'],'metadata_source_path')
        io.need(allowed.get(file['path'])==dict(pin=file['pin'],mode=file['mode']),'metadata_source_inventory')
        io.read_file(file,1024*1024)
    io.need(str(Path(sources['package']['path']).parent)==str(Path(sources['compat']['path']).parent)
            and Path(sources['package']['path']).name=='__init__.py' and Path(sources['compat']['path']).name=='_compat.py','metadata_source_layout');check()


def _loaded(file,name):
    module=sys.modules.get(name);io.need(type(module) is types.ModuleType and module.__dict__.get('__name__')==name and module.__dict__.get('__file__')==file['path'],'metadata_module')
    loader=module.__dict__.get('__loader__');spec=module.__dict__.get('__spec__')
    io.need(type(loader) is vi.VerifiedSourceLoader and spec is not None and spec.name==name and spec.loader is loader and loader.name==name
            and loader.path==file['path'] and loader.verified_path==file['path'] and loader.binding==dict(pin=file['pin'],mode=file['mode']),'metadata_execution_binding')
    return module


def live(finder,spec,check):
    """Validate the exact loaded object without executing its find_spec method."""
    check();package=_loaded(spec['sources']['package'],MODULES['package']);compat=_loaded(spec['sources']['compat'],MODULES['compat'])
    cls=package.__dict__.get('MetadataPathFinder');null=compat.__dict__.get('NullFinder')
    io.need(isinstance(cls,type) and isinstance(null,type) and type(finder) is cls and vars(finder)=={}
            and cls.__module__==MODULES['package'] and cls.__name__=='MetadataPathFinder' and null.__module__==MODULES['compat']
            and null in cls.__mro__ and cls.__getattribute__ is object.__getattribute__ and 'find_spec' not in vars(cls),'metadata_finder_identity')
    descriptor=vars(null).get('find_spec');io.need(type(descriptor) is staticmethod,'metadata_null_descriptor');function=descriptor.__func__
    io.need(type(function) is types.FunctionType and cls.find_spec is function and finder.find_spec is function
            and function.__globals__ is vars(compat) and function.__module__==MODULES['compat'] and function.__code__.co_filename==spec['sources']['compat']['path']
            and function.__defaults__ is None and function.__kwdefaults__ is None and function.__closure__ is None,'metadata_null_identity')
    io.need(all(getattr(function.__code__,k)==getattr(INERT,k) for k in CODE_FIELDS),'metadata_find_spec_not_inert')
    for name in ('find_distributions','invalidate_caches'):
        descriptor=vars(cls).get(name);io.need(type(descriptor) is classmethod,'metadata_method_descriptor')
        fn=descriptor.__func__;io.need(type(fn) is types.FunctionType and fn.__globals__ is vars(package) and fn.__module__==MODULES['package']
              and fn.__code__.co_filename==spec['sources']['package']['path'],'metadata_method_binding')
    check();return finder
