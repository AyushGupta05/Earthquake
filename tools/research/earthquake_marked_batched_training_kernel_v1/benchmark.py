"""Invented source-only microbenchmark; no optimizer or actual observation values."""
import json
import platform
import time
import numpy as np
import torch
import test_kernel as tests
import kernel


def run(arm, batched, repeats=5):
    samples=[]
    for iteration in range(repeats+1):
        data=tests.fixture()
        begin=time.monotonic()
        if batched:
            kernel.loss24(tests.batched(data,arm)['nll']).backward()
        else:
            p,m,c,n,y,h,o=data
            for i in range(24):
                posterior=tests.ref.forecast(tuple(x[i] for x in p),m[i],c,n[i],arm,6.,h[i],o[i],processing_begin=time.monotonic())
                (posterior.nll(y[i])/24).backward()
        elapsed=time.monotonic()-begin
        if iteration:samples.append(elapsed)
    return samples


if __name__=='__main__':
    torch.set_num_threads(1)
    results={}
    for arm in ('S','P'):
        scalar=run(arm,False);batch=run(arm,True)
        results[arm]=dict(scalar_seconds=scalar,batched_seconds=batch,
                          median_speedup=float(np.median(scalar)/np.median(batch)))
    print(json.dumps(dict(schema='invented-batched-kernel-benchmark-v1',python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,threads=torch.get_num_threads(),batch=24,cell_lengths=[len(x) for x in tests.fixture()[1]],results=results),sort_keys=True))
