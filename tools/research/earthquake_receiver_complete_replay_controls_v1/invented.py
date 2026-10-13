"""Small ROOT gate and numeric fixtures wholly invented in temporary directories."""
from pathlib import Path
import json
import time
import custody as c
import controls as x
import controller as p

def write(d,name,value):
 raw=value if type(value)is bytes else(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode();c.Store(d).put(name,raw);return dict(path=str(d/name),pin=c.pin(raw))

def fixture(root):
 root=Path(root);data=root/'inputs';data.mkdir();output=root/'output';output.mkdir();dev=list(range(91,113));one=write(data,'proof.private.json',dict(invented=True));checkpoint=write(data,'checkpoint.private.npz',b'invented_checkpoint')
 history=[dict(update=i,base_nll=1.,sequence_nll=0.,joint_or_conditional_nll=1.,gradient_norm=1.,base_gradient_norm=1.,sequence_gradient_norm=0.,seconds=float(i))for i in range(1,301)];journal=write(data,'history.private.jsonl',b''.join((json.dumps(v)+'\n').encode()for v in history))
 fits=[dict(seed=s,arm=a,status='complete',history=history,predictions=[dict(ordinal=i,horizon=h)for i in dev for h in(1,3,5)],numerical_failures=[],mref=4.,train_population_std=1.)for s,a in p.IDS];result=dict(status='complete',fits=fits,capacity={'invented':True},advance=dict(pass_all=False,checks=[{}]*24),comparisons=[{}]*24,diagnostics={'invented':True},fit_authorized=False);view=write(data,'result.private.json',result);aggregate=write(data,'aggregate.private.json',dict(result,retained_stage_results=[]))
 anchors=[dict(seed=s,arm=a,checkpoint=checkpoint,history=journal,metadata=one)for s,a in p.IDS];stages=[]
 for i,(stage,s,a)in enumerate(p.PLAN):
  files={'checkpoint.private.npz':checkpoint['pin'],'history.private.jsonl':journal['pin'],'stage_result.private.json':aggregate['pin']if i==17 else one['pin']}
  v=dict(schema='receiver-continuation-stage-return-v3',study=p.STUDY,index=i,stage=stage,seed=s,arm=a,status='complete',unit_exit=0,owned_unit_inactive=True,owned_cgroup_empty=True,files=files,experiment_begin=1.,source_commit='1'*40,scorer_binding='invented',capacity={'invented':True},study_fingerprint='2'*64);stages.append(write(data,'stage_%02d.private.json'%i,v))
 original=write(data,'original.private.json',dict(files={**{'checkpoint_%s_%s.private.npz'%(s,a):checkpoint['pin']for s,a in p.IDS[:3]},**{'history_%s_%s.private.jsonl'%(s,a):journal['pin']for s,a in p.IDS[:3]}}));preparation=write(data,'preparation.private.json',dict(schema='receiver-complete-replay-preparation-v1',passed=True,original_replay_verified=True,native_verified=True,continuation_closed=True,funding_resource_verified=True,publication_verified=True,linux_zero_skips=True,no_test=True,inputs={k:one for k in('original_provenance','native_agreement','continuation_agreement')}))
 def source(label,n):
  d=root/label;d.mkdir();files={}
  for i in range(n):name='s_%03d.txt'%i;spec=write(d,name,b'invented_public');files[name]=spec['pin']
  return dict(directory=str(d),files=files)
 gate=dict(schema='receiver-complete-replay-parent-gate-v1',study=p.STUDY,source_commit='a'*40,sources=dict(candidate=source('candidate',69),auditor=source('auditor',34),parent=source('parent',5)),runtime=dict(prefix_directory=str(root/'prefix'),manifest=one,canonical_sha256='b'*64,critical_files={str(root/('critical_%02d'%i)):dict(bytes=1,sha256='c'*64,mode='0o664'if i<3 else'0o775')for i in range(10)},torch_site=str(root/'torch'),symlinks=write(data,'symlinks.private.json',dict(schema='root-prefix-runtime-symlink-manifest-v1',prefix_directory=str(root/'prefix'),links={}))),packet=dict(archive=checkpoint,manifest=one),result=view,aggregate=aggregate,anchors=anchors,original_closed=original,stages=stages,preparation=preparation,output_root=str(output),dev_ordinals=dev);return gate,time.monotonic()

def replace(spec,value):
 path=Path(spec['path']);path.chmod(0o600);raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode();path.write_bytes(raw);path.chmod(0o400);spec['pin']=c.pin(raw)
