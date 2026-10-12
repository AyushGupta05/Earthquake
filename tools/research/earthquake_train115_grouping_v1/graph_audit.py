"""Separate graph replay: no producer imports or borrowed decisions."""
import math


def _expected(rows):
    if type(rows) is not list or len(rows)!=115:raise ValueError('115_rows')
    counts={'TRAIN':0,'DEV':0};old={'TRAIN':0,'DEV':0};origins={}
    for i,r in enumerate(rows):
        if type(r) is not dict or set(r)!=set(('ordinal','partition','origin_ns','latitude','longitude')):raise ValueError('row_keys')
        if type(r['ordinal']) is not int or r['ordinal']!=i or type(r['partition']) is not str or r['partition'] not in counts:raise ValueError('identity')
        p=r['partition'];counts[p]+=1
        if i<65:old[p]+=1
        elif p!='TRAIN':raise ValueError('new_TRAIN')
        t,a,b=r['origin_ns'],r['latitude'],r['longitude']
        if (type(t) is int and -(2**63)<=t<=2**63-1 and type(a) in (int,float) and type(b) in (int,float)
                and -90<=a<=90 and -180<=b<=180 and math.isfinite(a) and math.isfinite(b)):origins[i]=(t,float(a),float(b))
    if counts!={'TRAIN':91,'DEV':24} or old!={'TRAIN':41,'DEV':24}:raise ValueError('partitions')
    edges=[];neighbors={i:set() for i in origins}
    for i in sorted(origins):
        t,lat,lon=origins[i]
        for j in sorted(k for k in origins if k>i):
            q,la,lo=origins[j]
            if abs(q-t)>2592000000000000:continue
            lat0,lat1=math.radians(lat),math.radians(la)
            dlat=lat1-lat0;dlon=math.radians((lo-lon+180.)%360.-180.)
            h=math.sin(dlat/2.)**2+math.cos(lat0)*math.cos(lat1)*math.sin(dlon/2.)**2
            h=min(1.,max(0.,h));distance=12742.*math.atan2(math.sqrt(h),math.sqrt(1.-h))
            if distance<=200.:edges.append([i,j]);neighbors[i].add(j);neighbors[j].add(i)
    unseen=set(origins);groups=[];mapping={}
    while unseen:
        first=min(unseen);pending=[first];members=set()
        while pending:
            v=pending.pop()
            if v in members:continue
            members.add(v);pending.extend(neighbors[v]-members)
        ordered=sorted(members);unseen-=members;cross=len({rows[v]['partition'] for v in ordered})>1
        groups.append({'identifier':first,'original_ordinals':ordered,'cross_partition':cross,'operational_eligible':not cross})
        for v in ordered:mapping[v]=(first,cross)
    resultrows=[]
    for i,r in enumerate(rows):
        found=i in mapping;ident,cross=mapping.get(i,(None,False))
        resultrows.append({'slot':i,'ordinal':i,'partition':r['partition'],'group_identifier':ident,
                           'status':'UNKNOWN_ORIGIN' if not found else 'CROSS_PARTITION' if cross else 'known',
                           'operational_eligible':found and not cross})
    return {'schema':'operational-grouping115-v1','events':115,'maximum_pairs':6555,
            'partition_counts':{'TRAIN':91,'DEV':24},'edges':edges,'groups':groups,'rows':resultrows,
            'physical_sequence_independence_verified':False,'external_origin_binding_verified':False,'fit_authorized':False}


def _typed_equal(a,b):
    if type(a) is not type(b):return False
    if type(a) is dict:return set(a)==set(b) and all(_typed_equal(a[k],b[k]) for k in a)
    if type(a) is list:return len(a)==len(b) and all(_typed_equal(x,y) for x,y in zip(a,b))
    return a==b


def audit(rows,result):
    expected=_expected(rows);agreement=_typed_equal(expected,result)
    return {'schema':'operational-grouping115-audit-v1','agreement':agreement,'events':115,
            'groups':len(expected['groups']),'edges':len(expected['edges']),
            'unknown_slots':sum(r['status']=='UNKNOWN_ORIGIN' for r in expected['rows']),
            'external_origin_binding_verified':False,'physical_sequence_independence_verified':False,'fit_authorized':False}
