"""TRAIN-only original-common native-count amplitude/noise scalars."""
from fractions import Fraction
import math
import time

import adapter as native
import activity
import producer

SCHEMA = 'earthquake-train-amplitude-native-v1'
HORIZONS = (1, 3, 5)
MAX_SECONDS = 300
MAX_PRIVATE = 16 * 1024 * 1024
MAX_PUBLIC = 64 * 1024
STATUSES = ('available', 'DEFERRED_DEV', 'NON_COMMON', 'UNSUPPORTED', 'BAD_NOISE', 'BAD_WINDOW')


class InvalidInput(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise InvalidInput(code)


def deadline(started):
    need(time.monotonic() - started <= MAX_SECONDS, 'wall_timeout')


def manifest_bind(plan, qualified, metadata, manifest):
    need(native.keys(manifest, ('schema', 'study', 'rows', 'denominators'))
         and manifest['schema'] == 'earthquake-native-count-artifact-v1'
         and manifest['study'] == plan['study']
         and native.same(manifest['denominators'], {'rows':65,'cells':195,'train':41,'dev':24,'test_excluded':31})
         and type(manifest['rows']) is list and len(manifest['rows']) == 65, 'manifest_schema')
    for i, (row, qrow, meta, original) in enumerate(zip(plan['rows'], qualified['rows'], metadata, manifest['rows'])):
        need(native.keys(original, ('ordinal','partition','group','mw','cohort','cells'))
             and native.same(original['ordinal'], i) and native.same(original['partition'], row['partition'])
             and type(original['group']) is int and 0 <= original['group'] <= 64
             and type(original['mw']) in (int,float) and math.isfinite(original['mw'])
             and -5 <= original['mw'] <= 15 and float(original['mw']) == float(meta['mw'])
             and meta['group'] == str(original['group']) and type(original['cohort']) is bool
             and type(original['cells']) is list and len(original['cells']) == 3, 'manifest_row')
        available = []
        for h, cell, qcell in zip(HORIZONS, original['cells'], qrow['cells']):
            need(native.keys(cell, ('horizon','status','reason','array','shape','first','period','precontext_count','channels','view_sha256'))
                 and native.same(cell['horizon'], h) and cell['status'] in ('available','unavailable')
                 and type(cell['channels']) is list, 'manifest_cell')
            available.append(cell['status'] == 'available')
            if cell['status'] == 'available':
                required = producer.channels(row)
                need(len(required) == 3 and native.same(cell['channels'], required)
                     and cell['reason'] == 'supported' and cell['array'] == 'wave_%02d_%d' % (i,h)
                     and type(cell['shape']) is list and len(cell['shape']) == 2
                     and type(cell['shape'][0]) is int and cell['shape'][0] == 3
                     and type(cell['shape'][1]) is int and 1 <= cell['shape'][1] <= 10_000_000//3
                     and type(cell['precontext_count']) is int and 1 <= cell['precontext_count'] <= cell['shape'][1]
                     and qcell['joint']['status'] == 'complete' and qcell['pick_before_cutoff'] is True, 'manifest_support')
                by_code = {c['channel']: c for c in qcell['components']}
                components = [by_code[code] for code in required]
                need(native.same(cell['view_sha256'], [c['view_sha256'] for c in components])
                     and all(c['status'] == 'complete' and native.same(cell['first'], c['first'])
                             and native.same(cell['period'], producer.pair(Fraction(10**9)/Fraction(*c['rate'])))
                             and native.same(cell['shape'][1], c['count']) for c in components), 'manifest_view')
            else:
                need(cell['reason'] in ('metadata_unknown','operational_ineligible','qualification_unknown','grid_mismatch','no_precontext','reconstruction_unknown')
                     and all(cell[k] is None for k in ('array','shape','first','period','precontext_count','view_sha256')), 'manifest_unavailable')
        need(original['cohort'] == all(available), 'manifest_common')


def placeholder(h, status):
    return {'seconds':h, 'status':status, 'features':None}


def extract(components, row, started):
    try:
        prepared = activity._piece_geometry(components, row['family'])
        centers, powers, floors = activity._noise(prepared, row['t0_ns'])
    except activity.InvalidInput:
        return [placeholder(h, 'BAD_NOISE') for h in HORIZONS]
    cells = []
    for h in HORIZONS:
        deadline(started)
        cutoff = row['t0_ns'] + h * 10**9
        age_ns = cutoff - row['pick_ns']
        if age_ns < 250_000_000:
            cells.append(placeholder(h,'UNSUPPORTED'))
            continue
        try:
            peaks = [max(abs(value-center) for value in activity._window_values(pieces,row['pick_ns'],cutoff))
                     for pieces,center in zip(prepared,centers)]
            noise = [math.sqrt(power) for power in powers]
            best = max(range(3), key=lambda j: peaks[j]/noise[j])
            amplitude, scale = peaks[best], noise[best]
            features = {'y':math.log10(max(amplitude,1.0)/scale), 'L':-math.log10(scale),
                        'censored':amplitude <= 1.0, 'u':age_ns/10**9,
                        'selected_component':components[best]['name'], 'noise_floor':floors[best],
                        'peak':amplitude, 'noise':scale}
            need(all(math.isfinite(features[k]) for k in ('y','L','u','peak','noise')), 'feature_numeric')
            cells.append({'seconds':h,'status':'available','features':features})
        except (activity.InvalidInput, ValueError, OverflowError):
            cells.append(placeholder(h,'BAD_WINDOW'))
    return cells


def run(plan, qualified_v2, bodies, decode_record, metadata, tensor_manifest):
    """No actual IO authority: root binds originals, module pins and live controls."""
    started = time.monotonic()
    records = native.inputs(plan,qualified_v2,bodies,metadata,
                            {'grouping_frozen':False,'prior_support_floor_pass':False})
    need(callable(decode_record), 'decoder')
    manifest_bind(plan,qualified_v2,metadata,tensor_manifest)
    events = []
    for row,qrow,meta,original in zip(plan['rows'],qualified_v2['rows'],metadata,tensor_manifest['rows']):
        deadline(started)
        common = original['cohort']
        status = ('DEFERRED_DEV' if row['partition'] == 'DEV' else 'NON_COMMON' if not common else
                  'UNSUPPORTED' if not meta['group_eligible'] or row['family'] is None
                  or not all(c['joint']['status']=='complete' for c in qrow['cells']) else None)
        components = None
        if status is None:
            try:
                components,_ = native.reconstruct(plan,row,qrow,records,bodies,decode_record,started)
                cells = extract(components,row,started)
            except native.UnsupportedNativeGrid:
                cells = [placeholder(h,'UNSUPPORTED') for h in HORIZONS]
            finally:
                components = None
        else:
            cells = [placeholder(h,status) for h in HORIZONS]
        events.append({'slot':row['ordinal'],'partition':row['partition'],'mw':float(meta['mw']),
                       'group':meta['group'],'common':common,'horizons':cells})
    common_train = [e for e in events if e['partition']=='TRAIN' and e['common']]
    complete = [e for e in common_train if all(c['status']=='available' for c in e['horizons'])]
    counts = {str(h):{status:sum(e['horizons'][j]['status']==status for e in events) for status in STATUSES}
              for j,h in enumerate(HORIZONS)}
    aggregate = {'rows':65,'cells':195,'train':41,'dev':24,'test_excluded':31,
                 'original_common_train_events':len(common_train),'all_horizon_available_train_events':len(complete),
                 'fixed_common_train_complete':bool(common_train) and len(complete)==len(common_train),'status_counts':counts}
    result = {'schema':SCHEMA,'events':events,'aggregate':aggregate,
              'claims':{'fit_authorized':False,'physically_calibrated':False,'accuracy_improved':False,
                        'independent_bulk_preservation_verified':False,'novelty_verified':False,'published_superiority_verified':False}}
    need(len(producer.canonical(result))<=MAX_PRIVATE and len(producer.canonical(aggregate))<=MAX_PUBLIC,'output_cap')
    deadline(started)
    return result
