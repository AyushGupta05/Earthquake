"""NEW fixed50 projection independently validated from public schema only."""
import math
import re
from fractions import Fraction
from strict import Reject,integer,keys,pin

STUDY='geonet-fixed-TRAIN50-prefix3-native-POST-v1'
MIN_NS,MAX_NS=-(1<<63),(1<<63)-1
LITERAL=re.compile(r'[A-Z0-9]*\Z')


def literal(value,minimum,maximum):
    if type(value) is not str or not minimum<=len(value)<=maximum or not LITERAL.fullmatch(value):raise Reject('literal')


def rational(value):
    if type(value) is not list or len(value)!=2:raise Reject('rational')
    numerator=integer(value[0],1);denominator=integer(value[1],1)
    if math.gcd(numerator,denominator)!=1:raise Reject('unreduced')
    return Fraction(numerator,denominator)


def validate(plan):
    keys(plan,('study','rows','batches'))
    if type(plan['study']) is not str or plan['study']!=STUDY:raise Reject('study')
    if type(plan['rows']) is not list or len(plan['rows'])!=50 or type(plan['batches']) is not list or len(plan['batches'])!=13:raise Reject('denominator')
    for ordinal,row in enumerate(plan['rows']):
        keys(row,('ordinal','global_ordinal','partition','batch','queryable','network','station','location','prefix','t0_ns','pick_ns','family','nominal_rates'))
        if integer(row['ordinal'],0,49)!=ordinal or integer(row['global_ordinal'],65,114)!=65+ordinal or integer(row['batch'],0,12)!=ordinal//4:raise Reject('row_order')
        if type(row['partition']) is not str or row['partition']!='TRAIN' or type(row['queryable']) is not bool:raise Reject('partition_queryable')
        if row['t0_ns'] is not None:
            t0=integer(row['t0_ns'],MIN_NS,MAX_NS);integer(t0-3_000_000_000,MIN_NS,MAX_NS);integer(t0+5_000_000_000,MIN_NS,MAX_NS)
        if not row['queryable']:
            if any(row[k] is not None for k in ('network','station','location','prefix','pick_ns','family')):raise Reject('no_selection')
            keys(row['nominal_rates'],());continue
        if row['t0_ns'] is None:raise Reject('queryable_clock')
        for field,lo,hi in (('network',1,8),('station',1,8),('location',0,2),('prefix',2,2)):literal(row[field],lo,hi)
        integer(row['pick_ns'],MIN_NS,MAX_NS)
        family=row['family']
        if family is not None and (type(family) is not str or family not in ('ENZ','12Z')):raise Reject('family')
        keys(row['nominal_rates'],{row['prefix']+s for s in family} if family else ())
        for value in row['nominal_rates'].values():rational(value)
    total=0
    for ordinal,batch in enumerate(plan['batches']):
        keys(batch,('ordinal','rows','requested_rows','transport','body_bytes','body_sha256'))
        expected=list(range(4*ordinal,min(50,4*ordinal+4)))
        if integer(batch['ordinal'],0,12)!=ordinal or type(batch['rows']) is not list or any(type(n) is not int for n in batch['rows']) or batch['rows']!=expected:raise Reject('batch_order')
        requested=[i for i in expected if plan['rows'][i]['queryable']]
        if type(batch['requested_rows']) is not list or any(type(n) is not int for n in batch['requested_rows']) or batch['requested_rows']!=requested:raise Reject('requested_rows')
        if type(batch['transport']) is not str or batch['transport'] not in ('http200','no_data','error','empty','no_selection'):raise Reject('transport')
        if (batch['transport']=='no_selection')!=(not requested):raise Reject('no_selection_transport')
        if batch['transport']=='http200':
            pin({'bytes':batch['body_bytes'],'sha256':batch['body_sha256']},8_388_608);integer(batch['body_bytes'],1,8_388_608);total+=batch['body_bytes']
        elif integer(batch['body_bytes'],0,0)!=0 or batch['body_sha256'] is not None:raise Reject('nonpositive_pin')
    if total>109_051_904:raise Reject('body_total')
    return plan
