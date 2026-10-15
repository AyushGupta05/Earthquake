"""Exact frozen scalar validators, restricted to historical comparator arms.
No producer module, NumPy, Torch, model or optimizer import.
"""
import math
SOURCE_PROCESSOR_PIN={'bytes': 39454, 'sha256': '8118333ec7f7fe728c0c378485cd7bb6538b4fc66c2340191d25cabb7e450347'}
VALIDATOR_FUNCTION_PINS={'validate_forecast': {'bytes': 1009, 'sha256': '89d5f70f3959a44a39ec7a833060b522b83e242481874f6b76d7cf7fa788a8e0'}, 'validate_population': {'bytes': 629, 'sha256': '500bf37f5bfca8304d22fb6ef9b94992070e74a5d6a9c95c7f63c6a634ba349b'}}
ARMS=('L',)
HORIZONS=(1,3,5)
def need(ok,why):
    if not ok:raise ValueError(why)

def validate_forecast(p, require_quantiles=True):
    if p['arm'] in ARMS:numeric_evidence(p)
    required=('mean','median','nll','crps','pit')
    need(p['status']=='complete' and all(type(p[k]) is float and math.isfinite(p[k]) for k in required)
         and p['crps']>=0 and 0<=p['pit']<=1, 'forecast_fields')
    if not require_quantiles and 'quantiles' not in p:
        need(all(type(p['coverage_'+str(level)]) is bool for level in (50,80,95)), 'forecast_coverage')
        return
    q=p['quantiles']; keys=[str(x) for x in (.025,.1,.25,.5,.75,.9,.975)]
    need(type(q) is dict and set(q)==set(keys) and all(type(q[k]) is float and math.isfinite(q[k]) for k in keys)
         and all(q[a]<=q[b] for a,b in zip(keys[:-1],keys[1:])) and p['median']==q['0.5'], 'forecast_quantiles')
    for level,lo,hi in ((50,'0.25','0.75'),(80,'0.1','0.9'),(95,'0.025','0.975')):
        value=p['coverage_'+str(level)]
        need(type(value) is bool and value==bool(q[lo]<=p['target']<=q[hi]), 'forecast_coverage')


def validate_population(predictions, packet, seed, arm):
    expected=[(r['ordinal'],h) for r in packet['rows'] if r['common'] and r['partition']=='DEV' for h in HORIZONS]
    need(len(predictions)==66 and [(p['ordinal'],p['horizon']) for p in predictions]==expected, 'forecast_population')
    for p in predictions:
        row=packet['rows'][p['ordinal']]
        need(p['seed']==seed and p['arm']==arm and type(p['target']) is float and p['target']==row['mw'] and p['group']==row['group'], 'forecast_identity')
        validate_forecast(p,require_quantiles=arm not in ('B','F'))
        if arm in ARMS:numeric_evidence(p,row)


def validate_comparators(predictions,packet,seed,arm):
    need(type(seed)is int and seed in(20261012,20261013)and arm in('S','P','D','B','F','H','T'),'historical_comparator_only')
    validate_population(predictions,packet,seed,arm)
