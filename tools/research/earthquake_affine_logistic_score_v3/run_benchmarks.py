"""Fixed synthetic measurements; no dataset/model inputs or file loading."""
import copy
import json
import time
import platform
import statistics
import numpy as np
import scipy
from benchmarks import CASES
from scorer import score,NumericalFailure
from reference import Posterior,gaussian_score,NumericalFailure as ReferenceFailure
from third_reference import grid_reference,missed_mode_diagnostic,gaussian_absolute_moments


def run(repeats=3):
    if type(repeats)is not int or not 1<=repeats<=3:raise ValueError('repeats')
    # Warm rule construction separately; do not hide its time.
    before=time.perf_counter();score(**{k:v for k,v in CASES[0].items()if k!='name'},processing_begin=time.monotonic());cold=time.perf_counter()-before
    rows=[]
    for case in CASES:
        args={k:v for k,v in case.items()if k!='name'};newtimes=[];oldtimes=[];latest=None;legacy=None
        for _ in range(repeats):
            before=time.perf_counter()
            try:latest=score(**args,processing_begin=time.monotonic())
            except NumericalFailure as error:latest={'accepted':False,'reason':str(error),'evidence':error.evidence}
            newtimes.append(time.perf_counter()-before)
            before=time.perf_counter();old=None
            try:
                old=Posterior(case['pi'],case['mu'],case['sigma'],case['affine']);legacy={'status':'returned','score':old.score(case['target'])}
            except ReferenceFailure as error:legacy={'status':'failed','reason':str(error)}
            finally:
                if old is not None:old.components.clear();old._cdf_cache.clear()
            oldtimes.append(time.perf_counter()-before)
        row=dict(name=case['name'],v3_median_seconds=statistics.median(newtimes),legacy_median_seconds=statistics.median(oldtimes),v3=latest,legacy=legacy)
        if 'score'in latest and legacy['status']=='returned':row['legacy_crps_difference']=latest['score']['crps']-legacy['score']['crps']
        if case['name']=='sharp_20':row['diagnostic_only']=score(**args,processing_begin=time.monotonic(),require_gh=False)
        rows.append(row)
    case=CASES[3];args={k:v for k,v in case.items()if k!='name'}
    grid=[grid_reference(**args,resolution=r)for r in(20,40,80)]
    hazard_diagnostic=missed_mode_diagnostic(**args)
    zero=copy.deepcopy(args);zero['affine']=[]
    counter=dict(nonzero_hazard=dict(grids=grid,legacy_mode_diagnostic=hazard_diagnostic),zero_hazard=dict(analytic=gaussian_score(zero['target'],zero['pi'],zero['mu'],zero['sigma']),legacy_mode_diagnostic=missed_mode_diagnostic(**zero),v3=score(**zero,processing_begin=time.monotonic())))
    far=CASES[7];counter['rare_far_zero_hazard']=dict(analytic=gaussian_absolute_moments(far['pi'],far['mu'],far['sigma'],far['target']),legacy_mode_diagnostic=missed_mode_diagnostic(**{k:v for k,v in far.items()if k!='name'}))
    return dict(schema='affine-logistic-v3-synthetic-benchmark-v1',actual_data=False,scientific_superiority=False,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,repeats=repeats,cold_normal_seconds=cold,rows=rows,counterexample=counter)


if __name__=='__main__':print(json.dumps(run(),allow_nan=False,sort_keys=True,indent=2))
