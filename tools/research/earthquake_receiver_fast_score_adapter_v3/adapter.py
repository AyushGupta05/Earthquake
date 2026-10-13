"""Pure optional scorer adapter; parent source/runtime/adoption authority required."""
import math
import time
import numpy as np

NUMERIC_FIELDS=('log_normalizer','mean','nll')
HAZARD_FIELDS=('alpha','beta','z_weights','c_weights','gamma','extra')
QUANTILES=('0.025','0.1','0.25','0.5','0.75','0.9','0.975')
FAST_KEYS={'accepted','diagnostic_only','score','error','reference_error','gh_error','gh_required','gradients','gradient_error','work','method'}


def need(ok,reason):
    if not ok:raise ValueError(reason)


def number(value):return type(value) in (int,float) and math.isfinite(value)


def diagnostic(value):
    remaining=8192
    def visit(v,depth):
        nonlocal remaining
        remaining-=1;need(remaining>=0 and depth<=20,'diagnostic_cap')
        if type(v) is float:
            return v if math.isfinite(v) else 'NaN' if math.isnan(v) else '+Infinity' if v>0 else '-Infinity'
        if type(v) in (int,bool) or v is None:return v
        if type(v) is str:need(len(v)<=256,'diagnostic_text');return v
        if type(v) is list:return [visit(x,depth+1) for x in v]
        if type(v) is dict:
            need(all(type(k) is str and len(k)<=128 for k in v),'diagnostic_keys')
            return {k:visit(x,depth+1) for k,x in v.items()}
        return {'unsupported_type':type(v).__name__}
    return visit(value,0)


def tensor_values(tensor,torch,shape,dtype):
    need(isinstance(tensor,torch.Tensor) and tuple(tensor.shape)==shape and tensor.dtype==dtype and tensor.device.type=='cpu','tensor_contract')
    return tensor.detach().cpu().double().tolist()


def affine_factors(core,hazard,z,c,states):
    idx,change,u,age=core.transitions(states)
    intercept=hazard.logits(0.,z,c,idx,u,age)
    sign=np.where(change==1,1.,-1.)
    pairs=[[float(s*a),float(s*hazard.beta[i])] for s,a,i in zip(sign,intercept,idx)]
    need(len(pairs)<=19 and all(number(x) for pair in pairs for x in pair),'affine')
    return pairs


def fast_contract(value):
    need(type(value) is dict and set(value)==FAST_KEYS,'fast_schema')
    need(value['accepted'] is True and value['diagnostic_only'] is False and value['gh_required'] is True and value['method']=='vectorized-all-real-legendre-CDF-v3','fast_rejected')
    need(value['gradients'] is None and value['gradient_error'] is None,'fast_gradients')
    error=value['error'];need(type(error) is dict and set(error)=={'log_normalizer','mean','nll','crps','median','pit','quantiles','crps_identity','cdf_internal_defect'},'fast_error')
    score=value['score'];need(type(score) is dict and set(score)=={'log_normalizer','mean','nll','crps','median','pit','absolute_moment','pair_half_moment','cdf_product','quantiles','coverage_50','coverage_80','coverage_95'},'fast_score')
    for key in ('log_normalizer','mean','nll','crps','median','pit','absolute_moment','pair_half_moment','cdf_product'):need(number(score[key]),'fast_nonfinite')
    need(score['crps']>=0 and 0<=score['pit']<=1,'fast_probability')
    q=score['quantiles'];need(type(q) is dict and tuple(q)==QUANTILES and all(number(x) for x in q.values()) and list(q.values())==sorted(q.values()),'fast_quantiles')
    for key,err in error.items():
        relevant=score[key] if key in score and number(score[key]) else score['crps'] if key=='crps_identity' else 1.
        need(number(err) and 0<=err<=1e-6*(1+abs(relevant)),'fast_convergence')
    need(error['cdf_internal_defect']<=1e-10,'fast_cdf_defect')
    for key,fields in (('reference_error',{'log_normalizer','mean','nll','cdf','absolute_moment'}),('gh_error',set(NUMERIC_FIELDS))):
        errors=value[key];need(type(errors) is dict and set(errors)==fields and all(number(x) and 0<=x<=1e-4 for x in errors.values()),'fast_parity')
    work=value['work'];need(type(work) is dict and set(work)=={'vector_points','reference_points','intervals','refinements'} and all(type(x) is int and x>=0 for x in work.values()) and work['vector_points']<=2000000 and work['reference_points']<=2000000 and work['intervals']<=512 and work['refinements']<=7,'fast_work')
    return score


def make_adapter(deps):
    """Parent injects fixed frozen modules; no source lookup or IO authority."""
    core,models,torch,fast=deps.core,deps.models,deps.torch,deps.fast_scorer
    def numerical(net,raw,z,ctx,states,mask,target,tick):
        record=dict(accepted=False,errors={},torch_errors={},base_raw=[],z=[],c=[],states=[],hazard={},mref=None,integrals={})
        fast_evidence={'status':'not_called'};parity={}
        try:
            need(net.arm in ('H','T','C') and number(target),'input')
            rv=tensor_values(raw,torch,(1,15),torch.float32)[0];zv=tensor_values(z,torch,(1,36),torch.float32)[0];cv=tensor_values(ctx,torch,(1,35),torch.float32)[0]
            need(isinstance(states,torch.Tensor) and states.dtype==torch.int64 and states.device.type=='cpu' and states.ndim==2 and states.shape[0]==1 and 1<=states.shape[1]<=20,'states')
            need(isinstance(mask,torch.Tensor) and mask.dtype==torch.bool and mask.device.type=='cpu' and mask.shape==states.shape,'mask')
            models.edges(states,mask) # Exact original nonempty observed-prefix/binary validation.
            sv=states[0,mask[0]].detach().cpu().tolist();h=net.hazards
            hz={}
            for key,shape in (('alpha',(2,)),('beta',(2,)),('z_weights',(2,36)),('c_weights',(2,35)),('gamma',(2,)),('extra',(2,))):
                hz[key]=tensor_values(getattr(h,key),torch,shape,torch.float32)
            evidence=dict(base_raw=rv,z=zv,c=cv,states=sv,hazard=hz,mref=h.mref)
            record.update(diagnostic(evidence)) # Before any injected tick/numerical callback.
            need(all(number(x) for values in (rv,zv,cv) for x in values) and number(h.mref),'nonfinite_input')
            mixture=core.Mixture.from_raw(np.asarray(rv,dtype=np.float64));hazard=core.Hazard(net.arm,*[np.asarray(hz[k],dtype=np.float64) for k in HAZARD_FIELDS],h.mref)
            tick()
            checked=core.checked_inference(mixture,hazard,np.asarray(zv),np.asarray(cv),sv,target)
            record['errors']=diagnostic(checked['errors']);record['integrals']={k:diagnostic(vars(checked[k])) for k in ('gh64','gh128','adaptive')}
            need(checked['accepted'] is True and all(number(x) and 0<=x<=1e-4 for x in checked['errors'].values()),'original_core_rejected')
            tick()
            for order in (64,128):
                logz,mean=models.torch_gh(raw,h,z,ctx,states,mask,order);ref=checked['gh'+str(order)]
                error=max(abs(float(logz[0])-ref.log_normalizer),abs(float(mean[0])-ref.mean));record['torch_errors'][str(order)]=diagnostic(error)
                need(number(error) and error<=1e-4,'original_torch_rejected');tick()
            affine=affine_factors(core,hazard,np.asarray(zv),np.asarray(cv),sv)
            tick();before_call=time.monotonic()
            try:
                result=fast.score(mixture.weights.tolist(),mixture.means.tolist(),mixture.sigmas.tolist(),affine,target,processing_begin=before_call,budget_seconds=10,tolerance=1e-6,require_gh=True,gradients=False)
            except Exception as error:
                fast_evidence=dict(status='failed',exception_type=type(error).__name__,reason=str(error)[:128],evidence=diagnostic(getattr(error,'evidence',None)),affine=affine);raise
            fast_evidence=diagnostic(result) # Capture returned diagnostics BEFORE the next tick.
            fs=fast_contract(result)
            for method in ('gh64','gh128','adaptive'):
                ref=checked[method];parity[method]={key:abs(fs[key]-getattr(ref,key)) for key in NUMERIC_FIELDS}
                need(all(number(x) and x<=1e-4 for x in parity[method].values()),'original_fast_disagreement')
            coverage={}
            for key,lo,hi in (('coverage_50','0.25','0.75'),('coverage_80','0.1','0.9'),('coverage_95','0.025','0.975')):
                v=fs[key];truth=fs['quantiles'][lo]<=target<=fs['quantiles'][hi]
                need(type(v) in (int,float) and v in (0,1) and v==int(truth),'coverage_indicator')
                coverage[key]=bool(v)
            score=dict(mean=checked['gh64'].mean,nll=checked['gh64'].nll,median=fs['median'],crps=fs['crps'],pit=fs['pit'],quantiles=fs['quantiles'],**coverage)
            need(score['median']==score['quantiles']['0.5'],'median_binding')
            tick();record['accepted']=True
            return score,record
        except Exception as error:
            record.update(accepted=False,reason=str(error)[:128],exception_type=type(error).__name__,fast_diagnostics=fast_evidence,fast_parity_errors=diagnostic(parity))
            return None,record
    return numerical
