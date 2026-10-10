"""Constructed information/null controls only. Never accesses real data."""
import json
from pathlib import Path
import sys
import numpy as np
from features import masks
from ridge_probe import fit,predict,score,paired_bootstrap,SEEDS


def run():
    result = {'scope':'Constructed diagnostic controls; not EEW improvement or a false-positive-rate estimate','cases':{}}
    rng = np.random.default_rng(20261009)
    for label in ('null_constant_target','informative_cross_component'):
        x = np.zeros((512,127))
        x[:,106] = rng.choice([-1.,1.],size=len(x))
        if label == 'null_constant_target':
            raw = np.tile([4.5,16.,3.],(len(x),1))
        else:
            raw = np.column_stack((4.5+.5*x[:,106],16.+4*x[:,106],3.+x[:,106]))
        train,test = np.arange(320),np.arange(320,512)
        event = np.array([f'synthetic{i}' for i in test])
        case,ensemble = {},{}
        for arm,mask in masks().items():
            predictions = []
            for seed in SEEDS:
                state = fit(x[train],raw[train],np.ones(len(train)),mask,seed)
                predictions.append(predict(x[test],state)[0])
            ensemble[arm] = np.mean(predictions,axis=0)
            case[arm] = score(ensemble[arm],raw[test],np.ones(len(test)),event)
        case['F_minus_D_bootstrap'] = paired_bootstrap(ensemble['F'],ensemble['D'],raw[test],np.ones(len(test)),event)
        case['null_false_positive_on_tail_margin_and_ci'] = bool(case['F_minus_D_bootstrap']['m4_event_macro_mae_delta'] <= -.02
            and case['F_minus_D_bootstrap']['m4_event_macro_mae_ci95'][1] < 0)
        if label == 'null_constant_target':
            if case['null_false_positive_on_tail_margin_and_ci']:
                raise AssertionError('Constructed null triggered a tail-improvement claim')
        elif not case['F']['targets']['magnitude']['weighted_mae'] < .05:
            raise AssertionError('Cross-component informative control did not recover known signal')
        result['cases'][label] = case
    return result


if __name__ == '__main__':
    result = run()
    Path(sys.argv[1]).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
