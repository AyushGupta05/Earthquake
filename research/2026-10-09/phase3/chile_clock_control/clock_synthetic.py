"""Parent-only CUDA proof using invented tensors and fresh random model weights."""
import copy
import hashlib
import torch
from torch.utils.data import DataLoader

from clock_contract import atomic_json, import_sources, PROTOCOL_SHA
from clock_training import configure_runtime, fresh_model, train_epoch, Budget
from clock_rng import Streams, assert_paired, state_digest, tensor_bytes


def nested_digest(value):
    """Stable tensor/value digest for exact synthetic optimizer-state comparison."""
    h=hashlib.sha256()
    def visit(x):
        if isinstance(x,torch.Tensor):h.update(tensor_bytes(x))
        elif isinstance(x,dict):
            for key in sorted(x,key=str):h.update(str(key).encode()+b'\0');visit(x[key])
        elif isinstance(x,(tuple,list)):
            h.update(str(len(x)).encode()+b'\0')
            for item in x:visit(item)
        else:h.update(repr(x).encode()+b'\0')
    visit(value);return h.hexdigest()


def execute_synthetic(args,plan,protocol,sources):
    budget=Budget(args.max_seconds);output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    runtime=configure_runtime();device=torch.device('cuda')
    if not torch.cuda.is_available():raise ValueError('Synthetic CUDA proof requires CUDA, no CPU fallback')
    team,trainer=import_sources(args.source_dir)
    torch.manual_seed(100);initial=copy.deepcopy(team.TeamLM('transformer').state_dict())
    generator=torch.Generator().manual_seed(101)
    invented=[{'waveforms':torch.randn(2,3000,3,generator=generator),'coordinates':torch.tensor([[-30.,-70.,.1],[-29.,-69.,.2]]),
               'magnitude':4.5+i*.1,'event':f'invented{i}'} for i in range(3)]
    records=[]
    for arm in ('source_uniform','source_uniform','discrete_1_3_5'):
        budget.check();model=fresh_model(team,initial,20261011,device)
        parameters=[p for p in model.parameters() if p.requires_grad];optimizer=torch.optim.Adam(parameters,lr=9e-6)
        streams=Streams(20261011,device)
        loader=DataLoader(invented,batch_size=2,shuffle=False,num_workers=0,
                          generator=torch.Generator().manual_seed(100),collate_fn=trainer.collate_events)
        result=train_epoch(model,loader,optimizer,parameters,streams,arm,team,trainer,device,
                           seed=20261011,epoch=0,station_counts={r['event']:2 for r in invented},check_budget=budget.check)
        records.append({'arm':arm,'loss':result['train_loss'],'model_sha256':state_digest(model.state_dict()),
                        'optimizer_sha256':nested_digest(optimizer.state_dict()),'trace':result['trace']})
        del model,optimizer,parameters,streams
        torch.cuda.empty_cache()
    for key in ('loss','model_sha256','optimizer_sha256','trace'):
        if records[0][key]!=records[1][key]:raise ValueError('Identical-clock CUDA replay failed: '+key)
    assert_paired(records[0]['trace'],records[2]['trace'])
    budget.check()
    atomic_json(output/'COMPLETE.json',{'schema':'chile-clock-synthetic-cuda-v1','protocol_sha256':PROTOCOL_SHA,
      'source_manifest_sha256':args.source_manifest_sha256,'runtime':runtime,'gpu':torch.cuda.get_device_name(),
      'records':records,'production_artifact_reads':0,'scope':'Invented3-event,2-station CUDA update/RNG proof; does not establish full-batch recovery or model quality.'})
