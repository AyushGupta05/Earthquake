"""CPU-only protocol-v2 fit/scoring runner; dry-run unless --execute is given."""
import argparse
import json
import multiprocessing
import os
from pathlib import Path
import platform
import time
import traceback

for _key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[_key] = '2'
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import numpy as np
from audit_metadata import sha, EXPECTED_METADATA, EXPECTED_INVENTORY, EXPECTED_SOURCE
from extract_features import PROTOCOL_SHA256
from features import FEATURE_NAMES, masks
from population import bucket
from ridge_probe import SEEDS, fit, predict, ensemble_predictions, score, paired_bootstrap, gate

ADDENDUM_SHA256 = '6d83ce438aa94ced7805c35d7776be31b1fc1784a16ffbc10d653aaf6f7ee818'
TIME_LIMIT_SECONDS = 1800


def atomic_json(path,value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def verify_execution_code(output,source_directory,expected_hashes):
    changed = [name for name,expected in expected_hashes.items()
               if not (source_directory/name).exists() or sha(source_directory/name) != expected]
    if changed:
        path = output/'results.json'
        result = json.loads(path.read_text()) if path.exists() else {'completed_fits':[]}
        result.update(status='failed_provenance',error='Code changed during execution: '+', '.join(changed),
                      gate={'pass':False,'status':'invalid_provenance'})
        atomic_json(path,result)
        raise ValueError(result['error'])


def invalidate_abnormal_exit(output,outcome):
    if outcome['timed_out'] or outcome['exit_code'] != 0:
        path = output/'results.json'
        result = json.loads(path.read_text()) if path.exists() else {'completed_fits':[]}
        result.update(status='incomplete_timeout' if outcome['timed_out'] else 'failed_worker_exit',
                      gate={'pass':False,'status':'incomplete' if outcome['timed_out'] else 'failed'},watchdog=outcome)
        atomic_json(path,result)


def load_cache(directory):
    manifest = json.loads((directory/'manifest.json').read_text())
    if manifest.get('status') != 'complete' or manifest.get('protocol_sha256') != PROTOCOL_SHA256:
        raise ValueError('Incomplete cache or wrong protocol')
    required = {EXPECTED_METADATA,EXPECTED_INVENTORY,EXPECTED_SOURCE,PROTOCOL_SHA256}
    if set(manifest.get('pinned_sha256',{}).values()) != required:
        raise ValueError('Incorrect extraction input pins')
    if sha(directory/'features.npz') != manifest['outputs_sha256']['features.npz']:
        raise ValueError('Feature artifact checksum mismatch')
    here = Path(__file__).resolve().parent
    if set(manifest.get('code_sha256',{})) != {'extract_features.py','features.py','population.py','audit_metadata.py'}:
        raise ValueError('Extraction code manifest is incomplete')
    for name,expected in manifest['code_sha256'].items():
        if sha(here/name) != expected:
            raise ValueError('Extraction code does not match its artifact: '+name)
    with np.load(directory/'features.npz',allow_pickle=False) as source:
        data = {key:source[key] for key in source.files}
    n = len(data['source_row_index'])
    if (data['features'].shape != (n,3,127) or data['targets'].shape != (n,3)
            or data['valid'].shape != (n,3) or data['invalid_codes'].shape != (n,3)
            or not np.array_equal(data['deadlines'],[1,3,5])
            or list(data['feature_names']) != FEATURE_NAMES):
        raise ValueError('Descriptor schema mismatch')
    for name,mask in masks().items():
        if not np.array_equal(mask,data['mask_'+name]):
            raise ValueError('Arm mask changed')
    if not np.array_equal(data['valid'],data['invalid_codes']==0):
        raise ValueError('Invalid reason/validity mismatch')
    if not np.isfinite(data['features'][data['valid']]).all():
        raise ValueError('Nonfinite valid feature')
    if not np.isnan(data['features'][~data['valid']]).all():
        raise ValueError('Invalid feature rows must be explicitly NaN')
    if len(set(data['trace_name'])) != n or len(set(data['source_row_index'])) != n:
        raise ValueError('Duplicate sampled identity')
    event_magnitude = {}
    for i,event in enumerate(data['source_id']):
        event_fold = bucket('polarization-event-v1',event)
        station_fold = bucket('polarization-station-v1',data['station_group'][i])
        expected = 'fit' if event_fold>=2 and station_fold>=2 else ('eval_seen' if event_fold<2 and station_fold>=2 else 'eval_held' if event_fold<2 else 'excluded')
        if expected != data['subset'][i] or event_fold != data['event_bucket'][i] or station_fold != data['station_bucket'][i]:
            raise ValueError('Source identity violates preregistered split')
        magnitude = data['targets'][i,0]
        if event in event_magnitude and abs(event_magnitude[event]-magnitude)>1e-6:
            raise ValueError('Event magnitude inconsistent across sampled rows')
        event_magnitude[event] = magnitude
    if not np.allclose(data['sampling_weight'],data['n_metadata_eligible']/data['n_sampled'],rtol=0,atol=0):
        raise ValueError('Sampling weights changed after waveform nonresponse')
    return data,manifest


def score_subsets(prediction,transformed,data,valid):
    result = {}
    for subset in ('eval_seen','eval_held'):
        choose = valid & (data['subset']==subset)
        result[subset] = score(prediction[choose],data['targets'][choose],data['sampling_weight'][choose],
                               data['source_id'][choose],transformed[choose])
        result[subset]['strata'] = {}
        for field in ('native_units','station_channels'):
            result[subset]['strata'][field] = {}
            for value in np.unique(data[field][choose]):
                ix = choose & (data[field]==value)
                result[subset]['strata'][field][str(value)] = score(prediction[ix],data['targets'][ix],data['sampling_weight'][ix],data['source_id'][ix],transformed[ix])
    seen_events = set(data['source_id'][valid & (data['subset']=='eval_seen')])
    held_events = set(data['source_id'][valid & (data['subset']=='eval_held')])
    paired = np.isin(data['source_id'],sorted(seen_events & held_events))
    result['paired_event_population'] = {'events':len(seen_events & held_events)}
    for subset in ('eval_seen','eval_held'):
        ix = valid & paired & (data['subset']==subset)
        result['paired_event_population'][subset] = score(prediction[ix],data['targets'][ix],data['sampling_weight'][ix],data['source_id'][ix],transformed[ix])
    return result


def worker(cache,output):
    started = time.monotonic()
    output = Path(output)
    result = {'status':'running','completed_fits':[],'comparisons':[],'timing_seconds':{},
              'protocol_sha256':PROTOCOL_SHA256,'metric_scale_addendum_sha256':ADDENDUM_SHA256,
              'seed_order':list(SEEDS),'target_primary_units':['magnitude','km','km'],
              'runtime':{'python':platform.python_version(),'numpy':np.__version__,'cpu_threads':2,'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES']},
              'limitations':['TRAIN-internal new held events and stations only; no external generalization claim',
                             'Sampling weights do not repair waveform-quality nonresponse',
                             'Station dependence remains in event bootstrap uncertainty',
                             'Point ridge diagnostic; no probabilistic calibration or novelty claim']}
    try:
        data,manifest = load_cache(Path(cache))
        result['extraction_manifest_sha256'] = sha(Path(cache)/'manifest.json')
        result['features_sha256'] = manifest['outputs_sha256']['features.npz']
        result['population_quality'] = manifest['quality']
        for j,seconds in enumerate((1,3,5)):
            valid = data['valid'][:,j]
            fitting = valid & (data['subset']=='fit')
            if not fitting.any() or any(not (valid & (data['subset']==s)).any() for s in ('eval_seen','eval_held')):
                raise ValueError('Empty required fitting/evaluation subset')
            by_arm = {}
            for arm,mask in masks().items():
                predictions,transformed_predictions,seed_scores = [],[],[]
                for seed in SEEDS:
                    fit_started = time.monotonic()
                    state = fit(data['features'][fitting,j],data['targets'][fitting],data['sampling_weight'][fitting],mask,seed)
                    prediction = np.full((len(valid),3),np.nan)
                    transformed = np.full_like(prediction,np.nan)
                    prediction[valid],transformed[valid] = predict(data['features'][valid,j],state)
                    scores = score_subsets(prediction,transformed,data,valid)
                    stem = f'{seconds}s_{arm}_seed{seed}'
                    np.savez(output/(stem+'_model.npz'),**state)
                    np.savez(output/(stem+'_predictions.npz'),prediction=prediction,transformed_prediction=transformed,
                             source_row_index=data['source_row_index'],trace_name=data['trace_name'],
                             event_id=data['source_id'],station_group=data['station_group'],subset=data['subset'],valid=valid,
                             target=data['targets'],sampling_weight=data['sampling_weight'],mask=mask)
                    atomic_json(output/(stem+'_scores.json'),scores)
                    result['completed_fits'].append(stem)
                    result['timing_seconds'][stem] = time.monotonic()-fit_started
                    result['elapsed_seconds'] = time.monotonic()-started
                    atomic_json(output/'results.json',result)
                    print(json.dumps({'completed':stem,'seconds':result['elapsed_seconds']}),flush=True)
                    predictions.append(prediction)
                    transformed_predictions.append(transformed)
                    seed_scores.append(scores)
                ensemble,transformed = ensemble_predictions(predictions,transformed_predictions,valid)
                scores = score_subsets(ensemble,transformed,data,valid)
                stem = f'{seconds}s_{arm}_ensemble'
                np.savez(output/(stem+'_predictions.npz'),prediction=ensemble,transformed_prediction=transformed,
                         source_row_index=data['source_row_index'],trace_name=data['trace_name'],event_id=data['source_id'],
                         station_group=data['station_group'],subset=data['subset'],valid=valid,target=data['targets'],
                         sampling_weight=data['sampling_weight'],mask=mask)
                atomic_json(output/(stem+'_scores.json'),scores)
                by_arm[arm] = {'prediction':ensemble,'scores':scores,'seed_scores':seed_scores}
            for subset in ('eval_seen','eval_held'):
                sampled = data['subset']==subset
                ix = valid & sampled
                bootstrap = paired_bootstrap(by_arm['F']['prediction'][ix],by_arm['D']['prediction'][ix],
                    data['targets'][ix],data['sampling_weight'][ix],data['source_id'][ix])
                seed_deltas = []
                for k in range(2):
                    sf = by_arm['F']['seed_scores'][k][subset]['tail'].get('4',{})
                    sd = by_arm['D']['seed_scores'][k][subset]['tail'].get('4',{})
                    seed_deltas.append(sf.get('event_macro_mae',1e99)-sd.get('event_macro_mae',0))
                train_fraction = float(fitting.sum()/(data['subset']=='fit').sum())
                result['comparisons'].append({'seconds':seconds,'subset':subset,'B':by_arm['B']['scores'][subset],
                    'D':by_arm['D']['scores'][subset],'F':by_arm['F']['scores'][subset],'bootstrap':bootstrap,
                    'seed_m4_event_macro_deltas':seed_deltas,'valid_fraction':min(float(ix.sum()/sampled.sum()),train_fraction)})
            atomic_json(output/'results.json',result)
        result['gate'] = gate(result['comparisons'])
        result['status'] = 'complete'
        result['elapsed_seconds'] = time.monotonic()-started
        result['artifacts_sha256'] = {p.name:sha(p) for p in sorted(output.iterdir()) if p.suffix in ('.npz','.json') and p.name!='results.json'}
        atomic_json(output/'results.json',result)
    except Exception as error:
        result.update(status='failed',gate={'pass':False,'status':'failed'},error=str(error),
                      traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-started)
        atomic_json(output/'results.json',result)
        raise


def run_with_timeout(target,args,seconds):
    """Parent watchdog kills fitting/scoring at wall-clock deadline, even in BLAS."""
    process = multiprocessing.get_context('spawn').Process(target=target,args=args)
    started = time.monotonic()
    process.start()
    process.join(max(0,seconds-(time.monotonic()-started)))
    timed_out = process.is_alive()
    if timed_out:
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
    return {'timed_out':timed_out,'exit_code':process.exitcode,'elapsed_seconds':time.monotonic()-started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    args = parser.parse_args()
    plan = {'scope':'TRAIN-internal CPU fixed ridge fit/scoring','cache':str(args.cache),'output':str(args.output),
            'time_limit_seconds':TIME_LIMIT_SECONDS,'execute':args.execute}
    if not args.execute:
        print(json.dumps(plan,indent=2))
        return
    here = Path(__file__).resolve().parent
    if sha(here/'protocol.md') != PROTOCOL_SHA256 or sha(here/'metric_scale_addendum.md') != ADDENDUM_SHA256:
        raise ValueError('Protocol or approved metric clarification changed')
    args.output.mkdir(parents=True,exist_ok=False)
    files = ('ridge_probe.py','run_probe.py','features.py','population.py','extract_features.py','audit_metadata.py')
    hashes = {name:sha(here/name) for name in files}
    atomic_json(args.output/'run_manifest.json',dict(plan,code_sha256=hashes,protocol_sha256=PROTOCOL_SHA256,
                metric_scale_addendum_sha256=ADDENDUM_SHA256))
    outcome = run_with_timeout(worker,(str(args.cache),str(args.output)),TIME_LIMIT_SECONDS)
    atomic_json(args.output/'watchdog.json',outcome)
    invalidate_abnormal_exit(args.output,outcome)
    verify_execution_code(args.output,here,hashes)
    print(json.dumps(outcome),flush=True)
    if outcome['timed_out'] or outcome['exit_code'] != 0:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
