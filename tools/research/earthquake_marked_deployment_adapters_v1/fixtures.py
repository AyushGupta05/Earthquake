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
