"""Immutable raw-prefix export sharing completed polarization v2 identities.

Dry-run is default. No fitting. Production reads exactly the selected TRAIN
traces after validating the complete shared artifact and pinned source files.
The reviewed shared per-deadline mask is authoritative; this exporter repeats
basic finite/variance checks for every marked-valid prefix, not the expensive
127-feature eigendecomposition. It never replaces rejected observations.
"""
import argparse
import csv
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from response_data import file_sha
from audit_response import atomic_json,load_module,INVENTORY_SHA,ARCHIVE_SHA,finite_json
from join_train_metadata import row_join

POLARIZATION_PINS={'features.py':'417316ea2ff5c55384cefae4edecf4b98a5a1341c41558ea0ebf459afb9a5fec',
 'population.py':'7a36778e9d433181a2bb82adc195de7b5c1a8d3579b3e04de8bf6415eb11610f',
 'extract_features.py':'dce679f91046401d9c5d16f8e382be07fde17b5fae7d6608e949d6d79f22b5fe',
 'audit_metadata.py':'6a8f47c8fa6966c533765118e7b397c293fcf87409d2d4cd42a7ac63a198720f',
 'protocol.md':'a9b12a88be3a46e96d0f3f208f64b7728d1a17bb132e146887694e40288a448b'}


def basic_valid(segment,gain,seconds):
    observed=np.asarray(segment[:,:200+100*seconds],dtype=np.float64)
    if observed.shape!=(3,200+100*seconds) or not np.isfinite(observed).all():return False
    native=observed/np.asarray(gain)[:,None]
    noise=native[:,:200]-native[:,:200].mean(-1,keepdims=True)
    signal=native[:,200:]-native[:,200:].mean(-1,keepdims=True)
    with np.errstate(over='ignore',invalid='ignore'):
        nrms=np.sqrt((noise*noise).mean(-1));srms=np.sqrt((signal*signal).mean(-1))
    return bool(np.isfinite(nrms).all() and np.isfinite(srms).all() and (nrms>1e-12).all() and (srms>1e-12).all())


def validate_authoritative(rows,expected):
    n=len(rows)
    if not n:raise ValueError('Empty shared population')
    for key in ('source_row_index','trace_name','source_id','station_id','station_group','subset','sampling_weight',
                'event_bucket','station_bucket','n_metadata_eligible','n_sampled'):
        values=np.array([r[key] for r in rows],dtype=expected[key].dtype)
        if expected[key].shape!=(n,) or not np.array_equal(values,expected[key]):raise ValueError('Shared identity/value mismatch: '+key)
    if expected['valid'].dtype!=np.bool_ or expected['valid'].shape!=(n,3) or expected['invalid_codes'].shape!=(n,3):raise ValueError('Invalid shared validity schema')
    if not np.array_equal(expected['valid'],expected['invalid_codes']==0):raise ValueError('Invalid shared mask/codes')
    if not np.array_equal(expected['deadlines'],[1,3,5]):raise ValueError('Shared deadline order')
    if not np.array_equal(expected['target_names'],['source_magnitude','path_hyp_distance_km','source_depth_km']):raise ValueError('Shared target convention')
    targets=np.array([[float(r[k]) for k in expected['target_names']] for r in rows])
    if targets.shape!=expected['targets'].shape or not np.array_equal(targets,expected['targets']):raise ValueError('Shared targets/order mismatch')
    if len(set(expected['trace_name']))!=n or len(set(expected['source_row_index']))!=n:raise ValueError('Duplicate identity')
    if not np.isin(expected['subset'],['fit','eval_seen','eval_held']).all():raise ValueError('Unknown shared subset')
    if not np.isfinite(expected['sampling_weight']).all() or (expected['sampling_weight']<=0).any():raise ValueError('Invalid recording weight')
    if (expected['n_sampled']<=0).any() or (expected['n_metadata_eligible']<expected['n_sampled']).any():raise ValueError('Invalid recording denominators')
    if not np.array_equal(expected['sampling_weight'],expected['n_metadata_eligible']/expected['n_sampled']):raise ValueError('Recording weight/denominator mismatch')
    fit=expected['subset']=='fit';held=expected['subset']=='eval_held'
    if set(expected['source_id'][fit])&set(expected['source_id'][~fit]):raise ValueError('Held-event exposure')
    if set(expected['station_group'][fit])&set(expected['station_group'][held]):raise ValueError('Held-station exposure')


def write_export(raw,rows,expected,provider,output,provenance):
    """Also usable with an in-memory synthetic HDF-like mapping in unit tests.

    provider(row)->static34,gain3,units3,response72,epochIDs3. It must use the
    exact complete-window epoch. Signals are stored float64 so released int32
    counts remain exact; float32 model conversion is explicit at batch entry.
    """
    validate_authoritative(rows,expected)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    manifest=dict(provenance,status='started',rows=len(rows),deadlines=[1,3,5],
      counts_dtype='float64',count_clock='[P,P+500) at100Hz, ENZ; no waveform standardization',
      validity_authority='Pinned completed polarization v2 artifact; basic causal checks repeated here',
      source_sha256={name:file_sha(Path(__file__).with_name(name)) for name in ('export_waveforms.py','response_data.py','audit_response.py','join_train_metadata.py')})
    atomic_json(output/'manifest.json',manifest)
    counts=np.lib.format.open_memmap(output/'counts.npy',mode='w+',dtype=np.float64,shape=(len(rows),3,500))
    counts[:]=np.nan
    statics=[];gains=[];responses=[];epochs=[];units=[];rowhash=hashlib.sha256()
    for i,row in enumerate(rows):
        static,gain,unit,response,epoch=provider(row)
        static=np.asarray(static,dtype=np.float64);gain=np.asarray(gain,dtype=np.float64);response=np.asarray(response,dtype=np.float64)
        if static.shape!=(34,) or gain.shape!=(3,) or response.shape!=(72,) or len(epoch)!=3:raise ValueError('Provider schema mismatch')
        if not all(np.isfinite(v).all() for v in (static,gain,response)) or (gain<=0).any():raise ValueError('Provider nonfinite/invalid gain')
        if not np.allclose(static[[11,19,27]],np.log10(gain),rtol=1e-5,atol=1e-5):raise ValueError('Provider static/gain mismatch')
        r=response.reshape(3,6,4);mask=r[...,3]
        if not np.isin(mask,[0,1]).all() or (r[...,:3]*(1-mask[...,None])!=0).any():raise ValueError('Provider response mask/fallback mismatch')
        if len(unit)!=3 or len(set(unit))!=1 or unit[0] not in ('m/s','m/s^2'):raise ValueError('Provider units mismatch')
        if not np.array_equal(gain,expected['sensitivities'][i]) or unit[0]!=expected['native_units'][i]:raise ValueError('Shared response/gain disagreement')
        name=row['trace_name']
        if '/' in name or name in ('.','..'):raise ValueError('Literal trace name required')
        try:dataset=raw['data'][name]
        except KeyError:dataset=None
        npts=int(float(row['trace_npts']));p=int(float(row['trace_P_arrival_sample']))
        shape_ok=(dataset is not None and dataset.ndim==2 and dataset.shape==(3,npts) and dataset.dtype.kind in 'ifu' and p>=200 and p+500<=npts)
        if not shape_ok:
            if expected['valid'][i].any():raise ValueError('Previously valid raw trace missing/changed shape')
        else:
            segment=np.asarray(dataset[:,p-200:p+500],dtype=np.float64)
            for j,t in enumerate((1,3,5)):
                if expected['valid'][i,j] and not basic_valid(segment,gain,t):raise ValueError('Shared valid observation fails repeated basic checks')
            counts[i]=segment[:,200:]
        rowhash.update(np.int64(row['source_row_index']).tobytes())
        identity=name.encode();rowhash.update(len(identity).to_bytes(8,'little'));rowhash.update(identity)
        rowhash.update(np.asarray(counts[i],dtype='<f8').tobytes())
        statics.append(static);gains.append(gain);responses.append(response);epochs.append(epoch);units.append(unit[0])
    counts.flush();del counts
    metadata={key:expected[key] for key in ('source_row_index','trace_name','source_id','station_id','station_group','subset',
        'sampling_weight','valid','invalid_codes','deadlines','event_bucket','station_bucket','n_metadata_eligible','n_sampled')}
    metadata.update(targets=expected['targets'][:,0],sensitivity=np.array(gains),static=np.array(statics),response=np.array(responses),
                    native_units=np.array(units),response_epoch_ids=np.array(epochs))
    np.savez(output/'metadata.npz',**metadata)
    manifest.update(status='complete',canonical_waveform_rows_sha256=rowhash.hexdigest(),
                    outputs_sha256={name:file_sha(output/name) for name in ('counts.npy','metadata.npz')})
    # Production caller may defer COMPLETE until source postchecks succeed.
    atomic_json(output/'manifest.json',manifest)
    return manifest


def complete(output):
    output=Path(output)
    atomic_json(output/'COMPLETE.json',{'manifest_sha256':file_sha(output/'manifest.json')})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('polarization-source','polarization-output','response-audit','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--polarization-manifest-sha256',required=True)
    p.add_argument('--response-join-sha256',required=True)
    p.add_argument('--execute',action='store_true')
    args=p.parse_args()
    if not args.execute:
        print(json.dumps({'execute':False,'scope':'Planned shared TRAIN raw-prefix export only; no reads or fitting',
                          'output':str(args.output),'source':str(args.polarization_output)}));return
    source=args.polarization_source.resolve()
    for name,digest in POLARIZATION_PINS.items():
        if file_sha(source/name)!=digest:raise ValueError('Polarization source changed: '+name)
    sys.path.insert(0,str(source))
    for name in ('features','population','audit_metadata'):
        if name in sys.modules and Path(sys.modules[name].__file__).resolve()!=source/(name+'.py'):raise ValueError('Conflicting shared helper import')
    helper=load_module('response_export_polarization',source/'extract_features.py',POLARIZATION_PINS['extract_features.py'])
    parent=args.polarization_output/'manifest.json'
    if file_sha(parent)!=args.polarization_manifest_sha256:raise ValueError('Shared manifest changed/unpinned')
    manifest=json.loads(parent.read_text())
    if manifest['status']!='complete' or manifest['protocol_sha256']!=POLARIZATION_PINS['protocol.md']:raise ValueError('Shared export incomplete/wrong protocol')
    for name in ('features.npz','selected_metadata.csv','station_groups.json'):
        if file_sha(args.polarization_output/name)!=manifest['outputs_sha256'][name]:raise ValueError('Shared output changed: '+name)
    for path,digest in ((helper.METADATA,helper.EXPECTED_METADATA),(helper.INVENTORY,ARCHIVE_SHA),(helper.SOURCE,INVENTORY_SHA)):
        if file_sha(path)!=digest:raise ValueError('Original source changed')
    if helper.raw_stat(helper.RAW)!=manifest['raw_stat_before']:raise ValueError('Raw source differs from shared extraction')
    with (args.polarization_output/'selected_metadata.csv').open() as f:rows=list(csv.DictReader(f))
    for row in rows:
        for k in ('source_row_index','event_bucket','station_bucket','n_metadata_eligible','n_sampled'):row[k]=int(row[k])
        row['sampling_weight']=float(row['sampling_weight'])
    with np.load(args.polarization_output/'features.npz',allow_pickle=False) as f:
        expected={k:f[k] for k in f.files if k not in ('features','principal_degenerate','feature_names') and not k.startswith('mask_')}
    join_path=args.response_audit/'train_join_audit.json'
    if file_sha(join_path)!=args.response_join_sha256:raise ValueError('Response join audit not pinned')
    join=json.loads(join_path.read_text())
    if join['archive_sha256']!=ARCHIVE_SHA or join['original_train_metadata_sha256']!=helper.EXPECTED_METADATA:raise ValueError('Response source mismatch')
    for name,key in [('channel_epochs.json','audited_epochs_sha256'),('response_evaluations.json','evaluated_responses_sha256')]:
        if file_sha(args.response_audit/name)!=join[key]:raise ValueError('Audited response artifact changed')
    records=json.loads((args.response_audit/'channel_epochs.json').read_text());evaluations=json.loads((args.response_audit/'response_evaluations.json').read_text())
    module,inventory=helper.load_inventory(helper.SOURCE,helper.INVENTORY)
    if len(records)!=len(inventory.epochs):raise ValueError('Response epoch count changed')
    details={}
    for epoch,record in zip(inventory.epochs,records):
        core={k:v for k,v in record.items() if k not in ('epoch_id','response_id','descriptor','channel_reasons')}
        if finite_json(asdict(epoch))!=core:raise ValueError('Response epoch identity/properties alignment')
        details[id(epoch)]=dict(record,response_reasons=evaluations[record['response_id']]['reasons']+record['channel_reasons'])
    def provider(row):
        static,gain,unit=helper.static_and_response(row,inventory,module)
        matched=row_join(row,inventory.index,details,module)
        if not matched['metadata_eligible']:raise ValueError('Shared record no longer metadata eligible')
        channels=matched['channels']
        descriptor=np.concatenate([np.asarray(by_epoch[c['epoch_id']]['descriptor']).ravel() for c in channels])
        return static,gain,unit,descriptor,[c['epoch_id'] for c in channels]
    by_epoch={r['epoch_id']:r for r in records}
    import h5py
    started=time.monotonic()
    with h5py.File(helper.RAW,'r') as raw:
        helper.configure_cache(raw);fmt=helper.verify_format(raw)
        out=write_export(raw,rows,expected,provider,args.output,{'scope':'TRAIN selected prefixes only; no fit',
             'polarization_manifest_sha256':file_sha(parent),'response_join_audit_sha256':file_sha(join_path),
             'raw_stat_before':helper.raw_stat(helper.RAW),'raw_full_file_hash':None,'raw_format':fmt,
             'raw_provenance_limit':'Pinned path/stat/format, not full huge-file content hash; exported rows hashed',
             'protocol_sha256':file_sha(Path(__file__).with_name('frozen_protocol_v1.md'))})
    if helper.raw_stat(helper.RAW)!=manifest['raw_stat_before']:raise ValueError('Raw source changed during export')
    if file_sha(parent)!=args.polarization_manifest_sha256 or file_sha(join_path)!=args.response_join_sha256:raise ValueError('Parent manifests changed during export')
    for name in ('features.npz','selected_metadata.csv','station_groups.json'):
        if file_sha(args.polarization_output/name)!=manifest['outputs_sha256'][name]:raise ValueError('Shared artifact changed during export')
    for path,digest in ((helper.METADATA,helper.EXPECTED_METADATA),(helper.INVENTORY,ARCHIVE_SHA),(helper.SOURCE,INVENTORY_SHA)):
        if file_sha(path)!=digest:raise ValueError('Original source changed during export')
    for name,key in [('channel_epochs.json','audited_epochs_sha256'),('response_evaluations.json','evaluated_responses_sha256')]:
        if file_sha(args.response_audit/name)!=join[key]:raise ValueError('Response artifact changed during export')
    for name,digest in out['source_sha256'].items():
        if file_sha(Path(__file__).with_name(name))!=digest:raise ValueError('Exporter source changed during export')
    for name,digest in POLARIZATION_PINS.items():
        if file_sha(source/name)!=digest:raise ValueError('Shared code changed during export')
    out['seconds']=time.monotonic()-started;atomic_json(args.output/'manifest.json',out);complete(args.output)
    print(json.dumps({'status':'complete','rows':len(rows),'seconds':out['seconds']}))


if __name__=='__main__':main()
