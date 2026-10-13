"""Explicit old-model/new-comparison population join; never new old-model forecasts."""
import copy
import secure_io as io

ORDER=[(s,a) for s in (20261012,20261013) for a in ('B','F','H','T')]


def project(packet,old,join_proof_pin,packet_sha256):
    """Caller has independently verified original closure and native semantic truth.

    This function additionally compares actual roster/forecast values. A hash or
    shape alone is not sufficient authority; no caller-supplied override is allowed.
    """
    keys={'schema','original_packet_pins','original_packet_sha256','roster','fits'}
    io.need(type(old) is dict and set(old)==keys and old['schema']=='root-original-strong-comparison-input-v1','strong_input')
    io.need(type(old['original_packet_pins']) is dict and set(old['original_packet_pins'])=={'archive','manifest'},'original_packet_pins')
    for p in old['original_packet_pins'].values():io.pin_check(p,128*1024*1024)
    io.pin_check(join_proof_pin);io.pin_check(dict(bytes=1,sha256=packet_sha256));io.pin_check(dict(bytes=1,sha256=old['original_packet_sha256']))
    rows=[r for r in packet['rows'] if r['common']]
    expected=[dict(ordinal=r['ordinal'],partition=r['partition'],mw=r['mw'],group=r['group'],horizons=[1,3,5]) for r in rows]
    io.need(len(expected)==87 and sum(r['partition']=='TRAIN' for r in rows)==65 and sum(r['partition']=='DEV' for r in rows)==22
            and old['roster']==expected,'same87_actual_roster')
    io.need(type(old['fits']) is list and len(old['fits'])==8 and [(x['seed'],x['arm']) for x in old['fits']]==ORDER,'strong_order')
    dev=[r for r in rows if r['partition']=='DEV'];answers=[]
    for fit in old['fits']:
        io.need(fit['status']=='complete' and fit['no_optimizer'] is True and fit['packet_sha256']==old['original_packet_sha256'],'original_fit_binding')
        closed=fit['independent_closure'];io.need(type(closed) is dict and set(closed)=={'verified','checkpoint_sha256','source_sha256','packet_sha256','no_optimizer','proof_pin'}
                and closed['verified'] is True and closed['no_optimizer'] is True and closed['checkpoint_sha256']==fit['checkpoint_sha256']
                and closed['packet_sha256']==old['original_packet_sha256'],'old_closure_binding')
        io.pin_check(closed['proof_pin']);io.pin_check(fit['result_pin']);io.pin_check(dict(bytes=1,sha256=closed['source_sha256']));io.pin_check(dict(bytes=1,sha256=fit['checkpoint_sha256']))
        predictions=fit['predictions'];io.need(type(predictions) is list and len(predictions)==66,'old66')
        for record,(row,h) in zip(predictions,[(r,h) for r in dev for h in (1,3,5)]):
            io.need(record['seed']==fit['seed'] and record['arm']==fit['arm'] and record['ordinal']==row['ordinal'] and record['horizon']==h
                    and record['group']==row['group'] and record['target']==row['mw'] and record['status']=='complete','old_record_population')
        value=copy.deepcopy(fit);value['packet_sha256']=packet_sha256
        value['independent_closure']={k:closed[k] for k in ('verified','checkpoint_sha256','source_sha256','no_optimizer')}
        value['independent_closure']['packet_sha256']=packet_sha256
        value['origin']=dict(schema='old-model-new-comparison-join-v1',packet_sha256_semantics='comparison_population_only',
                            original_packet_sha256=old['original_packet_sha256'],original_packet_pins=copy.deepcopy(old['original_packet_pins']),
                            original_result_pin=copy.deepcopy(fit['result_pin']),original_checkpoint_sha256=fit['checkpoint_sha256'],
                            original_source_sha256=closed['source_sha256'],original_closure_proof_pin=copy.deepcopy(closed['proof_pin']),
                            comparison_join_proof_pin=copy.deepcopy(join_proof_pin),old_model_reexecuted=False)
        if 'origin' in fit:value['origin']['original_fit_origin']=copy.deepcopy(fit['origin'])
        if 'original_packet_sha256_semantics' in fit:
            value['origin']['original_packet_sha256_semantics']=copy.deepcopy(fit['original_packet_sha256_semantics'])
        io.need(value['predictions']==fit['predictions'],'prediction_changed');answers.append(value)
    return answers
