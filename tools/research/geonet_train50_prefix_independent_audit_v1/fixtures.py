"""Invented NEW50 projection only; no actual event/clock/body input."""
from invented import int_record
from strict import sha,canonical
from plan_validation import STUDY


def plan_and_bodies(positive=(0,),raw=None,queryable=None):
    if raw is None:raw=b''.join(int_record(channel='HH'+suffix,start_second=start,sequence=i*2+j+1) for i,suffix in enumerate('ENZ12') for j,start in enumerate((0,4)))
    allowed=set(range(50)) if queryable is None else set(queryable)
    rows=[]
    for i in range(50):
        family='ENZ' if i<40 else '12Z' if i<45 else None
        good=i in allowed
        rows.append(dict(ordinal=i,global_ordinal=65+i,partition='TRAIN',batch=i//4,queryable=good,network='NZ' if good else None,station='ABCD' if good else None,location='' if good else None,prefix='HH' if good else None,t0_ns=3_000_000_000 if good else None,pick_ns=3_500_000_000 if good else None,family=family if good else None,nominal_rates={'HH'+s:[10,1] for s in family} if good and family else {}))
    batches=[];bodies={}
    for n in range(13):
        slots=list(range(4*n,min(50,4*n+4)));requested=[i for i in slots if i in allowed];positive_body=n in positive and bool(requested)
        batches.append(dict(ordinal=n,rows=slots,requested_rows=requested,transport='http200' if positive_body else 'no_data' if requested else 'no_selection',body_bytes=len(raw) if positive_body else 0,body_sha256=sha(raw) if positive_body else None))
        if positive_body:bodies[n]=raw
    return dict(study=STUDY,rows=rows,batches=batches),bodies


def reader(bodies):return lambda ordinal,size:bodies[ordinal]


def input_pins(plan,result):
    a,b=canonical(plan),canonical(result)
    return a,b,dict(plan=dict(bytes=len(a),sha256=sha(a)),producer=dict(bytes=len(b),sha256=sha(b)))
