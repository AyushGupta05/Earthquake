"""Scalar-only public projection of a positively closed independent audit.

No IO, notebook execution, provider access or scientific fitting/scoring.
"""
import hashlib
import json
import math

SEEDS=(20261012,20261013)
H=(1,3,5)
NEW=tuple((s,a)for s in SEEDS for a in('S','P','D'))
OLD=tuple((s,a)for s in SEEDS for a in('B','F','H','T'))
PANEL=('n','nll','crps','mae','medae','tail_mae_5_5','tail_mae_6','lower_mae','lower_medae','tail_bias','cvar95','maximum','p95','median_mae','coverage_50','coverage_80','coverage_95')
COUNTS=dict(slots=115,horizons=345,common_train=65,common_dev=22,new_fits=6,stronger_fits=8,new_forecasts=396,stronger_forecasts=528)
BULK=('mae','medae','lower_mae','lower_medae','cvar95','maximum')

def need(v,why):
    if not v:raise ValueError(why)
def keys(v,names):need(type(v)is dict and set(v)==set(names),'keys')
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def pin(v):return dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest())
def digest(v):need(type(v)is str and len(v)==64 and all(c in'0123456789abcdef'for c in v),'digest')
def pincheck(v,cap):
    keys(v,('bytes','sha256'));need(type(v['bytes'])is int and 0<v['bytes']<=cap,'pin_bytes');digest(v['sha256'])
def numeric(v):return type(v)in(int,float)and math.isfinite(v)
def parse(raw,cap):
    need(type(raw)is bytes and len(raw)<=cap,'input_cap')
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate');out[k]=v
        return out
    obj=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in()).throw(ValueError('nonfinite')));need(canonical(obj)==raw,'canonical');return obj

def panels(v):
    keys(v,[str(h)for h in H]);out={}
    for h in H:
        p=v[str(h)];keys(p,PANEL);need(type(p['n'])is int and p['n']==22,'panel_n')
        for k in PANEL:
            if k=='n':continue
            optional=k in('tail_mae_5_5','tail_mae_6','lower_mae','lower_medae','tail_bias')
            need(p[k]is None and optional or numeric(p[k]),'metric_scalar')
            if p[k]is not None and k not in('nll','tail_bias'):need(p[k]>=0,'metric_nonnegative')
            if k.startswith('coverage_'):need(0<=p[k]<=1,'coverage')
        out[str(h)]={k:p[k]for k in PANEL}
    return out

def expected_guard(seed,h,arm,s,b):
    tail=s['tail_mae_5_5']is not None and b['tail_mae_5_5']is not None and b['tail_mae_5_5']-s['tail_mae_5_5']>=.02
    proper=s['nll']<b['nll']and s['crps']<b['crps']if arm in('B','F','P','D')else True
    bulk={k:s[k]is not None and b[k]is not None and s[k]<=b[k]for k in BULK}
    return dict(seed=seed,horizon=h,comparator=arm,tail=tail,proper=proper,bulk_worst=bulk,passed=tail and proper and all(bulk.values()))

def prepare_public(report_raw,closure_raw,expected_closure_pin):
    """expected_closure_pin MUST be ROOT-held independently verified authority.

    Never derive it from caller flags or incoming closure bytes; ROOT verifies all
    actual manager returns/empty units, stopped timer and read-only fetch separately.
    """
    pincheck(expected_closure_pin,1024*1024);need(pin(closure_raw)==expected_closure_pin,'root_closure_pin');closed=parse(closure_raw,1024*1024)
    keys(closed,('schema','status','aggregate_pin','stages','whole_stop_verified','readonly_fetch_verified','counts','dev_roster_sha256'))
    need(closed['schema']=='root-shared-noise-reporting-closure-v1' and closed['status']=='complete' and closed['whole_stop_verified']is True and closed['readonly_fetch_verified']is True,'root_not_closed');need(closed['counts']==COUNTS and all(type(v)is int for v in closed['counts'].values()),'counts');digest(closed['dev_roster_sha256'])
    pincheck(closed['aggregate_pin'],16*1024*1024);need(pin(report_raw)==closed['aggregate_pin'],'aggregate_pin')
    need(type(closed['stages'])is list and len(closed['stages'])==7,'seven_stages')
    for i,stage in enumerate(closed['stages']):
        keys(stage,('index','status','unit_inactive','cgroup_empty','checked','report_pin','closed_pin','root_evidence_pin'))
        need(type(stage['index'])is int and stage['index']==i and stage['status']=='complete' and stage['unit_inactive']is True and stage['cgroup_empty']is True and type(stage['checked'])is int and stage['checked']==(66 if i<6 else 396),'stage_closed')
        for k in('report_pin','closed_pin','root_evidence_pin'):pincheck(stage[k],16*1024*1024)
    need(closed['stages'][6]['report_pin']==closed['aggregate_pin'],'stage6_report_pin')
    report=parse(report_raw,16*1024*1024);keys(report,('schema','status','checked','fits','stronger','paired','advance','authority_sha256'))
    need(report['schema']=='marked-sixfit-independent-aggregate-v1' and report['status']=='pass' and type(report['checked'])is int and report['checked']==396,'aggregate_incomplete');digest(report['authority_sha256'])
    public={};roster=None
    for name,order in(('fits',NEW),('stronger',OLD)):
        fits=report[name];need(type(fits)is list and len(fits)==len(order),'fit_count');rows=[]
        for fit,pair in zip(fits,order):
            keys(fit,('seed','arm','records','metrics','strata')if name=='fits'else('seed','arm','records','metrics'))
            need(type(fit['seed'])is int and (fit['seed'],fit['arm'])==pair and type(fit['records'])is list and len(fit['records'])==66,'fit_identity')
            cohort=[]
            for j in range(22):
                group=fit['records'][3*j:3*j+3];first=group[0];need(type(first['ordinal'])is int and type(first['group'])is int and numeric(first['target']),'cohort_types');event={k:first[k]for k in('ordinal','target','group')};cohort.append(event)
                for record,h in zip(group,H):need(type(record['horizon'])is int and record['horizon']==h and all(type(record[k])is type(first[k])and record[k]==first[k]for k in event),'cohort_horizons')
            need(len({r['ordinal']for r in cohort})==22 and pin(canonical(cohort))['sha256']==closed['dev_roster_sha256'],'cohort_pin')
            if roster is None:roster=cohort
            need(cohort==roster,'same_cohort');rows.append(dict(seed=pair[0],arm=pair[1],metrics=panels(fit['metrics'])))
        public[name]=rows
    expected=[];extra=[];lookup={(r['seed'],r['arm']):r['metrics']for name in('fits','stronger')for r in public[name]}
    for seed in SEEDS:
        for h in H:
            for arm in('B','F','H','T','P','D'):
                item=expected_guard(seed,h,arm,lookup[seed,'S'][str(h)],lookup[seed,arm][str(h)]);(extra if arm in('P','D')else expected).append(item)
    advance=report['advance'];keys(advance,('pass_all','checks','additional'));
    for name in('checks','additional'):
        need(type(advance[name])is list,'guard_list')
        for item in advance[name]:
            keys(item,('seed','horizon','comparator','tail','proper','bulk_worst','passed'));need(type(item['seed'])is int and type(item['horizon'])is int and all(type(item[k])is bool for k in('tail','proper','passed')),'guard_types');keys(item['bulk_worst'],BULK);need(all(type(v)is bool for v in item['bulk_worst'].values()),'bulk_types')
    need(type(advance['pass_all'])is bool and advance['checks']==expected and advance['additional']==extra and advance['pass_all']==all(v['passed']for v in expected+extra),'guard_cohort_or_outcome')
    paired=report['paired'];triples=[(s,h,a)for s in SEEDS for a in('B','F','H','T','P','D')for h in H];need(type(paired)is list and len(paired)==36,'paired36');intervals=[]
    for item,triple in zip(paired,triples):
        keys(item,('seed','horizon','comparator','metrics'));need(type(item['seed'])is int and type(item['horizon'])is int and(item['seed'],item['horizon'],item['comparator'])==triple,'paired_identity');keys(item['metrics'],[k for k in PANEL if k!='n']);clean={}
        for key,value in item['metrics'].items():
            keys(value,('status','groups','delta','interval'));need(type(value['groups'])is int and 0<=value['groups']<=22 and(value['delta']is None or numeric(value['delta'])),'interval_scalar');need(value['status']in('descriptive','unsupported'),'interval_status')
            if value['status']=='descriptive':need(value['groups']>=3 and type(value['interval'])is list and len(value['interval'])==2 and all(numeric(x)for x in value['interval'])and value['interval'][0]<=value['interval'][1],'interval')
            else:need(value['interval']is None,'unsupported_interval')
            clean[key]={k:value[k]for k in('status','groups','delta','interval')}
        intervals.append(dict(seed=triple[0],horizon=triple[1],comparator=triple[2],metrics=clean))
    summary=dict(schema='shared-noise-public-summary-v1',study='earthquake-TRAIN115-marked-noise-fitting-v2',counts=dict(COUNTS),fits=public['fits'],stronger=public['stronger'],advance=dict(pass_all=advance['pass_all'],checks=expected,additional=extra),paired=intervals,provenance=dict(aggregate_sha256=closed['aggregate_pin']['sha256'],root_closure_sha256=expected_closure_pin['sha256']),limitations='Exploratory reused DEV cohort; descriptive group bootstrap; no novelty, matched published-benchmark superiority or independent generalization claim.')
    return dict(summary=summary,markdown=markdown(summary))

def metric_table(summary):
    lines=['| Seed | Arm | Seconds | High ≥5.5 MAE | Mean MAE | Mean MedAE | Lower MAE | Lower MedAE | CVaR95 | Max | NLL | CRPS | Median-action MAE |','|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    def fmt(v):return 'unsupported'if v is None else format(v,'.4f')
    for fit in summary['fits']+summary['stronger']:
        for h in H:
            p=fit['metrics'][str(h)];fields=('tail_mae_5_5','mae','medae','lower_mae','lower_medae','cvar95','maximum','nll','crps','median_mae');lines.append('| '+' | '.join([str(fit['seed']),fit['arm'],str(h)]+[fmt(p[k])for k in fields])+' |')
    return '\n'.join(lines)

def guard_table(summary):
    lines=['| Seed | Seconds | Comparator | Tail | Proper | Bulk and worst | Overall |','|---|---|---|---|---|---|---|']
    for r in summary['advance']['checks']+summary['advance']['additional']:
        yn=lambda v:'pass'if v else'fail';lines.append('| '+' | '.join([str(r['seed']),str(r['horizon']),r['comparator'],yn(r['tail']),yn(r['proper']),yn(all(r['bulk_worst'].values())),yn(r['passed'])])+' |')
    return '\n'.join(lines)

def markdown(summary):
    checks=summary['advance']['checks']+summary['advance']['additional'];passed=sum(r['passed']for r in checks);result='passed'if summary['advance']['pass_all']else'did not pass'
    return 'The shared-noise S method '+result+' the fixed advancement gate ('+str(passed)+'/36 checks passed). Every horizon, seed and comparator remains a separate required check.\n\nThe completed independent audit covers six new fits and 396 forecasts on the same 22 DEV events at 1/3/5 seconds; eight previously audited comparators contribute 528 forecasts. S=shared reference support, P=zero-nuisance plug-in, D=direct summary distribution. The current S loading is1 in every conditional factor.\n\nErrors use the posterior mean action except the separate posterior-median-action MAE column. High means target Mw≥5.5; lower means Mw<5.5. Natural-cohort MAE and MedAE, lower error, CVaR95 and maximum each remain guarded.\n\n'+metric_table(summary)+'\n\n'+guard_table(summary)+'\n\n'+summary['limitations']+' The paired intervals in the public summary are descriptive; unsupported intervals stay absent. A negative gate is retained, not averaged into success.\n'
