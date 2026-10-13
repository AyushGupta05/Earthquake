"""Invented temporary source/control proofs only; never actual artifacts."""
from pathlib import Path
import json
import time
import custody as c
import controller as p

def write(directory,name,value):
 raw=value if type(value)is bytes else(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode();c.Store(directory).put(name,raw);return dict(path=str(directory/name),pin=c.pin(raw))

def fixture(root,index=0):
 root=Path(root);data=root/'inputs';data.mkdir();experiment=root/'experiment';experiment.mkdir()
 def source(label,n):
  d=root/label;d.mkdir();files={}
  for i in range(n):raw=b'invented source\n';name='s_%03d.txt'%i;write(d,name,raw);files[name]=c.pin(raw)
  return dict(directory=str(d),files=files)
 one=write(data,'proof.private.json',{'invented':True});summary=dict(schema='receiver-continuation-prerequisites-v3',passed=True,native_observations_verified=True,original_checkpoint_forward_records=178,original_independent_scores=178,original_replay_agreed=True,prior_units_inactive=True,prior_cgroups_empty=True,publication_verified=True,linux_zero_skips=True,funding_resource_authorized=True,inputs={k:one for k in('native','original_replay','original_agreement','original_closed_output')})
 prerequisites=write(data,'prerequisites.private.json',summary);manifest=write(data,'runtime.private.json',{'invented':True});packet=write(data,'packet.private.npz',b'invented');pm=write(data,'packet_manifest.private.json',{'invented':True})
 closed=write(data,'original_closed.private.json',dict(files={**{'checkpoint_20261012_%s.private.npz'%a:packet['pin']for a in('B','F','H')},**{'history_20261012_%s.private.jsonl'%a:one['pin']for a in('B','F','H')}}));summary['inputs']['original_closed_output']=closed
 old=Path(prerequisites['path']);old.chmod(0o600);newraw=(json.dumps(summary,sort_keys=True)+'\n').encode();old.write_bytes(newraw);old.chmod(0o400);prerequisites['pin']=c.pin(newraw)
 stage,seed,arm=p.PLAN[index];begin=time.monotonic()
 a=dict(schema='receiver-continuation-admission-v3',original_replay_verified=True,source_runtime_verified=True,resource_verified=True,capacity=dict(counts={'B':5007,'F':5147,'H':5125,'T':5125,'C':5125},nonzero_TRAIN_probe_gradient_degrees={'B':5007,'F':5147,'H':5125,'T':5125,'C':5125}),scorer_mode='original',scorer_binding='invented-original',optional_scorer_verified=False)
 gate=dict(schema='receiver-continuation-parent-gate-v3',study=p.STUDY,index=index,stage=stage,seed=seed,arm=arm,experiment_begin=begin,source_commit='1'*40,admission=a,sources=dict(candidate=source('candidate',69),engine=source('engine',34),parent=source('parent',3),optional=None),runtime=dict(prefix_directory=str(root/'prefix'),manifest=manifest,canonical_sha256='2'*64,critical_files={str(root/('critical_%02d'%i)):dict(bytes=1,sha256='3'*64,mode='0o644')for i in range(10)},torch_site=str(root/'torch')),packet=dict(archive=packet,manifest=pm),prerequisites=prerequisites,anchor=dict(checkpoint=packet,history=one,metadata=one)if stage=='score'else None,score_results=[one]*10 if stage=='aggregate'else None,previous=[],experiment_root=str(experiment))
 return gate,begin,summary

def bind_summary(gate,summary):
 spec=gate['prerequisites'];p=Path(spec['path']);p.chmod(0o600);raw=(json.dumps(summary,sort_keys=True)+'\n').encode();p.write_bytes(raw);p.chmod(0o400);spec['pin']=c.pin(raw)
