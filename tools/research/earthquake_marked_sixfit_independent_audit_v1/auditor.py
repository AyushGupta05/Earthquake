"""Pure independent per-fit S/P/D saved-state/proper-score audit, no IO/models."""
import math
import time
import numpy as np
from scipy.special import logsumexp
import math_core as core
import packet as pkt
import transport as tx
import metrics

STUDY='earthquake-TRAIN115-marked-noise-fitting-v2'
IDS=tuple((s,a)for s in(20261012,20261013)for a in('S','P','D'))
SOURCES={'operator','native_validator','reference','processor','protocol'}


def stage_tick(begin):
 now=time.monotonic();core.need(type(begin)in(int,float)and math.isfinite(begin)and 0<=begin<=now and now-begin<=900,'stage_deadline')
def hashstr(v):core.need(type(v)is str and len(v)==64 and all(c in'0123456789abcdef'for c in v),'sha256')
def sources(v):
 pkt.keys(v,SOURCES)
 for pin in v.values():pkt.keys(pin,('bytes','sha256'));core.need(type(pin['bytes'])is int and pin['bytes']>0,'source_bytes');hashstr(pin['sha256'])

def close(a,b,tol=1e-10):
 if type(b)is np.ndarray:return type(a)is np.ndarray and a.dtype==b.dtype and a.shape==b.shape and np.isfinite(a).all()and bool(np.all(np.abs(a-b)<=tol*(1+np.abs(b))))
 if type(b)is dict:return type(a)is dict and set(a)==set(b)and all(close(a[k],v,tol)for k,v in b.items())
 if type(b)is list:return type(a)is list and len(a)==len(b)and all(close(x,y,tol)for x,y in zip(a,b))
 if type(b)is float:return type(a)in(int,float)and math.isfinite(a)and abs(a-b)<=tol*(1+abs(b))
 return type(a)is type(b)and a==b

def runtime(v):
 pkt.keys(v,('torch','numpy','threads','dtype','device'));core.need(all(type(v[k])is str and v[k] for k in('torch','numpy','dtype','device'))and type(v['threads'])is int and v['threads']==1 and v['dtype']=='float64'and v['device']=='cpu','runtime')

def shape_state(parameters,K,active,arm):
 shapes={'prior.second.weight':(16,16),'prior.second.bias':(16,),'prior.head.weight':(14,16),'prior.head.bias':(14,)}
 if K:shapes.update({'prior.first.weight':(16,K),'prior.first.bias':(16,)})
 else:shapes['prior.first_bias']=(16,)
 shapes.update({'coefficients':(3,6)}if arm in('S','P')else{'theta':(len(active),),'tau':()});pkt.keys(parameters,shapes)
 # Raw saved NN parameters are finite/shape-bound; operator inputs/outputs have separate domains.
 for k,shape in shapes.items():core.array(parameters[k],shape)
 return sum(math.prod(shape)for shape in shapes.values())

def probe(v,parameters,total):
 pkt.keys(v,('events','horizons','terms','used','total','masks','maximum_event_gradient_norm'));core.need(all(type(v[k])is int and v[k]==n for k,n in(('events',65),('horizons',3),('terms',195),('used',total),('total',total))),'probe_count');pkt.keys(v['masks'],parameters);pkt.keys(v['maximum_event_gradient_norm'],parameters)
 for k,a in parameters.items():
  mask=v['masks'][k];core.need(type(mask)is np.ndarray and mask.dtype==np.uint8 and mask.shape==a.shape and bool(np.all(mask==1)),'probe_mask');norm=v['maximum_event_gradient_norm'][k];core.need(type(norm)in(int,float)and math.isfinite(norm)and norm>0,'probe_norm')

def admission_checked(admission,p,authority):
 pkt.keys(admission,('status','study','packet_sha256','source_pins','schema','capacity','models','runtime','order','denominators','slots'));core.need(admission['status']=='admitted'and admission['study']==STUDY,'admission');sources(admission['source_pins']);runtime(admission['runtime']);roles=pkt.validate(p);schema=pkt.schema(p,roles);core.need(close(admission['schema'],schema),'TRAIN_schema');scalers_checked(admission['schema'],schema,p,roles);reconstruction_checked(admission['schema']['static'],p,roles);core.need(admission['packet_sha256']==tx.sha(p)and admission['packet_sha256']==authority['packet_sha256'],'packet_binding');core.need(admission['denominators']==p['denominators']and type(admission['slots'])is list and len(admission['slots'])==115,'slots')
 expected=[[s,a]for s,a in IDS];core.need(admission['order']==expected,'six_order');K=len(schema['static']['kept']);q=len(schema['summary']['active']);capacity={'S':16*K+544,'P':16*K+544,'D':16*K+527+q};core.need(admission['capacity']==capacity and all(type(v)is int for v in admission['capacity'].values())and max(capacity.values())<=1.05*min(capacity.values()),'capacity');pkt.keys(admission['models'],[str(s)+':'+a for s,a in IDS]);priors={}
 for seed,arm in IDS:
  m=admission['models'][str(seed)+':'+arm];pkt.keys(m,('initial','initial_receipt','prior_sha256','probe','order'));total=shape_state(m['initial'],K,schema['summary']['active'],arm);probe(m['probe'],m['initial'],total);prior={k[6:]:v for k,v in m['initial'].items()if k.startswith('prior.')};hashstr(m['prior_sha256']);core.need(m['prior_sha256']==tx.sha(prior),'initial_prior_hash');core.need(seed not in priors or tx.sha(priors[seed])==tx.sha(prior),'cloned_prior');priors[seed]=prior;order=m['order'];core.need(type(order)is np.ndarray and order.dtype==np.int64 and order.shape==(300,8),'event_order');rng=np.random.default_rng(seed+1009);expected_order=np.asarray([rng.choice(roles['TRAIN'],8,replace=False)for _ in range(300)],dtype=np.int64);core.need(pkt.byteeq(order,expected_order),'TRAIN_event_order');receipt=m['initial_receipt'];pkt.keys(receipt,('status','sha256'));core.need(receipt['status']=='durable','initial_receipt');hashstr(receipt['sha256']);initial=dict(status='initial',study=STUDY,seed=seed,arm=arm,update=0,parameters=m['initial'],schema_sha256=tx.sha(admission['schema']),packet_sha256=tx.sha(p),source_pins=admission['source_pins'],prior_sha256=m['prior_sha256']);core.need(receipt['sha256']==tx.sha(initial),'initial_receipt_binding')
 for slot,row in zip(admission['slots'],p['rows']):
  pkt.keys(slot,('ordinal','partition','common','status','horizons'));core.need(slot['horizons']==[dict(seconds=h['seconds'],status=h['status'])for h in row['horizons']],'slot_horizons');core.need(type(slot['ordinal'])is int and slot['ordinal']==row['ordinal']and slot['partition']==row['partition']and slot['common']is row['common']and slot['status']==row['status'],'slot_binding')
 return admission['schema']

def authority_checked(a):
 pkt.keys(a,('schema','verified','native_verified','optimizer_history_verified','gradient_probes_verified','stronger_verified','packet_sha256','admission_sha256','checkpoint_sha256','score_sha256','source_pins','stronger_closure_sha256'));core.need(a['schema']=='root-marked-sixfit-independent-authority-v1'and all(a[k]is True for k in('verified','native_verified','optimizer_history_verified','gradient_probes_verified','stronger_verified')),'root_authority')
 for k in('packet_sha256','admission_sha256','checkpoint_sha256','score_sha256','stronger_closure_sha256'):hashstr(a[k])
 sources(a['source_pins'])

def checkpoint_checked(cp,admission,schema,pair,authority):
 pkt.keys(cp,('status','study','seed','arm','update','history','admission_sha256','packet_sha256','source_pins','prior_sha256','initial_sha256','order_sha256','runtime','parameters','optimizer','current','final_probe'));core.need(cp['status']=='final'and cp['study']==STUDY and type(cp['seed'])is int and type(cp['arm'])is str and(cp['seed'],cp['arm'])==pair and type(cp['update'])is int and cp['update']==300,'final_checkpoint');core.need(cp['admission_sha256']==tx.sha(admission)==authority['admission_sha256']and cp['packet_sha256']==admission['packet_sha256']and cp['source_pins']==admission['source_pins']==authority['source_pins'],'checkpoint_binding');runtime(cp['runtime']);core.need(cp['runtime']==admission['runtime'],'runtime_binding');entry=admission['models'][str(pair[0])+':'+pair[1]];core.need(cp['prior_sha256']==entry['prior_sha256']and cp['initial_sha256']==tx.sha(entry['initial'])and cp['order_sha256']==tx.sha(entry['order']),'initial_order_hashes');total=shape_state(cp['parameters'],len(schema['static']['kept']),schema['summary']['active'],pair[1]);probe(cp['final_probe'],cp['parameters'],total);core.need(type(cp['history'])is list and len(cp['history'])==300,'history300')
 for i,item in enumerate(cp['history']):
  pkt.keys(item,('update','loss','gradient_norm','ordinals'));core.need(type(item['update'])is int and item['update']==i+1 and type(item['loss'])in(int,float)and math.isfinite(item['loss'])and type(item['gradient_norm'])in(int,float)and math.isfinite(item['gradient_norm'])and item['gradient_norm']>=0 and item['ordinals']==entry['order'][i].tolist(),'history_order')
 optimizer_checked(cp['optimizer'],cp['parameters']);pkt.keys(cp['current'],('update','ordinal','horizon','loss'));core.need(type(cp['current']['update'])is int and cp['current']['update']==300 and type(cp['current']['ordinal'])is int and type(cp['current']['horizon'])is int and cp['current']['ordinal']==entry['order'][-1,-1]and cp['current']['horizon']==5 and type(cp['current']['loss'])in(int,float)and math.isfinite(cp['current']['loss']),'current_last');core.need(tx.sha(cp)==authority['checkpoint_sha256'],'checkpoint_authority');return cp['parameters']

def reconstruct(row,h,schema,parameters,arm,budget,evidence=None):
 evidence={}if evidence is None else evidence;core.need(type(evidence)is dict,'reconstruction_evidence');evidence.update(raw_context=row['precontext'],parameters=parameters,static_scaler=schema['static'],summary_scaler=schema['summary'],mref=schema['mref'],reported=row['horizons'][(1,3,5).index(h)]['reported'],nu=row['noise']['nu'])
 K=len(schema['static']['kept']);s=schema['static'];raw=row['precontext'][s['reference_keep']];z,ez=core.standardize_bound(raw,np.zeros(30),s['mean'],s['std']);context=np.ascontiguousarray(z[s['kept']],dtype=np.float64);evidence.update(coded_context=context,context_bound=np.ascontiguousarray(ez[s['kept']]));prior,bounds=core.prior_forward(context,parameters,K,np.ascontiguousarray(ez[s['kept']]));evidence.update(prior=list(prior),prior_bounds=list(bounds));marks=row['horizons'][(1,3,5).index(h)]['reported'];nu=row['noise']['nu'];facts=[]
 if arm in('S','P'):
  evidence['facts']=facts;core.factors(marks,parameters['coefficients'],schema['mref'],evidence=facts);reference=dict(prior=list(prior),facts=facts,nu=nu,arm=arm);evidence['reference']=reference;mix=core.complete(prior,facts,nu,arm,budget)
 else:
  st=schema['summary'];rawsummary=core.summaries(marks,nu);evidence['raw_summary']=rawsummary;theta=parameters['theta'];shift,shift_error=core.direct_shift(rawsummary,core.summary_error(marks,nu),st,theta);evidence.update(shift=shift,shift_bound=shift_error);tau=float(parameters['tau']);core.need(math.isfinite(shift)and math.isfinite(tau)and abs(tau)<=1e6,'direct_domain');factor=math.exp(tau);logw,mu,sd=prior;newmu=mu+shift;newsd=.05+factor*(sd-.05);bounds=(bounds[0],bounds[1]+shift_error+16*core.EPS*(1+np.abs(mu)+abs(shift)),factor*bounds[2]+32*core.EPS*(1+np.abs(newsd)));prior=(logw,newmu,newsd)
  for v,e in zip(prior,bounds):core.bound_ok(v,e);core.need(bool((np.abs(v)<=1e6).all()),'prior_output_domain')
  reference=dict(prior=list(prior),facts=[],nu=np.zeros((12,3)),arm='P');evidence.update(reference=reference,direct_prior=list(prior),direct_bounds=list(bounds));mix=core.Mixture(*prior,budget=budget)
 return mix,reference,bounds

def source_checked(source,mix,reference,bounds,factor_bounds=None):
 pkt.keys(source,('reference','log_weights','means','scales','log_normalizer','noise_probabilities'));pkt.keys(source['reference'],('prior','facts','nu','arm'));saved=source['reference'];core.need(type(saved['prior'])is list and len(saved['prior'])==3 and type(saved['facts'])is list and len(saved['facts'])==len(reference['facts'])and saved['arm']==reference['arm'],'reference_fields')
 for v,expected,error in zip(saved['prior'],reference['prior'],bounds):core.compare(v,expected,error)
 core.need(pkt.byteeq(saved['nu'],reference['nu']),'native_noise_support')
 for j,(actual,expected) in enumerate(zip(saved['facts'],reference['facts'])):
  core.need(type(actual)is list and len(actual)==4,'factor_fields')
  for k,(a,b)in enumerate(zip(actual,expected)):core.compare(a,b,32*core.EPS*(1+np.abs(b))if factor_bounds is None else factor_bounds[j][k])
 for k,b in(('log_weights',mix.logw),('means',mix.mu),('scales',mix.sd)):core.need(close(source[k],b,1e-10),'completed_gaussian')
 core.need(type(source['log_normalizer'])is float and abs(source['log_normalizer']-mix.logz)<=1e-4,'log_normalizer')
 if mix.noise is None:core.need(source['noise_probabilities']is None,'noise_probability_null')
 else:core.need(close(source['noise_probabilities'],mix.noise,1e-10),'noise_probability')

def diagnostic(d):
 pkt.keys(d,('errors','work','allpositive_only','reference_reserved_points','reference_actual_points'));core.need(d['allpositive_only']is True and type(d['reference_reserved_points'])is int and d['reference_reserved_points']==240 and type(d['reference_actual_points'])is int and 0<=d['reference_actual_points']<=240,'diagnostic');pkt.keys(d['errors'],('mean','nll','log_normalizer','crps','pit'))
 for k,v in d['errors'].items():core.need(type(v)in(int,float)and math.isfinite(v)and 0<=v<=(1e-6 if k in('crps','pit')else 1e-4),'diagnostic_error')
 pkt.keys(d['work'],('density_points','scalar_terms','seconds'));core.need(type(d['work']['density_points'])is int and 0<=d['work']['density_points']<=1_000_000 and type(d['work']['scalar_terms'])is int and d['work']['scalar_terms']>=0 and type(d['work']['seconds'])is float and 0<=d['work']['seconds']<=10,'diagnostic_work')

def audit_fit(score,packet,admission,checkpoint,authority,*,processing_begin,retain=None):
 records=[];evidence=[];retention_failed=False;current=None;budget=None
 try:
  stage_tick(processing_begin);authority_checked(authority);schema=admission_checked(admission,packet,authority);pkt.keys(score,('status','study','predictions','seed','arm','admission_sha256','packet_sha256','checkpoint_sha256','source_pins','no_optimizer','metrics'));pair=(score['seed'],score['arm']);core.need(type(pair[0])is int and type(pair[1])is str and pair in IDS and score['status']=='complete'and score['study']==STUDY and score['no_optimizer']is True and type(score['predictions'])is list and len(score['predictions'])==66,'score_complete');core.need(score['admission_sha256']==authority['admission_sha256']and score['packet_sha256']==authority['packet_sha256']and score['checkpoint_sha256']==authority['checkpoint_sha256']and tx.sha(score)==authority['score_sha256']and score['source_pins']==authority['source_pins'],'score_binding');parameters=checkpoint_checked(checkpoint,admission,schema,pair,authority)
  for position,(stored,(ordinal,h))in enumerate(zip(score['predictions'],((i,h)for i in schema['dev']for h in(1,3,5)))):
   current=dict(position=position,seed=pair[0],arm=pair[1],ordinal=ordinal,horizon=h,stored=stored);budget=None;stage_tick(processing_begin);budget=core.Budget(time.monotonic());row=packet['rows'][ordinal];pkt.keys(stored,('seed','arm','ordinal','horizon','target','group','status','mean','median','nll','crps','pit','quantiles','coverage_50','coverage_80','coverage_95','diagnostics','source'));core.need(type(stored['seed'])is int and(stored['seed'],stored['arm'])==pair and type(stored['ordinal'])is int and type(stored['horizon'])is int and(stored['ordinal'],stored['horizon'])==(ordinal,h)and type(stored['target'])in(int,float)and math.isfinite(stored['target'])and stored['target']==row['mw']and type(stored['group'])is int and stored['group']==row['group']and stored['status']=='complete','forecast_identity');current['reconstruction']={};mix,reference,bounds=reconstruct(row,h,schema,parameters,pair[1],budget,evidence=current['reconstruction']);current.update(reference=reference,posterior=dict(log_weights=mix.logw,means=mix.mu,scales=mix.sd,log_normalizer=mix.logz,noise_probabilities=mix.noise),forward_bounds=list(bounds));factor_bounds=affine_bounds(row['horizons'][(1,3,5).index(h)]['reported'],parameters['coefficients'],schema['mref'])if pair[1]in('S','P')else None;source_checked(stored['source'],mix,reference,bounds,factor_bounds);diagnostic(stored['diagnostics']);fresh={};errors={};current.update(fresh=fresh,errors=errors);mix.scores(float(row['mw']),evidence=fresh)
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
  panels={str(h):metrics.panel([v for v in records if v['horizon']==h])for h in(1,3,5)};core.need(close(score['metrics'],panels,1e-4),'stored_metrics');report=dict(schema='marked-sixfit-independent-audit-v1',status='pass',seed=pair[0],arm=pair[1],records=records,metrics=panels,strata=metrics.strata(records),checked=66,authority_sha256=tx.sha(authority),score_sha256=tx.sha(score),advance=dict(pass_all=False,checks=[]));stage_tick(processing_begin);return report
 except Exception as error:
  failure=dict(position=len(records),status='fail',reason=str(error)[:128],exception_type=type(error).__name__,current_record=current,current_work=None if budget is None else dict(density_points=budget.points,scalar_terms=budget.terms,elapsed=max(0.,time.monotonic()-budget.begin)),advance=dict(pass_all=False,checks=[]))
  if retain is not None and not retention_failed:
   try:retain(failure)
   except Exception:failure['retention_failed']=True
  return dict(schema='marked-sixfit-independent-audit-v1',status='fail',records=records,evidence=evidence,failure=failure,checked=len(records),advance=dict(pass_all=False,checks=[]))

def optimizer_checked(value,parameters):
 pkt.keys(value,[str(i)for i in range(len(parameters))])
 # Root authenticates optimizer event truth; state is retained and never loaded.
 prior_names=['prior.first.weight','prior.first.bias']if 'prior.first.weight'in parameters else['prior.first_bias'];prior_names+=['prior.second.weight','prior.second.bias','prior.head.weight','prior.head.bias'];names=(['coefficients']if 'coefficients'in parameters else['theta','tau'])+prior_names
 for i,name in enumerate(names):
  entry=value[str(i)];parameter=parameters[name]
  pkt.keys(entry,('step','exp_avg','exp_avg_sq'));step=entry['step'];core.need(type(step)is np.ndarray and step.dtype in(np.dtype('float32'),np.dtype('float64'))and step.shape==()and float(step)==300.,'optimizer_step');core.array(entry['exp_avg'],parameter.shape);core.array(entry['exp_avg_sq'],parameter.shape);core.need(bool((entry['exp_avg_sq']>=0).all()),'optimizer_square')

def stronger_checked(stronger,packet,schema,authority,partial=None):
 core.need(type(stronger)is list and len(stronger)==8,'stronger_count');expected=[(s,a)for s in(20261012,20261013)for a in('B','F','H','T')];out=[]if partial is None else partial['stronger']
 for item,pair in zip(stronger,expected):
  if partial is not None:partial['current_stronger']=dict(seed=pair[0],arm=pair[1],records=[])
  pkt.keys(item,('seed','arm','predictions','closure'));core.need(type(item['seed'])is int and type(item['arm'])is str and(item['seed'],item['arm'])==pair,'stronger_identity');c=item['closure'];pkt.keys(c,('verified','no_optimizer','checkpoint_sha256','source_sha256','packet_sha256','independent_audit_sha256'));core.need(c['verified']is True and c['no_optimizer']is True,'stronger_closed')
  for key in('checkpoint_sha256','source_sha256','packet_sha256','independent_audit_sha256'):hashstr(c[key])
  core.need(type(item['predictions'])is list and len(item['predictions'])==66,'stronger_66');records=[]if partial is None else partial['current_stronger']['records']
  for v,(ordinal,h)in zip(item['predictions'],((i,h)for i in schema['dev']for h in(1,3,5))):
   required={'ordinal','horizon','target','group','mean','median','nll','crps','pit','coverage_50','coverage_80','coverage_95'};core.need(type(v)is dict and required<=set(v),'stronger_fields');row=packet['rows'][ordinal];core.need(type(v['ordinal'])is int and type(v['horizon'])is int and(v['ordinal'],v['horizon'])==(ordinal,h)and type(v['target'])in(int,float)and v['target']==row['mw']and type(v['group'])is int and v['group']==row['group'],'stronger_roles')
   for k in('target','mean','median','nll','crps','pit'):core.need(type(v[k])in(int,float)and math.isfinite(v[k]),'stronger_numeric')
   core.need(v['crps']>=0 and 0<=v['pit']<=1,'stronger_proper')
   for level in(50,80,95):core.need(type(v['coverage_'+str(level)])is bool,'stronger_coverage')
   if pair[1]in('H','T'):
    pkt.keys(v['quantiles'],[str(q)for q in core.Q]);core.need(all(type(x)in(int,float)and math.isfinite(x)for x in v['quantiles'].values()),'stronger_quantiles')
   records.append(dict(v,family='ENZ'if row['precontext'][14]==1 else'12Z',receiver=row['precontext'][8:11].tolist(),rate=row['noise']['rate']))
  out.append(dict(seed=pair[0],arm=pair[1],records=records,metrics={str(h):metrics.panel([r for r in records if r['horizon']==h])for h in(1,3,5)}))
 core.need(tx.sha(stronger)==authority['stronger_closure_sha256'],'stronger_byte_binding')
 if partial is not None:partial['current_stronger']=None
 return out

def aggregate(fit_audits,score_results,packet,admission,stronger,authority,*,processing_begin,retain=None):
 retention_failed=False;partial=dict(fits=[],stronger=[],computed_guard_outcomes=None,paired=[],current_paired=None)
 try:
  stage_tick(processing_begin);pkt.keys(authority,('schema','verified','native_verified','stronger_verified','packet_sha256','admission_sha256','source_pins','stronger_closure_sha256','fits'));core.need(authority['schema']=='root-marked-sixfit-aggregate-authority-v1'and authority['verified']is True and authority['native_verified']is True and authority['stronger_verified']is True,'aggregate_authority');sources(authority['source_pins'])
  for k in('packet_sha256','admission_sha256','stronger_closure_sha256'):hashstr(authority[k])
  core.need(type(fit_audits)is list and type(score_results)is list and len(fit_audits)==len(score_results)==6 and type(authority['fits'])is list and len(authority['fits'])==6,'six_complete');schema=admission_checked(admission,packet,authority);core.need(tx.sha(admission)==authority['admission_sha256']and admission['source_pins']==authority['source_pins'],'aggregate_admission');fits=partial['fits']
  for audit,result,pair,pin in zip(fit_audits,score_results,IDS,authority['fits']):
   stage_tick(processing_begin);pkt.keys(pin,('seed','arm','audit_sha256','authority_sha256','score_sha256','checkpoint_sha256'));core.need(type(pin['seed'])is int and(pin['seed'],pin['arm'])==pair,'aggregate_fit_identity')
   for k in('audit_sha256','authority_sha256','score_sha256','checkpoint_sha256'):hashstr(pin[k])
   core.need(audit['schema']=='marked-sixfit-independent-audit-v1'and audit['status']=='pass'and audit['checked']==66 and(audit['seed'],audit['arm'])==pair and tx.sha(audit)==pin['audit_sha256']and audit['authority_sha256']==pin['authority_sha256']and audit['score_sha256']==pin['score_sha256']==tx.sha(result)and result['checkpoint_sha256']==pin['checkpoint_sha256'],'aggregate_audit_custody');core.need(result['status']=='complete'and result['no_optimizer']is True and(result['seed'],result['arm'])==pair and result['source_pins']==authority['source_pins']and result['packet_sha256']==authority['packet_sha256']and result['admission_sha256']==authority['admission_sha256'],'aggregate_score_binding');records=audit['records'];core.need(type(records)is list and len(records)==66,'aggregate_records')
   for v,(ordinal,h)in zip(records,((i,h)for i in schema['dev']for h in(1,3,5))):
    row=packet['rows'][ordinal];core.need(type(v['ordinal'])is int and type(v['horizon'])is int and(v['ordinal'],v['horizon'])==(ordinal,h)and(v['seed'],v['arm'])==pair and v['target']==row['mw']and v['group']==row['group'],'aggregate_record_identity')
    for k in('mean','median','nll','crps','pit'):core.need(type(v[k])in(int,float)and math.isfinite(v[k]),'aggregate_numeric')
   fits.append(dict(seed=pair[0],arm=pair[1],records=records,metrics={str(h):metrics.panel([r for r in records if r['horizon']==h])for h in(1,3,5)},strata=metrics.strata(records)))
  old=stronger_checked(stronger,packet,schema,authority,partial=partial);partial['stronger']=old;advance=metrics.guards(fits,old);partial['computed_guard_outcomes']=advance;intervals=partial['paired']
  for fit in fits:
   if fit['arm']!='S':continue
   for comparator in [v for v in old+fits if v['seed']==fit['seed']and v['arm']in('B','F','H','T','P','D')]:
    for h in(1,3,5):
     current=dict(seed=fit['seed'],horizon=h,comparator=comparator['arm'],bootstrap={});partial['current_paired']=current;result=metrics.paired([v for v in fit['records']if v['horizon']==h],[v for v in comparator['records']if v['horizon']==h],lambda:stage_tick(processing_begin),evidence=current['bootstrap']);intervals.append(dict(seed=fit['seed'],horizon=h,comparator=comparator['arm'],metrics=result));partial['current_paired']=None
  report=dict(schema='marked-sixfit-independent-aggregate-v1',status='pass',checked=396,fits=fits,stronger=old,paired=intervals,advance=advance,authority_sha256=tx.sha(authority))
  if retain is not None:
   try:retain(report)
   except Exception:retention_failed=True;raise core.AuditFailure('retention_failed')
  stage_tick(processing_begin);return report
 except Exception as error:
  failure=dict(schema='marked-sixfit-independent-aggregate-v1',status='fail',reason=str(error)[:128],exception_type=type(error).__name__,partial=partial,advance=dict(pass_all=False,checks=[],additional=[]))
  if retain is not None and not retention_failed:
   try:retain(failure)
   except Exception:failure['retention_failed']=True
  return failure


def affine_bounds(marks,coeff,mref):
 result=[]
 for j,y in enumerate(marks):
  t=math.log1p(.25*j);prev=np.zeros(3)if j==0 else marks[j-1];beta=coeff[:,1]+coeff[:,3]*t;eb=32*core.EPS*(1+np.abs(coeff[:,1])+np.abs(coeff[:,3]*t));a=coeff[:,0]+coeff[:,2]*t+coeff[:,4]*prev-beta*mref;ea=abs(mref)*eb+32*core.EPS*(1+np.abs(coeff[:,0])+np.abs(coeff[:,2]*t)+np.abs(coeff[:,4]*prev)+np.abs(beta*mref));sigma=.05+core.softplus(coeff[:,5]);es=32*core.EPS*(1+np.abs(sigma));ey=np.zeros(3)
  for v,e in((a,ea),(beta,eb),(sigma,es),(y,ey)):core.bound_ok(v,e)
  result.append([ea,eb,es,ey])
 return result


def statistic_bounds(raw,raw_error):
 n=len(raw);gamma=(n+4)*core.EPS/(1-(n+4)*core.EPS);mean=raw.mean(0);std=raw.std(0);em=2*gamma*np.mean(np.abs(raw),0)+16*core.EPS*np.abs(mean)+np.mean(raw_error,0);es=8*gamma*std+2*em+2*np.max(raw_error,0);return em,es

def scalers_checked(admitted,fresh,p,roles):
 raw=np.asarray([p['rows'][i]['precontext'][pkt.KEEP]for i in roles['TRAIN']]);summary=np.asarray([core.summaries(p['rows'][i]['horizons'][h]['reported'],p['rows'][i]['noise']['nu'])for i in roles['TRAIN']for h in range(3)]);summary_error=np.asarray([core.summary_error(p['rows'][i]['horizons'][h]['reported'],p['rows'][i]['noise']['nu'])for i in roles['TRAIN']for h in range(3)])
 for name,x,error in(('static',raw,np.zeros_like(raw)),('summary',summary,summary_error)):
  a,b=admitted[name],fresh[name];core.array(a['mean'],b['mean'].shape);core.array(a['std'],b['std'].shape);constant=np.all(x==x[0],0);core.need(bool(np.array_equal(a['std']==0,constant))and bool((a['std']>=0).all()),'scaler_zero_semantics');em,es=statistic_bounds(x,error);nonconstant=~constant;core.need(bool(np.all(em[nonconstant]<=1e-10*b['std'][nonconstant]))and bool(np.all(es[nonconstant]<=1e-10*b['std'][nonconstant])),'scaler_bound_unresolved');core.need(bool(np.all(np.abs(a['mean']-b['mean'])<=em))and bool(np.all(np.abs(a['std'][nonconstant]-b['std'][nonconstant])<=es[nonconstant])),'scaler_arithmetic_disagreement')
  if name=='static':core.need(pkt.byteeq(a['constant'],b['constant']),'scaler_constant_mask')
 labels=np.asarray([p['rows'][i]['mw']for i in roles['TRAIN']],dtype=np.float64);em,es=statistic_bounds(labels[:,None],np.zeros((65,1)));core.need(abs(admitted['mref']-fresh['mref'])<=float(em[0])and abs(admitted['train_std']-fresh['train_std'])<=float(es[0]),'label_scaler_arithmetic')


def reconstruction_checked(static,p,roles):
 raw=np.asarray([p['rows'][i]['precontext'][pkt.KEEP]for i in roles['TRAIN']]);z=np.divide(raw-static['mean'],static['std'],out=np.zeros_like(raw),where=static['std']>0);kept=static['kept'];coef=core.array(static['reconstruction'],(len(kept),30));prediction=z[:,kept]@coef;residual=float(np.max(np.abs(prediction-z)));core.need(math.isfinite(residual)and residual<=1e-10,'admitted_reconstruction_residual');reported=static['reconstruction_max_abs'];core.need(type(reported)is float and math.isfinite(reported)and 0<=reported<=1e-10,'admitted_reconstruction_report');gamma=(len(kept)+4)*core.EPS/(1-(len(kept)+4)*core.EPS);bound=float(8*gamma*np.max(np.abs(z[:,kept])@np.abs(coef)+np.abs(z)));core.need(math.isfinite(bound)and bound<=1e-10 and abs(reported-residual)<=bound,'admitted_reconstruction_roundoff')
