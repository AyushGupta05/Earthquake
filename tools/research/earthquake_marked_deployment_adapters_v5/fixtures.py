"""Invented source-only fixtures. They are never deployment authorization."""
import copy
from pathlib import Path
import secure_io as io


def put(path,raw,mode=0o400):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():path.chmod(0o600)
    path.write_bytes(raw);path.chmod(mode)
    return dict(path=str(path),pin=io.pin(raw),mode=mode)


def source(root,role='processor'):
    count={'processor':32,'native':22,'gaussian':34,'parent':32,'adapters':8}[role]
    values={'module.py':b'value=123\n'}
    values.update({'doc%02d.txt'%i:b'invented public source\n' for i in range(count-2)})
    files={name:io.pin(raw) for name,raw in values.items()}
    manifest=io.canonical(dict(files=files));values['FIRST_CLEAN_MANIFEST.json']=manifest
    for name,raw in values.items():put(root/name,raw)
    return dict(directory=str(root),files={n:io.pin(v) for n,v in values.items()},manifest=dict(path=str(root/'FIRST_CLEAN_MANIFEST.json'),pin=io.pin(manifest),mode=0o400),upload_manifest=None)


def commands(root):return {name:put(root/name,b'invented command identity '+name.encode(),0o775) for name in ('systemctl','systemd_run')}


def answer(raw=b'',code=0):return dict(code=code,timeout=False,stdout=raw,stderr=b'',streams_complete=True)


def comparison():
    rows=[dict(ordinal=i,partition='TRAIN' if i<65 else 'DEV',mw=i/10,group='invented-group-%d'%i,common=True) for i in range(87)]
    original='1'*64;proof=io.pin(b'invented independent proof only')
    old=dict(schema='root-original-strong-comparison-input-v1',original_packet_pins={'archive':io.pin(b'old invented archive'),'manifest':io.pin(b'old invented manifest')},original_packet_sha256=original,
             roster=[dict(ordinal=r['ordinal'],partition=r['partition'],mw=r['mw'],group=r['group'],horizons=[1,3,5]) for r in rows],fits=[])
    for seed in (20261012,20261013):
        for arm in ('B','F','H','T'):
            predictions=[dict(seed=seed,arm=arm,ordinal=r['ordinal'],horizon=h,group=r['group'],target=r['mw'],status='complete',mean=r['mw']) for r in rows[65:] for h in (1,3,5)]
            closed=dict(verified=True,no_optimizer=True,checkpoint_sha256='2'*64,source_sha256='3'*64,packet_sha256=original,proof_pin=proof)
            old['fits'].append(dict(status='complete',no_optimizer=True,seed=seed,arm=arm,packet_sha256=original,checkpoint_sha256='2'*64,result_pin=io.pin(io.canonical(predictions)),independent_closure=closed,predictions=predictions))
    return dict(rows=rows),old,proof,'9'*64


def root_receipt(scope,raws,now):
    """TEST ONLY. Real ROOT checker must independently verify all evidence."""
    return dict(schema='root-marked-stage-authority-v1',scope=copy.deepcopy(scope),decision='authorized',expires=now+400,
                evidence_pins=dict(publication=io.pin(raws['publication']),feature=io.pin(raws['feature_authority']),strong=io.pin(raws['strong_authority']),funding=scope['funding_pin']))


def vendor(root,raw=b'value = "good"\n',name='invented_pkg.py',mode=0o664):
    import base64
    import hashlib
    root=Path(root);site=root/'site-packages';rid='invented-1.0.dist-info';file=put(site/name,raw,mode)
    digest=base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
    record=put(site/rid/'RECORD',(name+',sha256='+digest+','+str(len(raw))+'\n'+rid+'/RECORD,,\n').encode(),0o664)
    doc=dict(schema='marked-supplemental-vendor-inventory-v1',roots=[str(site)],records={rid:record},files={file['path']:dict(file['pin'],mode=mode,record_id=rid,record_path=name)})
    return put(root/'vendor.json',io.canonical(doc)),file,record,doc


def generated(root,raw=b'VALUE = 7\n'):
    import os
    import stat
    import base64
    import hashlib
    root=Path(root);site=root/'site-packages';rid='invented-1.0.dist-info'
    sources={};files={};rows=[]
    for role,relative in [('instantiator','torch/distributed/nn/jit/instantiator.py'),('template','torch/distributed/nn/jit/templates/remote_module_template.py')]:
        body=('"""Invented '+role+' fixture, no Torch."""\n').encode();file=put(site/relative,body,0o664);sources[role]=file
        files[file['path']]=dict(file['pin'],mode=file['mode'],record_id=rid,record_path=relative)
        rows.append(relative+',sha256='+base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip('=')+','+str(len(body)))
    bodies={'importlib_metadata/_compat.py':b'class NullFinder:\n    @staticmethod\n    def find_spec(*args, **kwargs):\n        return None\n',
            'importlib_metadata/__init__.py':b'from ._compat import NullFinder\nimport sys\nclass MetadataPathFinder(NullFinder):\n    @classmethod\n    def find_distributions(cls,context=None):\n        return iter(("invented-metadata",))\n    @classmethod\n    def invalidate_caches(cls):\n        pass\nsys.meta_path.append(MetadataPathFinder())\n'}
    for relative,body in bodies.items():
        file=put(site/relative,body,0o644);files[file['path']]=dict(file['pin'],mode=file['mode'],record_id=rid,record_path=relative)
        rows.append(relative+',sha256='+base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip('=')+','+str(len(body)))
    record=put(site/rid/'RECORD',('\n'.join(rows)+'\n').encode(),0o664)
    inventory=put(root/'vendor.json',io.canonical(dict(schema='marked-supplemental-vendor-inventory-v1',roots=[str(site)],records={rid:record},files=files)))
    parent=root/'private-temp';parent.mkdir(mode=0o700);ps=parent.stat()
    spec=dict(schema='torch-nonscriptable-remote-helper-v1',module='_remote_module_non_scriptable',basename='_remote_module_non_scriptable.py',body_pin=io.pin(raw),generator_sources=sources,
              temp_parent=dict(path=str(parent),uid=ps.st_uid,mode=stat.S_IMODE(ps.st_mode)),owner_uid=os.geteuid(),directory_mode=0o700,file_mode=0o644,max_depth=1)
    return spec,inventory,raw


def metadata(inventory):
    doc=io.json_read(Path(inventory['path']).read_bytes());sources={}
    for role,suffix in [('package','/importlib_metadata/__init__.py'),('compat','/importlib_metadata/_compat.py')]:
        matches=[(p,b) for p,b in doc['files'].items() if p.endswith(suffix)];assert len(matches)==1
        path,entry=matches[0];sources[role]=dict(path=path,pin={k:entry[k] for k in ('bytes','sha256')},mode=entry['mode'])
    return dict(schema='importlib-metadata-inert-finder-v1',sources=sources)
