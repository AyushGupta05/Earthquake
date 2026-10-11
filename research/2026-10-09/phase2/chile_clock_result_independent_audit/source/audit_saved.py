"""Explicit completed-artifact replay; independent math, zero forwards or TEST reads."""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import time
import numpy as np
import independent_artifacts as art
import independent_math as calc

BASE=Path(__file__).resolve().parent
MEMBERS=('independent_math.py','independent_artifacts.py','checkpoint_state_body.py','audit_saved.py','test_independent.py','PROTOCOL.md')


def source_pins():return {n:art.file_pin(BASE/n,4*art.MIB)['sha256'] for n in MEMBERS}

def private(path):
    allowed=BASE.parent/'local_runs';p=Path(path)
    if allowed.is_symlink() or p.is_symlink() or not p.resolve().is_relative_to(allowed.resolve()) or p.resolve()==allowed.resolve():raise ValueError('private replay files must stay in local_runs')
    return p.resolve()

def load_indices(item,n,recorded_numpy):
    expected={'seed':20261013,'draws':2000,'events':n,'dtype':'int64','calls':'2000 successive integers(0,N,N)','pairing':'same indices across both arms/actions/deadlines; reset per split/seed'}
    if any(item.get(k)!=v for k,v in expected.items()) or item.get('numpy_version')!=recorded_numpy:raise ValueError('frozen bootstrap generation receipt differs')
    if set(item.get('canonical_sha256_by_seed',{}))!={'20261011','20261012'} or len(set(item['canonical_sha256_by_seed'].values()))!=1:raise ValueError('both reset-seed bootstrap index pins required')
    digest=item['canonical_sha256_by_seed']['20261011']
    if item.get('file'):
        f=item['file']
        if art.file_pin(f['path'],64*art.MIB)!=f['pin']:raise ValueError('private bootstrap file pin differs')
        indices=np.load(f['path'],allow_pickle=False)
    else:
        rng=np.random.default_rng(20261013)
        if np.__version__!=recorded_numpy or type(rng.bit_generator).__name__!=item.get('backend'):raise ValueError('actual recorded NumPy/bootstrap backend or private indices required')
        indices=np.asarray([rng.integers(0,n,n) for _ in range(2000)],dtype=np.int64)
    calc.validate_indices(indices,n,digest)
    return indices,digest

def inspect(receipt):
    if receipt.get('schema')!='chile-clock-independent-replay-inputs-v1' or receipt.get('completed_grid_handoff') is not True or receipt.get('source_pins')!=source_pins():raise ValueError('reviewed source-bound completed handoff required')
    protocol=art.json_file(receipt['protocol_path'],art.MIB)
    if art.file_pin(receipt['protocol_path'],art.MIB)['sha256']!=art.PROTOCOL:raise ValueError('frozen protocol changed')
    root=Path(receipt['grid_root']);verified=art.grid(root,receipt['complete_pin'],receipt['execution'])
    if verified['identity']['baseline_artifact_sha256']!=protocol['artifact_sha256']:raise ValueError('original nine artifact identity changed')
    original=receipt['original_files'];required={'run','split_manifest','dataset_manifest','metadata_manifest','metadata'}
    if set(original)!=required:raise ValueError('exact original provenance metadata members required')
    for name,item in original.items():
        if item['pin']['sha256']!=protocol['artifact_sha256'][name] or art.file_pin(item['path'],64*art.MIB)!=item['pin']:raise ValueError('original provenance input changed')
    run=art.json_file(original['run']['path']);split=art.json_file(original['split_manifest']['path']);manifest=art.json_file(original['dataset_manifest']['path']);sidecar=art.json_file(original['metadata_manifest']['path'])
    if run.get('test_reads')!=0 or run.get('selection_used_dev') is not False or run.get('selected_epoch')!=97 or manifest.get('schema')!='chile-team-prefix-v1' or manifest.get('stored_samples')!=3000 or manifest.get('source_test_waveforms_read') is not False or manifest.get('all_event_readback_verified') is not True or manifest.get('sha256')!=protocol['artifact_sha256']['cache'] or sidecar.get('cache_sha256')!=manifest['sha256'] or sidecar.get('sha256')!=original['metadata']['pin']['sha256'] or sidecar.get('rows')!=manifest['cache_rows'] or sidecar.get('columns')!=['EVENT','MA','TIME','source_row_index','benchmark_split']:raise ValueError('sealed original baseline provenance changed')
    population=art.split_and_targets(split,run,manifest,original['metadata']['path'],original['metadata']['pin'])
    trace=art.traces(verified['histories'],population['training_examples_per_epoch'])
    produced=art.json_file(root/'report.json');all_scores={};all_comp={};parameter_checks={};report_checks={}
    if produced.get('protocol_sha256')!=art.PROTOCOL or produced.get('runtime')!=verified['identity']['runtime']:raise ValueError('producer runtime/protocol differs')
    runtime=receipt['numerical_runtime']
    if runtime['torch']!=verified['identity']['runtime']['torch'] or runtime['numpy_backend']!='PCG64' or runtime['byteorder'] not in ('little','big'):raise ValueError('actual numerical runtime receipt differs')
    for split_name in ('calibration','dev'):
        predictions={};total_array_bytes=0;parameter_checks[split_name]={};all_scores[split_name]={};report_checks[split_name]={}
        for fit in (*art.FITS,'starting_epoch97'):
            name=f'{split_name}_{fit}_predictions.npz';p=art.prediction_archive(root/name,verified['pins'][name]);total_array_bytes+=sum(a.nbytes for a in p.values())
            if total_array_bytes>256*art.MIB:raise MemoryError('cohort saved-array memory bound exceeded')
            y=calc.validate(p)
            if p['event_ids'].tolist()!=population['ids'][split_name] or not np.array_equal(y,population['targets'][split_name]):raise ValueError('original saved cohort/target alignment differs')
            parameter_checks[split_name][fit]=calc.replay_arrays(p);predictions[fit]=p;all_scores[split_name][fit]=calc.scores(p)
            public_scores={k:v for k,v in all_scores[split_name][fit].items() if k!='tail_events'}
            report_checks[split_name][fit]=calc.compare_tree(public_scores,produced['scores'][split_name][fit])
        indices,digest=load_indices(receipt['bootstrap'][split_name],len(population['ids'][split_name]),runtime['numpy'])
        all_comp[split_name]={}
        for seed in (20261011,20261012):
            c=calc.paired(predictions[f'discrete_1_3_5_{seed}'],predictions[f'source_uniform_{seed}'],indices,digest)
            all_comp[split_name][str(seed)]=c
            public={k:v for k,v in c.items() if k!='bootstrap_indices_sha256'}
            report_checks[split_name]['comparison_'+str(seed)]=calc.compare_tree(public,produced['comparisons'][split_name][str(seed)])
        del predictions,indices
    gate=calc.gate(all_comp['dev']);gate_check=calc.compare_tree(gate,produced['gate'])
    tensor_file=receipt['checkpoint_proof'];proof=art.json_file(tensor_file['path'])
    if art.file_pin(tensor_file['path'])!=tensor_file['pin'] or proof.get('schema')!='chile-clock-independent-checkpoint-state-v1' or proof.get('all_checks_pass') is not True or proof.get('source_sha256')!=source_pins()['checkpoint_state_body.py'] or proof.get('request_sha256')!=tensor_file['request_sha256'] or proof.get('runtime')!={k:runtime[k] for k in ('python','torch','numpy','byteorder')}:raise ValueError('exact-runtime independent checkpoint proof missing')
    request=art.json_file(tensor_file['request_path'])
    if art.file_pin(tensor_file['request_path'],16*art.MIB)['sha256']!=tensor_file['request_sha256'] or request['complete']['pin']!=receipt['complete_pin'] or request['execution']!=receipt['execution'] or request['expected_runtime']!=proof['runtime'] or request['baseline']['pin']['sha256']!=protocol['artifact_sha256']['checkpoint'] or request['baseline']['expected_state_sha256']!=art.BASELINE_STATE or proof.get('baseline_initial_state_sha256')!=art.BASELINE_STATE or proof.get('baseline_pin')!=request['baseline']['pin'] or set(request['fits'])!=set(art.FITS):raise ValueError('checkpoint proof request is not bound to completed original artifacts')
    for fit in art.FITS:
        r=request['fits'][fit]
        if r['identity']!=verified['fit_receipts'][fit]['identity'] or r['history']!=verified['histories'][fit] or any(r[n]['pin']!=verified['pins'][fit+'/'+n+'.pth'] for n in ('model','latest')):raise ValueError('checkpoint proof used different fit/history/body')
        p=proof['fits'][fit]
        if p['completed_epochs']!=6 or p['identical_final_latest_state'] is not True or p['all_model_and_optimizer_values_finite'] is not True or p['optimizer_configuration_matches'] is not True or p['optimizer_steps']!=sum(r['trace']['batches'] for r in verified['histories'][fit]):raise ValueError('checkpoint tensor/draw proof differs')
    if set(proof.get('paired_rng',{}))!={'20261011','20261012'} or any(p.get('augmentation_global_model_python_numpy_equal') is not True or p.get('clock_state_exempt') is not True for p in proof['paired_rng'].values()):raise ValueError('final persisted RNG pairing not verified')
    passed=gate_check['passed'] and all(v['passed'] for cohort in report_checks.values() for v in cohort.values()) and all(v['passed'] for cohort in parameter_checks.values() for v in cohort.values())
    return {'schema':'chile-clock-independent-replay-v1','all_checks_pass':passed,'complete_pin':receipt['complete_pin'],'artifact_pins':verified['pins'],'source_pins':source_pins(),'numerical_runtime':runtime,'parameter_replay':parameter_checks,'trace_replay':trace,'report_replay':report_checks,'gate_replay':gate_check,'scores':all_scores,'comparisons':all_comp,'gate':gate,'checkpoint_proof_pin':tensor_file['pin'],'claim_limits':{'saved_parameter_and_recorded_pairing_replay_only':True,'new_checkpoint_waveform_forward':False,'large_event_generalization':False,'sequence_independence':False,'novelty_or_matched_paper_superiority':False,'TEST_reads':0,'training_or_optimizer_steps':0}}

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--inputs-sha256',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:raise ValueError('explicit completed handoff execution required')
    def deadline(signum,frame):raise TimeoutError('independent replay1200s ceiling; incomplete')
    prior=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,1200)
    try:
        inputs=private(a.inputs);out=private(a.output)
        if art.file_pin(inputs,4*art.MIB)['sha256']!=a.inputs_sha256 or out.exists():raise ValueError('exact parent input pin and fresh private output required')
        result=inspect(art.json_file(inputs,4*art.MIB));result['inputs_sha256']=a.inputs_sha256
        out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
        return 0 if result['all_checks_pass'] else 1
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,prior)

if __name__=='__main__':raise SystemExit(main())
