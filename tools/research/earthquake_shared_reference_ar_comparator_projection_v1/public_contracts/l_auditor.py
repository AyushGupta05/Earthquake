"""Independent L saved-state and full-forecast audit. No producer/Torch or IO."""
import math
import time
import numpy as np
import auditor as old
import math_core as core
import ar_core as ar
import packet as pkt
import packet_digest
import transport as tx
import metrics

STUDY = 'earthquake-TRAIN115-shared-reference-AR-L-study-v1'
IDS = ((20261012, 'L'), (20261013, 'L'))
SOURCES = {'operator','native_validator','reference','kernel','processor','protocol','numeric_state'}
REPORT = 'shared-reference-AR-L-independent-audit-v1'
COMPARATORS = ('S','P','D','B','F','H','T')
stage_tick = old.stage_tick


def sources(value):
    pkt.keys(value, SOURCES)
    for pin in value.values():
        pkt.keys(pin, ('bytes','sha256'))
        core.need(type(pin['bytes']) is int and pin['bytes'] > 0, 'source_bytes')
        old.hashstr(pin['sha256'])


def authority_checked(a, aggregate=False):
    flags = ['verified','native_verified','original_initialization_verified']
    hashes = ['packet_sha256','admission_sha256','original_admission_sha256','original_execution_closure_sha256']
    extra = ['fits','closed_comparator_report_sha256','origins_sha256'] if aggregate else ['checkpoint_sha256','score_sha256']
    flags += ['comparators_verified'] if aggregate else ['optimizer_history_verified','gradient_probes_verified']
    pkt.keys(a, ['schema','source_pins','original_source_pins'] + flags + hashes + extra)
    suffix = 'aggregate' if aggregate else 'audit'
    core.need(a['schema'] == f'root-shared-reference-AR-L-{suffix}-authority-v1'
              and all(a[k] is True for k in flags), 'root_authority')
    for k in hashes + [k for k in extra if k != 'fits']:
        old.hashstr(a[k])
    sources(a['source_pins']); old.sources(a['original_source_pins'])


def admission_checked(ad, original, packet, authority):
    # Original schema/QR/active mask/all six initial states/probes are reconstructed
    # with byte-identical independently reviewed code, not a producer adapter.
    schema = old.admission_checked(original, packet, authority)
    core.need(tx.sha(original) == authority['original_admission_sha256']
              and original['source_pins'] == authority['original_source_pins'], 'original_admission_authority')
    pkt.keys(ad, ('status','study','packet_sha256','source_pins','schema','capacity','models','runtime','order',
                  'denominators','slots','original_admission_sha256','original_source_pins'))
    core.need(ad['status'] == 'admitted' and ad['study'] == STUDY and ad['order'] == [list(x) for x in IDS], 'L_admission')
    core.need(tx.sha(ad) == authority['admission_sha256'] and ad['packet_sha256'] == original['packet_sha256']
              and ad['source_pins'] == authority['source_pins']
              and ad['original_admission_sha256'] == tx.sha(original)
              and ad['original_source_pins'] == original['source_pins'], 'admission_binding')
    for role in ('operator','native_validator'):
        core.need(ad['source_pins'][role] == original['source_pins'][role], 'unchanged_role_binding')
    # L copies the original admitted schema; no refit of scalers/labels/summary mask.
    for key in ('schema','slots','denominators'):
        core.need(tx.sha(ad[key]) == tx.sha(original[key]), 'original_' + key)
    old.runtime(ad['runtime'])
    expected_capacity = dict(original['capacity'], L=original['capacity']['S'])
    core.need(ad['capacity'] == expected_capacity and all(type(x) is int for x in ad['capacity'].values())
              and max(expected_capacity.values()) <= 1.05 * min(expected_capacity.values()), 'L_capacity')
    pkt.keys(ad['models'], [str(seed)+':L' for seed, _ in IDS])
    K = len(schema['static']['kept'])
    for seed, arm in IDS:
        entry = ad['models'][str(seed)+':L']; archived = original['models'][str(seed)+':S']
        plugin = original['models'][str(seed)+':P']
        pkt.keys(entry, ('initial','initial_receipt','prior_sha256','probe','order','original_initial_sha256'))
        total = old.shape_state(entry['initial'], K, schema['summary']['active'], 'S')
        old.probe(entry['probe'], entry['initial'], total)
        core.need(total == expected_capacity['L'] and tx.sha(entry['initial']) == tx.sha(archived['initial'])
                  == tx.sha(plugin['initial']) == entry['original_initial_sha256'], 'original_initial_state')
        core.need(entry['prior_sha256'] == archived['prior_sha256']
                  and pkt.byteeq(entry['order'], archived['order']), 'original_initial_order')
        initial = dict(status='initial',study=STUDY,seed=seed,arm=arm,update=0,parameters=entry['initial'],
                       schema_sha256=tx.sha(schema),packet_sha256=ad['packet_sha256'],source_pins=ad['source_pins'],
                       prior_sha256=entry['prior_sha256'],original_admission_sha256=tx.sha(original),
                       original_initial_sha256=tx.sha(archived['initial']))
        pkt.keys(entry['initial_receipt'], ('status','sha256'))
        core.need(entry['initial_receipt'] == dict(status='durable',sha256=tx.sha(initial)), 'initial_receipt_binding')
    return schema


def checkpoint_checked(cp, ad, schema, pair, authority):
    pkt.keys(cp, ('status','study','seed','arm','update','history','admission_sha256','packet_sha256','source_pins',
                  'prior_sha256','initial_sha256','order_sha256','runtime','parameters','optimizer','current','final_probe'))
    core.need(cp['status'] == 'final' and cp['study'] == STUDY and type(cp['seed']) is int
              and (cp['seed'],cp['arm']) == pair and type(cp['update']) is int and cp['update'] == 300, 'final_checkpoint')
    core.need(cp['admission_sha256'] == tx.sha(ad) == authority['admission_sha256']
              and cp['packet_sha256'] == ad['packet_sha256'] and cp['source_pins'] == ad['source_pins'], 'checkpoint_binding')
    old.runtime(cp['runtime']); core.need(cp['runtime'] == ad['runtime'], 'runtime_binding')
    entry = ad['models'][str(pair[0])+':L']
    core.need(cp['prior_sha256'] == entry['prior_sha256'] and cp['initial_sha256'] == tx.sha(entry['initial'])
              and cp['order_sha256'] == tx.sha(entry['order']), 'initial_order_hashes')
    total = old.shape_state(cp['parameters'],len(schema['static']['kept']),schema['summary']['active'],'S')
    old.probe(cp['final_probe'], cp['parameters'], total)
    core.need(type(cp['history']) is list and len(cp['history']) == 300, 'history300')
    for i, item in enumerate(cp['history']):
        pkt.keys(item, ('update','loss','gradient_norm','ordinals'))
        core.need(type(item['update']) is int and item['update'] == i+1
                  and type(item['loss']) in (int,float) and math.isfinite(item['loss'])
                  and type(item['gradient_norm']) in (int,float) and math.isfinite(item['gradient_norm'])
                  and item['gradient_norm'] >= 0 and item['ordinals'] == entry['order'][i].tolist(), 'history_order')
    old.optimizer_checked(cp['optimizer'], cp['parameters'])
    v = cp['current']; pkt.keys(v, ('update','ordinal','horizon','loss'))
    core.need(type(v['update']) is int and v['update'] == 300 and type(v['ordinal']) is int
              and v['ordinal'] == entry['order'][-1,-1] and type(v['horizon']) is int and v['horizon'] == 5
              and type(v['loss']) in (int,float) and math.isfinite(v['loss']), 'current_last')
    core.need(tx.sha(cp) == authority['checkpoint_sha256'], 'checkpoint_authority')
    return cp['parameters']


def reconstruct(row, h, schema, parameters, budget, source=None, evidence=None):
    evidence = {} if evidence is None else evidence
    core.need(type(evidence) is dict, 'reconstruction_evidence')
    s = schema['static']; marks = row['horizons'][(1,3,5).index(h)]['reported']; nu = row['noise']['nu']
    evidence.update(raw_context=row['precontext'],parameters=parameters,static_scaler=s,
                    mref=schema['mref'],reported=marks,nu=nu,arrival_offset_ns=row['noise']['arrival_offset_ns'])
    raw = row['precontext'][s['reference_keep']]
    z, ez = core.standardize_bound(raw,np.zeros(30),s['mean'],s['std'])
    context = np.ascontiguousarray(z[s['kept']]); error = np.ascontiguousarray(ez[s['kept']])
    evidence.update(coded_context=context,context_bound=error)
    prior, bounds = core.prior_forward(context,parameters,len(s['kept']),error)
    evidence.update(prior=list(prior),prior_bounds=list(bounds))
    args = (prior,marks,parameters['coefficients'],nu,schema['mref'],h,row['noise']['arrival_offset_ns'])
    reference = ar.build_reference(*args,budget=budget); evidence['reference'] = reference
    mix = ar.complete(reference,budget)
    # Retain the once-completed independent posterior BEFORE any producer parity
    # rejection. The frozen core's combined verify_source cannot expose this
    # intermediate mixture if it raises; use its identical comparison rules here.
    evidence['posterior'] = dict(log_weights=mix.logw,means=mix.mu,scales=mix.sd,
                                log_normalizer=mix.logz,noise_probabilities=mix.noise)
    if source is not None:
        ar.keys(source, ar.SOURCE_KEYS)
        ar.check_reference(source['reference'], reference, bounds)
        errors = {}; evidence['posterior_errors'] = errors
        for key, expected in (('log_weights',mix.logw),('means',mix.mu),('scales',mix.sd),('noise_probabilities',mix.noise)):
            ar.p.array(source[key], expected.shape)
            error = np.abs(source[key]-expected); errors[key] = error
            ar.p.need(bool((error <= 1e-10*(1+np.abs(expected))).all()), 'completed_gaussian')
        value = source['log_normalizer']
        ar.p.need(type(value) is float and math.isfinite(value), 'log_normalizer')
        errors['log_normalizer'] = abs(value-mix.logz)
        ar.p.need(errors['log_normalizer'] <= 1e-4, 'log_normalizer')
    budget.tick()
    return mix, reference, bounds


def diagnostic(d):
    pkt.keys(d, ('errors','work','allpositive_only','law'))
    core.need(d['allpositive_only'] is True and d['law'] == 'shared-level-reference-AR-L-v1', 'diagnostic_law')
    pkt.keys(d['errors'], ('mean','nll','log_normalizer','crps','pit','median','quantiles'))
    for key in ('mean','nll','log_normalizer','crps','pit','median'):
        v = d['errors'][key]
        core.need(type(v) in (int,float) and math.isfinite(v) and 0 <= v <= (1e-4 if key in ('mean','nll','log_normalizer') else 1e-6),'diagnostic_error')
    pkt.keys(d['errors']['quantiles'], [str(q) for q in core.Q])
    for v in d['errors']['quantiles'].values():
        core.need(type(v) in (int,float) and math.isfinite(v) and 0 <= v <= 1e-6, 'diagnostic_quantile')
    pkt.keys(d['work'], ('density_points','scalar_terms','seconds'))
    w = d['work']
    core.need(type(w['density_points']) is int and 0 <= w['density_points'] <= 1_000_000
              and type(w['scalar_terms']) is int and w['scalar_terms'] >= 0
              and type(w['seconds']) is float and 0 <= w['seconds'] <= 10, 'diagnostic_work')


def audit_fit(score,packet,admission,original_admission,checkpoint,authority,*,processing_begin,retain=None):
 records=[];evidence=[];retention_failed=False;current=None;budget=None
 try:
  stage_tick(processing_begin);authority_checked(authority);schema=admission_checked(admission,original_admission,packet,authority);pkt.keys(score,('status','study','predictions','seed','arm','admission_sha256','packet_sha256','checkpoint_sha256','source_pins','no_optimizer','metrics'));pair=(score['seed'],score['arm']);core.need(type(pair[0])is int and type(pair[1])is str and pair in IDS and score['status']=='complete'and score['study']==STUDY and score['no_optimizer']is True and type(score['predictions'])is list and len(score['predictions'])==66,'score_complete');core.need(score['admission_sha256']==authority['admission_sha256']and score['packet_sha256']==authority['packet_sha256']and score['checkpoint_sha256']==authority['checkpoint_sha256']and tx.sha(score)==authority['score_sha256']and score['source_pins']==authority['source_pins'],'score_binding');parameters=checkpoint_checked(checkpoint,admission,schema,pair,authority)
  for position,(stored,(ordinal,h))in enumerate(zip(score['predictions'],((i,h)for i in schema['dev']for h in(1,3,5)))):
   current=dict(position=position,seed=pair[0],arm=pair[1],ordinal=ordinal,horizon=h,stored=stored);budget=None;stage_tick(processing_begin);budget=core.Budget(time.monotonic());row=packet['rows'][ordinal];pkt.keys(stored,('seed','arm','ordinal','horizon','target','group','status','mean','median','nll','crps','pit','quantiles','coverage_50','coverage_80','coverage_95','diagnostics','source'));core.need(type(stored['seed'])is int and(stored['seed'],stored['arm'])==pair and type(stored['ordinal'])is int and type(stored['horizon'])is int and(stored['ordinal'],stored['horizon'])==(ordinal,h)and type(stored['target'])in(int,float)and math.isfinite(stored['target'])and stored['target']==row['mw']and type(stored['group'])is int and stored['group']==row['group']and stored['status']=='complete','forecast_identity');current['reconstruction']={};mix,reference,bounds=reconstruct(row,h,schema,parameters,budget,source=stored['source'],evidence=current['reconstruction']);current.update(reference=reference,posterior=dict(log_weights=mix.logw,means=mix.mu,scales=mix.sd,log_normalizer=mix.logz,noise_probabilities=mix.noise),forward_bounds=list(bounds));diagnostic(stored['diagnostics']);fresh={};errors={};current.update(fresh=fresh,errors=errors);mix.scores(float(row['mw']),evidence=fresh)
   for k in('mean','median','nll','crps','pit'):
    v=stored[k];core.need(type(v)in(int,float)and math.isfinite(v),'proper_scalar');errors[k]=abs(v-fresh[k]);core.need(errors[k]<=(1e-4 if k in('mean','nll')else 1e-6),'proper_disagreement')
   pkt.keys(stored['quantiles'],[str(q)for q in core.Q])
   for q in core.Q:core.need(type(stored['quantiles'][str(q)])is float and abs(mix.cdf(stored['quantiles'][str(q)])-q)<=1e-6 and abs(stored['quantiles'][str(q)]-fresh['quantiles'][str(q)])<=1e-6,'quantile_disagreement')
   for level in(50,80,95):core.need(type(stored['coverage_'+str(level)])is bool and stored['coverage_'+str(level)]is fresh['coverage_'+str(level)],'coverage_bool')
   item=dict(seed=pair[0],arm=pair[1],ordinal=ordinal,horizon=h,target=row['mw'],group=row['group'],family='ENZ'if row['precontext'][14]==1 else'12Z',receiver=row['precontext'][8:11].tolist(),rate=row['noise']['rate'],**fresh);record=dict(position=position,status='pass',errors=errors,work=dict(density_points=budget.points,scalar_terms=budget.terms),source_sha256=tx.sha(stored['source']),fresh=item);evidence.append(record)
   if retain is not None:
    try:retain(record)
    except Exception:retention_failed=True;raise core.AuditFailure('retention_failed')
   records.append(item);budget.tick();stage_tick(processing_begin);current=None;budget=None
  panels={str(h):metrics.panel([v for v in records if v['horizon']==h])for h in(1,3,5)};core.need(old.close(score['metrics'],panels,1e-4),'stored_metrics');report=dict(schema=REPORT,status='pass',seed=pair[0],arm=pair[1],records=records,metrics=panels,strata=metrics.strata(records),checked=66,authority_sha256=tx.sha(authority),score_sha256=tx.sha(score),advance=dict(pass_all=False,checks=[]))
  if retain is not None:
   try:retain(report)
   except Exception:retention_failed=True;raise core.AuditFailure('retention_failed')
  stage_tick(processing_begin);return report
 except Exception as error:
  failure=dict(position=len(records),status='fail',reason=str(error)[:128],exception_type=type(error).__name__,current_record=current,current_work=None if budget is None else dict(density_points=budget.points,scalar_terms=budget.terms,elapsed=max(0.,time.monotonic()-budget.begin)),advance=dict(pass_all=False,checks=[]))
  if retain is not None and not retention_failed:
   try:retain(failure)
   except Exception:failure['retention_failed']=True
  return dict(schema=REPORT,status='fail',records=records,evidence=evidence,failure=failure,checked=len(records),advance=dict(pass_all=False,checks=[]))


def record_set(records, pair, packet, schema, *, quantiles):
    core.need(type(records) is list and len(records) == 66, 'records66')
    for v, (ordinal,h) in zip(records, ((i,h) for i in schema['dev'] for h in (1,3,5))):
        row = packet['rows'][ordinal]
        required = {'ordinal','horizon','target','group','mean','median','nll','crps','pit',
                    'coverage_50','coverage_80','coverage_95','family','receiver','rate'}
        core.need(type(v) is dict and required <= set(v), 'record_fields')
        core.need(type(v['ordinal']) is int and type(v['horizon']) is int and (v['ordinal'],v['horizon']) == (ordinal,h)
                  and type(v['target']) in (int,float) and v['target'] == row['mw']
                  and type(v['group']) is int and v['group'] == row['group'], 'record_roster')
        if 'seed' in v or 'arm' in v:
            core.need(type(v.get('seed')) is int and (v.get('seed'),v.get('arm')) == pair, 'record_fit')
        core.need(v['family'] == ('ENZ' if row['precontext'][14] == 1 else '12Z')
                  and v['receiver'] == row['precontext'][8:11].tolist() and v['rate'] == row['noise']['rate'], 'record_stratum')
        for k in ('mean','median','nll','crps','pit'):
            core.need(type(v[k]) in (int,float) and math.isfinite(v[k]), 'record_numeric')
        core.need(v['crps'] >= 0 and 0 <= v['pit'] <= 1, 'record_proper')
        for level in (50,80,95):
            core.need(type(v['coverage_'+str(level)]) is bool, 'record_coverage')
        if quantiles or 'quantiles' in v:
            pkt.keys(v['quantiles'], [str(q) for q in core.Q])
            core.need(all(type(x) in (int,float) and math.isfinite(x) for x in v['quantiles'].values()), 'record_quantiles')
    return dict(seed=pair[0],arm=pair[1],records=records,
                metrics={str(h):metrics.panel([r for r in records if r['horizon'] == h]) for h in (1,3,5)},
                strata=metrics.strata(records))


def comparators_checked(report, origins, packet, schema, authority):
    # Full already-closed independent report is held by ROOT, never replaced by
    # a projection's claim of verification. No old forecasts are recomputed here.
    core.need(tx.sha(report) == authority['closed_comparator_report_sha256']
              and tx.sha(origins) == authority['origins_sha256'], 'closed_comparator_bytes')
    pkt.keys(report, ('schema','status','checked','fits','stronger','paired','advance','authority_sha256'))
    core.need(report['schema'] == 'marked-sixfit-independent-aggregate-v1' and report['status'] == 'pass'
              and type(report['checked']) is int and report['checked'] == 396, 'closed_comparator_report')
    old.hashstr(report['authority_sha256'])
    expected = list(old.IDS) + [(s,a) for s in (20261012,20261013) for a in ('B','F','H','T')]
    core.need(type(report['fits']) is list and len(report['fits']) == 6
              and type(report['stronger']) is list and len(report['stronger']) == 8
              and type(origins) is list and len(origins) == 14, 'comparator_count')
    out = []
    for item, origin, pair in zip(report['fits']+report['stronger'], origins, expected):
        core.need(type(item) is dict and type(item['seed']) is int and (item['seed'],item['arm']) == pair, 'comparator_order')
        required = {'seed','arm','checkpoint_sha256','source_sha256','packet_sha256',
                    'independent_audit_sha256','origin_sha256','records_sha256'}
        core.need(type(origin) is dict and required <= set(origin) and type(origin['seed']) is int
                  and (origin['seed'],origin['arm']) == pair, 'comparator_origin')
        for key in required - {'seed','arm'}:
            old.hashstr(origin[key])
        core.need(origin['records_sha256'] == tx.sha(item['records']), 'origin_record_binding')
        fresh = record_set(item['records'],pair,packet,schema,quantiles=pair[1] not in ('B','F'))
        core.need(old.close(item['metrics'],fresh['metrics'],1e-10), 'closed_comparator_metrics')
        out.append(fresh)
    # Reproduce existing guards too; no dependence on their pass/fail for L's result.
    core.need(old.close(report['advance'],metrics.guards(out[:6],out[6:]),0.), 'closed_original_guards')
    return out


def guards(fits, comparators):
    checks = []; extra = []
    for seed,_ in IDS:
        selected = [f for f in fits if f['seed'] == seed and f['arm'] == 'L']
        others = {f['arm']:f for f in comparators if f['seed'] == seed}
        core.need(len(selected) == 1 and set(others) == set(COMPARATORS), 'all_seven_comparators')
        for h in (1,3,5):
            a = selected[0]['metrics'][str(h)]
            for arm in COMPARATORS:
                b = others[arm]['metrics'][str(h)]
                tail = a['tail_mae_5_5'] is not None and b['tail_mae_5_5'] is not None and b['tail_mae_5_5']-a['tail_mae_5_5'] >= .02
                proper = a['nll'] < b['nll'] and a['crps'] < b['crps'] if arm in ('S','P','D','B','F') else True
                bulk = {k:a[k] is not None and b[k] is not None and a[k] <= b[k]
                        for k in ('mae','medae','lower_mae','lower_medae','cvar95','maximum')}
                value = dict(seed=seed,horizon=h,comparator=arm,tail=tail,proper=proper,
                             bulk_worst=bulk,passed=tail and proper and all(bulk.values()))
                (extra if arm in ('S','P','D') else checks).append(value)
    return dict(pass_all=all(v['passed'] for v in checks+extra),checks=checks,additional=extra)


def aggregate(fit_audits, score_results, packet, admission, original_admission,
              closed_comparator_report, origins, authority, *, processing_begin, retain=None):
    retention_failed = False
    partial = dict(fits=[],comparators=[],computed_guard_outcomes=None,paired=[],current_paired=None)
    try:
        stage_tick(processing_begin); authority_checked(authority,aggregate=True)
        schema = admission_checked(admission,original_admission,packet,authority)
        core.need(type(fit_audits) is list and type(score_results) is list and type(authority['fits']) is list
                  and len(fit_audits) == len(score_results) == len(authority['fits']) == 2, 'two_complete')
        for audit,result,pair,pin in zip(fit_audits,score_results,IDS,authority['fits']):
            stage_tick(processing_begin)
            pkt.keys(pin, ('seed','arm','audit_sha256','authority_sha256','score_sha256','checkpoint_sha256'))
            core.need(type(pin['seed']) is int and (pin['seed'],pin['arm']) == pair, 'aggregate_fit_identity')
            for k in ('audit_sha256','authority_sha256','score_sha256','checkpoint_sha256'):
                old.hashstr(pin[k])
            core.need(audit['schema'] == REPORT and audit['status'] == 'pass' and type(audit['checked']) is int
                      and audit['checked'] == 66 and (audit['seed'],audit['arm']) == pair
                      and tx.sha(audit) == pin['audit_sha256'] and audit['authority_sha256'] == pin['authority_sha256']
                      and audit['score_sha256'] == pin['score_sha256'] == tx.sha(result)
                      and result['checkpoint_sha256'] == pin['checkpoint_sha256'], 'aggregate_audit_custody')
            core.need(result['status'] == 'complete' and result['study'] == STUDY and result['no_optimizer'] is True
                      and (result['seed'],result['arm']) == pair and result['source_pins'] == authority['source_pins']
                      and result['packet_sha256'] == authority['packet_sha256']
                      and result['admission_sha256'] == authority['admission_sha256'], 'aggregate_score_binding')
            partial['fits'].append(record_set(audit['records'],pair,packet,schema,quantiles=True))
        partial['comparators'] = comparators_checked(closed_comparator_report,origins,packet,schema,authority)
        advance = guards(partial['fits'],partial['comparators']); partial['computed_guard_outcomes'] = advance
        for fit in partial['fits']:
            for arm in COMPARATORS:
                comparator = next(v for v in partial['comparators'] if v['seed'] == fit['seed'] and v['arm'] == arm)
                for h in (1,3,5):
                    current = dict(seed=fit['seed'],horizon=h,comparator=arm,bootstrap={})
                    partial['current_paired'] = current
                    intervals = metrics.paired([v for v in fit['records'] if v['horizon'] == h],
                                               [v for v in comparator['records'] if v['horizon'] == h],
                                               lambda:stage_tick(processing_begin),evidence=current['bootstrap'])
                    partial['paired'].append(dict(seed=fit['seed'],horizon=h,comparator=arm,
                                                  role='mechanistic' if arm == 'S' else 'descriptive',metrics=intervals))
                    partial['current_paired'] = None
        report = dict(schema='shared-reference-AR-L-independent-aggregate-v1',status='pass',checked=132,
                      record_counts=dict(new_L=132,reused_SPD=396,reused_BFHT=528,total=1056),
                      fits=partial['fits'],comparators=partial['comparators'],origins=origins,
                      closed_comparator_report_sha256=authority['closed_comparator_report_sha256'],
                      paired=partial['paired'],advance=advance,authority_sha256=tx.sha(authority))
        if retain is not None:
            try:
                retain(report)
            except Exception:
                retention_failed=True; raise core.AuditFailure('retention_failed')
        stage_tick(processing_begin); return report
    except Exception as error:
        failure = dict(schema='shared-reference-AR-L-independent-aggregate-v1',status='fail',reason=str(error)[:128],
                       exception_type=type(error).__name__,partial=partial,advance=dict(pass_all=False,checks=[],additional=[]))
        if retain is not None and not retention_failed:
            try:
                retain(failure)
            except Exception:
                failure['retention_failed']=True
        return failure
