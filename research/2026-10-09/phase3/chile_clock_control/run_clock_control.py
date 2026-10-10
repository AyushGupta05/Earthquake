"""Dry by default. Parent owns credit verification, cgroup and12h worker stop."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import json

# Must happen before Torch, either dependency or worker module, is imported.
if os.environ.get('CUBLAS_WORKSPACE_CONFIG', ':4096:8') != ':4096:8':
    raise ValueError('Conflicting CUBLAS_WORKSPACE_CONFIG; use pinned deterministic runtime')
os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
from clock_contract import preflight


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--plan-sha256',required=True)
    p.add_argument('--source-dir',type=Path,required=True)
    p.add_argument('--source-manifest',type=Path,required=True);p.add_argument('--source-manifest-sha256',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds',type=int,default=39600)
    p.add_argument('--synthetic-runtime',action='store_true',help='Parent-only invented-tensor CUDA equality proof; no production artifact reads')
    p.add_argument('--initial-replay',type=Path,help='Parent-only first16 TRAIN-fit initial replay against pinned diagnostic directory')
    p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    return p


def validate_output(output,plan,source_dir):
    output=output.resolve()
    protected=[Path(v['path']).parent.resolve() for v in plan['artifacts'].values()]+[source_dir.resolve(),Path(__file__).parent.resolve()]
    if output.exists() or any(output==p or p in output.parents for p in protected):
        raise ValueError('Require a new output outside all source and input-artifact directories')


def supervise(command,maximum,output):
    """Single child stays in outer cgroup/process group; synchronous cancellation."""
    cancellation=[]
    def cancelled(signum,frame):cancellation.append(signum)
    previous={sig:signal.getsignal(sig) for sig in (signal.SIGTERM,signal.SIGINT)}
    child=None;code=None;deadline=time.monotonic()+maximum
    try:
        for sig in previous:signal.signal(sig,cancelled)
        child=subprocess.Popen(command)
        while True:
            if cancellation:raise SystemExit(128+cancellation[0])
            remaining=deadline-time.monotonic()
            if remaining<=0:raise subprocess.TimeoutExpired(command,maximum)
            try:code=child.wait(timeout=min(.1,remaining));break
            except subprocess.TimeoutExpired:pass
        if cancellation:raise SystemExit(128+cancellation[0])
    finally:
        if child is not None:
            if child.poll() is None:child.kill()
            child.wait()
        success=code==0 and not cancellation and sys.exc_info()[0] is None
        complete=Path(output)/'COMPLETE.json'
        if not success and complete.exists():complete.unlink()
        for sig,handler in previous.items():signal.signal(sig,handler)
    if cancellation:raise SystemExit(128+cancellation[0])
    return code


def main():
    args=parser().parse_args();plan,protocol,sources=preflight(args)
    if not args.execute:
        if args.worker:raise ValueError('Worker requires explicit execution')
        print(json.dumps({'dry_run':True,'production_artifacts_opened':0,'protocol':protocol,'sources':sources},indent=2));return
    validate_output(args.output,plan,args.source_dir)
    if args.initial_replay and (args.output.resolve()==args.initial_replay.resolve() or args.initial_replay.resolve() in args.output.resolve().parents):
        raise ValueError('Replay output must be outside immutable diagnostic input directory')
    if args.worker:
        if args.synthetic_runtime:
            from clock_synthetic import execute_synthetic
            execute_synthetic(args,plan,protocol,sources)
        elif args.initial_replay:
            from clock_replay import execute_replay
            execute_replay(args,plan,protocol,sources)
        else:
            from clock_training import execute
            execute(args,plan,protocol,sources)
        return
    code=supervise([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--worker'],args.max_seconds,args.output)
    if code:raise SystemExit(code)


if __name__=='__main__':main()
