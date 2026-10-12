"""Metadata-only fixed115 convention; no data/IO/physics/fit authority."""
import math

EARTH_KM=6371.0
WINDOW_NS=30*86400*10**9


def _keys(row,names):
    if type(row) is not dict or set(row)!=set(names):raise ValueError('EXACT_ROW_KEYS')


def _origin(row):
    t,la,lo=row['origin_ns'],row['latitude'],row['longitude']
    if type(t) is not int or not -(2**63)<=t<=2**63-1:return None
    if type(la) not in (int,float) or type(lo) not in (int,float):return None
    if not -90<=la<=90 or not -180<=lo<=180 or not math.isfinite(la) or not math.isfinite(lo):return None
    return t,float(la),float(lo)


def validate(rows):
    if type(rows) is not list or len(rows)!=115:raise ValueError('FIXED115')
    counts={'TRAIN':0,'DEV':0};old={'TRAIN':0,'DEV':0};origins=[]
    for i,r in enumerate(rows):
        _keys(r,('ordinal','partition','origin_ns','latitude','longitude'))
        if type(r['ordinal']) is not int or r['ordinal']!=i:raise ValueError('ORIGINAL_SLOT_ORDER')
        p=r['partition']
        if type(p) is not str or p not in counts:raise ValueError('TRAIN_DEV_ONLY')
        if i>=65 and p!='TRAIN':raise ValueError('NEW50_TRAIN_ONLY')
        counts[p]+=1
        if i<65:old[p]+=1
        origins.append(_origin(r))
    if counts!={'TRAIN':91,'DEV':24} or old!={'TRAIN':41,'DEV':24}:raise ValueError('FIXED_PARTITIONS')
    return origins


def distance_km(la1,lo1,la2,lo2):
    p1,p2=math.radians(la1),math.radians(la2)
    d=p2-p1;dl=math.radians((lo2-lo1+180.)%360.-180.)
    a=math.sin(d/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    a=min(1.,max(0.,a))
    return 2*EARTH_KM*math.atan2(math.sqrt(a),math.sqrt(1.-a))


def group_events(rows):
    origins=validate(rows);parent=list(range(115));edges=[]
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,a in enumerate(origins):
        if a is None:continue
        for j in range(i+1,115):
            b=origins[j]
            if b is not None and abs(a[0]-b[0])<=WINDOW_NS and distance_km(a[1],a[2],b[1],b[2])<=200.:
                edges.append([i,j]);x,y=find(i),find(j);parent[max(x,y)]=min(x,y)
    components={}
    for i,o in enumerate(origins):
        if o is not None:components.setdefault(find(i),[]).append(i)
    groups=[];mapping={}
    for members in components.values():
        identifier=min(members);cross=len({rows[i]['partition'] for i in members})>1
        groups.append({'identifier':identifier,'original_ordinals':members,'cross_partition':cross,'operational_eligible':not cross})
        for i in members:mapping[i]=(identifier,cross)
    groups.sort(key=lambda g:g['identifier']);out=[]
    for i,r in enumerate(rows):
        known=i in mapping;identifier,cross=mapping.get(i,(None,False))
        out.append({'slot':i,'ordinal':i,'partition':r['partition'],'group_identifier':identifier,
                    'status':'UNKNOWN_ORIGIN' if not known else 'CROSS_PARTITION' if cross else 'known',
                    'operational_eligible':known and not cross})
    return {'schema':'operational-grouping115-v1','events':115,'maximum_pairs':6555,
            'partition_counts':{'TRAIN':91,'DEV':24},'edges':edges,'groups':groups,'rows':out,
            'physical_sequence_independence_verified':False,'external_origin_binding_verified':False,'fit_authorized':False}


def public_summary(result):
    _keys(result,('schema','events','maximum_pairs','partition_counts','edges','groups','rows',
                  'physical_sequence_independence_verified','external_origin_binding_verified','fit_authorized'))
    if result['schema']!='operational-grouping115-v1':raise ValueError('RESULT_SCHEMA')
    return {'schema':'operational-grouping115-public-v1','events':115,'maximum_pairs':6555,
            'TRAIN':91,'DEV':24,'groups':len(result['groups']),'edges':len(result['edges']),
            'cross_partition_groups':sum(g['cross_partition'] for g in result['groups']),
            'unknown_origin_slots':sum(r['status']=='UNKNOWN_ORIGIN' for r in result['rows']),
            'eligible_slots':sum(r['operational_eligible'] for r in result['rows']),
            'physical_sequence_independence_verified':False,'external_origin_binding_verified':False,'fit_authorized':False}
