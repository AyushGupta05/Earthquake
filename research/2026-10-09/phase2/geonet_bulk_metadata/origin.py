"""Offline origin diagnostics around the unchanged reviewed associated-P parser."""
import datetime as dt

UTC=dt.timezone.utc
START=dt.datetime(2003,8,1,tzinfo=UTC)
END=dt.datetime(2025,1,1,tzinfo=UTC)
PARTITIONS={'train2003_2014':(2003,2014),'dev2015_2017':(2015,2017),'test2018_2024':(2018,2024)}


def partition(year):return next((p for p,(a,b) in PARTITIONS.items() if a<=year<=b),None)


def offline_origin(lib,body,eid,cmt_time,base):
    result={'unique_preferred_origin_linkage':False,'valid_timezone_aware_origin_time':False,'valid_origin_time_in_window':False,'geometry_complete':False,
            'time_utc':None,'latitude_degrees':None,'longitude_degrees':None,'depth_m':None,'negative_depth':None,
            'signed_origin_minus_cmt_minute_seconds':None,'origin_cmt_utc_day_match':None,'origin_cmt_utc_year_match':None,
            'origin_cmt_candidate_partition_match':None,'abs_origin_cmt_offset_ge_300s':None,
            'earliest_NZ_P_minus_origin_seconds':None,'earliest_NZ_P_before_origin':None,'earliest_NZ_P_later_than_600s':None,'earliest_NZ_pick_outside_source_window':None,
            'origin_type':None,'reference_system_id':None,'depth_unit':'meters',
            'depth_reference':'QuakeML BED 1.2: WGS84 geoid nominal sea level',
            'reasons':[],'offline_sequence_diagnostics_only':True,'inference_inputs':False}
    # This limited origin-only extraction preserves origin evidence when the
    # unchanged P parser fails on an unrelated pick singleton. It makes no P claim.
    try:
        decoded=body.decode('utf-8-sig')
        if '\x00' in decoded or '<!DOCTYPE' in decoded.upper() or '<!ENTITY' in decoded.upper():raise ValueError('unsafe XML')
        root=lib.ET.fromstring(decoded)
        if root.tag!='{'+lib.QML_NS+'}quakeml':raise ValueError('wrong namespace')
        parameters=root.findall(lib.bed('eventParameters'))
        if len(parameters)!=1:raise ValueError('ambiguous eventParameters')
        events=[e for e in parameters[0].findall(lib.bed('event')) if e.get('publicID','').rstrip('/').rsplit('/',1)[-1]==eid]
        if len(events)!=1:raise ValueError('ambiguous event identity')
        event=events[0]
    except (UnicodeError,ValueError,lib.ET.ParseError):
        result['reasons'].append('source_structure_or_identity_invalid');return result
    try:preferred=lib.text_at(event,'preferredOriginID')
    except ValueError:
        result['reasons'].append('preferred_origin_linkage_ambiguous');return result
    origins=[o for o in event.findall(lib.bed('origin')) if o.get('publicID')==preferred]
    if not preferred or len(origins)!=1:
        result['reasons'].append('preferred_origin_linkage_unknown');return result
    if base.get('status')=='ok' and base.get('preferred_origin_id')!=preferred:raise ValueError('reviewed preferred-origin resolution changed')
    selected=origins[0];result['unique_preferred_origin_linkage']=True;origin_time=None
    for name,key in (('type','origin_type'),('referenceSystemID','reference_system_id')):
        try:result[key]=lib.text_at(selected,name) or None
        except ValueError:result['reasons'].append(name+'_ambiguous')
    def scalar(name):
        try:value=lib.text_at(selected,name+'/value')
        except ValueError:result['reasons'].append(name+'_ambiguous');return None
        if not value:result['reasons'].append(name+'_missing');return None
        return value
    value=scalar('time')
    if value is not None:
        try:
            origin_time=lib.utc(value);result['time_utc']=origin_time.isoformat();result['valid_timezone_aware_origin_time']=True
            result['valid_origin_time_in_window']=START<=origin_time<END
            if not result['valid_origin_time_in_window']:result['reasons'].append('time_outside_frozen_window')
        except (ValueError,OverflowError):result['reasons'].append('time_invalid_or_naive')
    geometry=[]
    for name,key,bounds in (('latitude','latitude_degrees',(-90,90)),('longitude','longitude_degrees',(-180,180)),('depth','depth_m',None)):
        value=scalar(name);number=lib.number(value) if value is not None else None
        if value is not None and number is None:result['reasons'].append(name+'_nonfinite_or_invalid')
        valid=number is not None and (bounds is None or bounds[0]<=number<=bounds[1])
        if number is not None and not valid:result['reasons'].append(name+'_outside_range')
        result[key]=number;geometry.append(valid)
    result['geometry_complete']=all(geometry)
    if result['depth_m'] is not None:result['negative_depth']=result['depth_m']<0
    picks=[lib.utc(p['time']) for p in base.get('accepted_picks',[]) if p['network']=='NZ'] if base.get('status')=='ok' else []
    earliest=min(picks) if picks else None
    if earliest is not None:result['earliest_NZ_pick_outside_source_window']=not START<=earliest<END
    if origin_time is not None:
        cmt=dt.datetime.strptime(cmt_time,'%Y%m%d%H%M%S').replace(tzinfo=UTC)
        offset=(origin_time-cmt).total_seconds();result['signed_origin_minus_cmt_minute_seconds']=offset
        result['origin_cmt_utc_day_match']=origin_time.date()==cmt.date()
        result['origin_cmt_utc_year_match']=origin_time.year==cmt.year
        result['origin_cmt_candidate_partition_match']=partition(origin_time.year)==partition(cmt.year)
        result['abs_origin_cmt_offset_ge_300s']=abs(offset)>=300
        if earliest is not None:
            delta=(earliest-origin_time).total_seconds();result['earliest_NZ_P_minus_origin_seconds']=delta
            result['earliest_NZ_P_before_origin']=delta<0;result['earliest_NZ_P_later_than_600s']=delta>600
    result['reasons']=sorted(set(result['reasons']))
    return result
