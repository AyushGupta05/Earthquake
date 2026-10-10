"""Join pinned TRAIN identities/clock metadata with audited response epochs.

No magnitude, geometry, waveform, cached model input, or validation/test files.
The shared polarization population helper is imported only with an explicit
SHA256 pin. Its group/sampling semantics are not reimplemented here.
"""
from collections import Counter, defaultdict
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from audit_response import (ARCHIVE_SHA, INVENTORY_SHA, atomic_json, covering_epoch,
                            load_module, sha, finite_json)


def window(row, inventory_module):
    try:
        p=float(row['trace_P_arrival_sample']);dt=float(row['trace_dt_s']);n=float(row['trace_npts'])
        ts=inventory_module.utc_seconds(row['trace_start_time'])
    except (ValueError,TypeError,OverflowError,KeyError):
        return None
    if (not all(math.isfinite(v) for v in (p,dt,n)) or ts is None or not math.isfinite(ts)
        or not p.is_integer() or p<200 or abs(dt-.01)>1e-10 or not n.is_integer() or n<p+500):
        return None
    return ts+(p-200)*.01,ts+(p+500)*.01


def canonical_orientation(component, epoch):
    if epoch.dip_deg is None or not math.isfinite(epoch.dip_deg):
        return False
    if component=='Z':
        return abs(epoch.dip_deg+90)<=1
    azimuth=epoch.azimuth_deg
    expected=90 if component=='E' else 0
    return (azimuth is not None and math.isfinite(azimuth) and abs(epoch.dip_deg)<=1
            and abs((azimuth-expected+180)%360-180)<=1)


def row_join(row,index,details,inventory_module):
    bounds=window(row,inventory_module)
    loc,repaired=inventory_module.location_code(row)
    expected=[row['source_id'],row['station_network_code'],row['station_code'],loc,row['station_channels']]
    if row['trace_name'].rsplit('.',4)!=expected:
        raise ValueError('TRAIN trace/source/SCNL identity disagreement: '+row['trace_name'])
    channels=[]
    for component in 'ENZ':
        key=(row['station_network_code'],row['station_code'],loc,row['station_channels']+component)
        status,epoch=covering_epoch(index.get(key,[]),*(bounds or (None,None)))
        item={'component':component,'status':status,'epoch_id':'','response_id':'',
              'unit':'unknown','orientation':False,'valid_frequencies':0,'response_reasons':[]}
        if epoch is not None:
            info=details[id(epoch)]
            item.update(epoch_id=info['epoch_id'],response_id=info['response_id'],
                        unit=inventory_module.normalize_units(epoch.input_units),
                        orientation=canonical_orientation(component,epoch),
                        valid_frequencies=int(np.asarray(info['descriptor'])[:,3].sum()),
                        response_reasons=info['response_reasons'])
        channels.append(item)
    matched=all(c['status']=='matched' for c in channels)
    units={c['unit'] for c in channels}
    uniform=matched and len(units)==1 and next(iter(units)) in ('m/s','m/s^2')
    oriented=matched and all(c['orientation'] for c in channels)
    return {'metadata_eligible':bounds is not None and matched and uniform and oriented,
            'clock_valid':bounds is not None,'all_scalar_responses':matched,'same_known_unit':uniform,
            'canonical_orientation':oriented,'location_repaired':repaired,'channels':channels}


def main(args):
    start=time.monotonic()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    provenance=json.loads(Path(args.metadata_provenance).read_text())
    if provenance['source_sha256']!='168b5d861804e9707f68125dc8bc9453c8e0a47a48ef4055a7920c6526f1535d':
        raise ValueError('Wrong original TRAIN metadata provenance')
    if sha(args.metadata)!=provenance['export_sha256']:
        raise ValueError('TRAIN export changed')
    expected=['source_row_index','source_id','trace_name','trace_start_time','trace_P_arrival_sample',
              'trace_dt_s','trace_npts','station_network_code','station_code','station_location_code','station_channels']
    if provenance['columns']!=expected or provenance['rows']!=979487:
        raise ValueError('Wrong metadata-only export schema/population')
    invmod=load_module('response_join_inventory',args.inventory_module,INVENTORY_SHA)
    population=load_module('response_shared_population',args.population_module,args.population_sha256)
    if sha(args.archive)!=ARCHIVE_SHA:
        raise ValueError('Wrong inventory archive')
    inventory=invmod.Inventory.from_archive(args.archive)
    audited=json.loads(Path(args.epochs).read_text())
    evaluations=json.loads(Path(args.responses).read_text())
    if len(inventory.epochs)!=len(audited):
        raise ValueError('Audited epoch count disagreement')
    details={}
    for epoch,record in zip(inventory.epochs,audited):
        core={k:getattr(epoch,k) for k in record if k not in ('epoch_id','response_id','descriptor','channel_reasons')}
        if finite_json(core)!={k:v for k,v in record.items() if k not in ('epoch_id','response_id','descriptor','channel_reasons')}:
            raise ValueError('Audited epoch identity/properties changed')
        details[id(epoch)]=dict(record,response_reasons=evaluations[record['response_id']]['reasons']+record['channel_reasons'])
    with gzip.open(args.metadata,'rt') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=expected:
            raise ValueError('Unexpected actual export columns')
        stations={row['station_network_code']+'.'+row['station_code'] for row in reader}
    groups,missing_coordinates=population.station_groups(stations,inventory.epochs)
    alias_sets=defaultdict(list)
    for station,group in groups.items():alias_sets[group].append(station)
    atomic_json(output/'station_alias_groups.json',{'groups':groups,'missing_coordinates':missing_coordinates,
                'merged_groups':{k:sorted(v) for k,v in alias_sets.items() if len(v)>1},
                'population_module_sha256':sha(args.population_module)})
    eligible=[];counts=Counter();status=Counter();unit_patterns=Counter();response_reasons=Counter()
    by_family=defaultdict(Counter);by_subset=defaultdict(Counter);join_hash=hashlib.sha256()
    columns=['source_row_index','source_id','trace_name','station_id','metadata_eligible','clock_valid',
             'same_known_unit','canonical_orientation']
    columns += [c+'_'+k for c in 'ENZ' for k in ('status','epoch_id','response_id','valid_frequencies')]
    joined=output/'train_response_join.csv.gz';temp=joined.with_suffix(joined.suffix+'.partial')
    with gzip.open(args.metadata,'rt') as stream,gzip.open(temp,'wt',newline='') as dest:
        writer=csv.DictWriter(dest,fieldnames=columns,lineterminator='\n');writer.writeheader()
        for row in csv.DictReader(stream):
            index=int(row['source_row_index'])
            if index!=counts['rows']:
                raise ValueError('Noncontiguous source row order')
            joined_row=row_join(row,inventory.index,details,invmod)
            station=row['station_network_code']+'.'+row['station_code']
            event_fold=population.bucket('polarization-event-v1',row['source_id'])
            station_fold=population.bucket('polarization-station-v1',groups[station])
            subset=('fit' if event_fold>=2 else 'eval_seen') if station_fold>=2 else ('excluded_fit_event_held_station' if event_fold>=2 else 'eval_held')
            counts['rows']+=1;by_family[row['station_channels']]['rows']+=1;by_subset[subset]['rows']+=1
            for key in ('metadata_eligible','clock_valid','all_scalar_responses','same_known_unit','canonical_orientation','location_repaired'):
                counts[key]+=int(joined_row[key])
            complete=all(c['valid_frequencies']==6 for c in joined_row['channels']) and joined_row['all_scalar_responses']
            any_frequency=any(c['valid_frequencies']>0 for c in joined_row['channels']) and joined_row['all_scalar_responses']
            counts['all_components_all6_response_frequencies']+=int(complete)
            counts['at_least_one_component_frequency']+=int(any_frequency)
            if joined_row['metadata_eligible']:
                counts['eligible_all_components_all6_response_frequencies']+=int(complete)
                counts['eligible_some_response_frequencies']+=int(any_frequency)
                by_family[row['station_channels']]['eligible']+=1;by_subset[subset]['eligible']+=1
                by_family[row['station_channels']]['eligible_complete_response']+=int(complete)
                by_subset[subset]['eligible_complete_response']+=int(complete)
                eligible.append({'source_row_index':index,'source_id':row['source_id'],'trace_name':row['trace_name'],
                                 'station_id':station})
            unit_patterns['/'.join(c['unit'] for c in joined_row['channels'])]+=1
            item={k:row[k] for k in ('source_row_index','source_id','trace_name')}
            item['station_id']=station
            for k in ('metadata_eligible','clock_valid','same_known_unit','canonical_orientation'):item[k]=int(joined_row[k])
            for c in joined_row['channels']:
                status[c['status']]+=1
                if c['status']=='matched':response_reasons.update(c['response_reasons'])
                for k in ('status','epoch_id','response_id','valid_frequencies'):item[c['component']+'_'+k]=c[k]
            writer.writerow(item)
            join_hash.update(json.dumps(item,sort_keys=True,separators=(',',':')).encode()+b'\n')
    if counts['rows']!=979487:
        raise ValueError('Wrong row count')
    temp.replace(joined)
    selected,sample_audit=population.select(eligible,groups)
    selected_path=output/'selected_metadata_population.csv.gz'
    with gzip.open(selected_path,'wt',newline='') as dest:
        writer=csv.DictWriter(dest,fieldnames=list(selected[0]),lineterminator='\n');writer.writeheader();writer.writerows(selected)
    summary={'scope':'TRAIN identities/clocks and response metadata only; no labels or waveform reads',
             'metadata_eligibility':'Same seven-second clock/scalar/unit/orientation gate as polarization v2; no additional response-quality exclusion',
             'population_boundary':'No magnitude/geometry validity audit yet; selected rows are metadata population before target and per-deadline waveform checks',
             'original_train_metadata_sha256':provenance['source_sha256'],'metadata_export_sha256':sha(args.metadata),
             'metadata_export_provenance_sha256':sha(args.metadata_provenance),'archive_sha256':sha(args.archive),
             'audited_epochs_sha256':sha(args.epochs),'evaluated_responses_sha256':sha(args.responses),
             'source_sha256':sha(__file__),'response_auditor_sha256':sha(Path(__file__).with_name('audit_response.py')),
             'population_module_sha256':sha(args.population_module),'counts':dict(counts),
             'channel_status':dict(status),'unit_patterns':dict(unit_patterns),'matched_channel_response_failure_reasons_nonexclusive':dict(response_reasons),
             'family':dict(by_family),'partition':dict(by_subset),'alias_counts':{'stations':len(groups),'groups':len(set(groups.values())),
                'merged_groups':sum(len(v)>1 for v in alias_sets.values()),'stations_missing_coordinates':len(missing_coordinates)},
             'sampling':sample_audit,'artifacts':{'join_sha256':sha(joined),'canonical_join_rows_sha256':join_hash.hexdigest(),
                'selected_metadata_population_sha256':sha(selected_path)},'seconds':time.monotonic()-start}
    atomic_json(output/'train_join_audit.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('metadata','metadata-provenance','archive','inventory-module','population-module','epochs','responses','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--population-sha256',required=True)
    main(p.parse_args())
