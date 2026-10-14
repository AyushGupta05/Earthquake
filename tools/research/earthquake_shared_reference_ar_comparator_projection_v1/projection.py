"""Pure historical comparator projection. ROOT authenticates the expected contract.

No closure is inferred here. Dependencies are ROOT-bound frozen canonical,
packet_digest, L validate_population and comparators_checked (curried with the
held schema/authority). The returned callback has the exact bridge ABI.
"""
import copy
import hashlib

SEEDS = (20261012, 20261013)
REUSED = tuple((s, a) for s in SEEDS for a in ('S', 'P', 'D'))
STRONG = tuple((s, a) for s in SEEDS for a in ('B', 'F', 'H', 'T'))
CLOSURE = {'verified', 'no_optimizer', 'checkpoint_sha256', 'source_sha256',
           'packet_sha256', 'independent_audit_sha256'}
ORIGIN = {'seed', 'arm', 'checkpoint_sha256', 'source_sha256', 'packet_sha256',
          'independent_audit_sha256', 'origin_sha256', 'records_sha256'}


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(value):
    need(type(value) is str and len(value) == 64 and
         all(c in '0123456789abcdef' for c in value), 'digest')


def pin(raw):
    need(type(raw) is bytes and len(raw) > 0, 'canonical_bytes')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def ordered(items, pairs, name):
    need(type(items) is list and len(items) == len(pairs), name)
    need(all(type(v) is dict and type(v.get('seed')) is int and
             type(v.get('arm')) is str and (v['seed'], v['arm']) == pair
             for v, pair in zip(items, pairs)), name)


def make_projector(expected, *, expected_pin, canonical, packet_digest,
                   validate_population, check_closed):
    """ROOT must independently authenticate expected AND hold expected_pin.

    expected contains exact scope, receipt, canonical/raw input pins, and 14
    historical closures plus separately authenticated comparison closures. This
    is a mapper/checker of that contract, never an authenticator or authorizer.
    """
    need(callable(canonical) and callable(packet_digest) and
         callable(validate_population) and callable(check_closed), 'frozen_dependencies')
    need(type(expected) is dict and pin(canonical(expected)) == expected_pin,
         'held_contract_pin')
    held = copy.deepcopy(expected)
    need(set(held) == {'schema', 'scope', 'receipt', 'inputs', 'joins'}, 'contract_fields')
    need(held['schema'] == 'root-held-L-comparator-projection-v1', 'contract_schema')
    ordered(held['joins'], REUSED + STRONG, 'join_order')
    inputs = held['inputs']
    need(type(inputs) is dict and set(inputs) == {'reused_scores', 'stronger_envelope',
         'closed_comparator_report', 'comparator_origins'}, 'input_fields')
    need(type(inputs['reused_scores']) is list and len(inputs['reused_scores']) == 6,
         'six_pins')
    for value in inputs['reused_scores'] + [inputs[k] for k in
            ('stronger_envelope', 'closed_comparator_report', 'comparator_origins')]:
        need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
             type(value['bytes']) is int and value['bytes'] > 0, 'input_pin')
        digest(value['sha256'])
    need(all(v['bytes'] <= 2*1024*1024 for v in inputs['reused_scores']) and
         all(inputs[k]['bytes'] <= 16*1024*1024 for k in
             ('stronger_envelope', 'closed_comparator_report', 'comparator_origins')), 'frozen_caps')

    def project_comparators(scope, packet, decoded_six, decoded_stronger,
                            decoded_closed_report, decoded_origins, input_receipt):
        # Authenticate exact held input identities before any output is built.
        need(canonical(scope) == canonical(held['scope']) and
             canonical(input_receipt) == canonical(held['receipt']), 'held_scope_receipt')
        need(input_receipt['schema'] == 'root-L-bridge-input-authentication-v1' and
             input_receipt['decision'] == 'authorized' and input_receipt['scope'] == scope and
             input_receipt['source_pins'] == scope['source_pins'] and
             input_receipt['original_source_pins'] == scope['original_source_pins'], 'receipt_binding')
        need(scope['historical_pins'] == {k: inputs[k] for k in
             ('reused_scores', 'stronger_envelope')}, 'raw_historical_pins')
        need(all(scope['input_pins'][k] == inputs[k] for k in
             ('closed_comparator_report', 'comparator_origins')), 'raw_report_origins_pins')
        current = packet_digest(packet)
        digest(current)
        need(current == input_receipt['packet_sha256'], 'native_packet_binding')
        ordered(decoded_six, REUSED, 'six_order')
        ordered(decoded_stronger, STRONG, 'eight_order')
        need([pin(canonical(v)) for v in decoded_six] == inputs['reused_scores'] and
             pin(canonical(decoded_stronger)) == inputs['stronger_envelope'] and
             pin(canonical(decoded_closed_report)) == inputs['closed_comparator_report'] and
             pin(canonical(decoded_origins)) == inputs['comparator_origins'], 'canonical_input_binding')
        report = decoded_closed_report
        need(type(report) is dict and set(report) == {'schema', 'status', 'checked',
             'fits', 'stronger', 'paired', 'advance', 'authority_sha256'} and
             report['schema'] == 'marked-sixfit-independent-aggregate-v1' and
             report['status'] == 'pass' and type(report['checked']) is int and
             report['checked'] == 396, 'full_closed_report')
        digest(report['authority_sha256'])
        ordered(report['fits'], REUSED, 'report_six_order')
        ordered(report['stronger'], STRONG, 'report_eight_order')
        ordered(decoded_origins, REUSED + STRONG, 'origin_order')
        dev = [r['ordinal'] for r in packet['rows'] if r['common'] and r['partition'] == 'DEV']
        train = [r['ordinal'] for r in packet['rows'] if r['common'] and r['partition'] == 'TRAIN']
        need(len(dev) == len(set(dev)) == 22 and len(train) == len(set(train)) == 65,
             'same87_cohort')
        expected_records = [(i, h) for i in dev for h in (1, 3, 5)]
        for item, origin, pair in zip(report['fits'] + report['stronger'], decoded_origins,
                                      REUSED + STRONG):
            records = item['records']
            need(type(records) is list and len(records) == 66 and
                 [(r['ordinal'], r['horizon']) for r in records] == expected_records,
                 'closed_record_order')
            need(ORIGIN <= set(origin), 'origin_fields')
            for key in ORIGIN - {'seed', 'arm'}:
                digest(origin[key])
            need(origin['records_sha256'] == pin(canonical(records))['sha256'], 'origin_records')
        # The frozen independent checker verifies descriptors, targets, scalar
        # types, complete metrics and old guards against the actual same cohort.
        # ROOT supplies a closure of the frozen function, not a Boolean result.
        check_closed(report, decoded_origins, packet)
        out = []
        for index, (raw, item, origin, join, pair) in enumerate(zip(
                decoded_six + decoded_stronger, report['fits'] + report['stronger'],
                decoded_origins, held['joins'], REUSED + STRONG)):
            need(set(join) == {'seed', 'arm', 'historical_closure', 'comparison_closure',
                 'comparison_packet_sha256', 'records_sha256', 'semantics'}, 'join_fields')
            need(join['comparison_packet_sha256'] == current and
                 join['records_sha256'] == origin['records_sha256'] and
                 join['semantics'] == 'same-cohort-only; historical-fit-packet-retained', 'explicit_cohort_join')
            historical = join['historical_closure']
            comparison = join['comparison_closure']
            for closure in (historical, comparison):
                need(type(closure) is dict and set(closure) == CLOSURE and
                     closure['verified'] is True and closure['no_optimizer'] is True, 'held_closed_evidence')
                for key in CLOSURE - {'verified', 'no_optimizer'}:
                    digest(closure[key])
            need(all(historical[k] == origin[k] for k in CLOSURE - {'verified', 'no_optimizer'}),
                 'historical_origin_binding')
            need(comparison == dict(historical, packet_sha256=current), 'comparison_closure_join')
            if index < 6:
                need(raw['status'] == 'complete' and raw['no_optimizer'] is True and
                     raw['study'] == 'earthquake-TRAIN115-marked-noise-fitting-v2' and
                     raw['packet_sha256'] == historical['packet_sha256'] and
                     raw['checkpoint_sha256'] == historical['checkpoint_sha256'] and
                     raw['source_pins'] == scope['original_source_pins'] and
                     raw['admission_sha256'] == scope['input_pins']['original_admission']['sha256'],
                     'six_source_admission_binding')
            else:
                need(set(raw) == {'seed', 'arm', 'predictions', 'closure'} and
                     raw['closure'] == comparison, 'original_stronger_envelope')
            value = copy.deepcopy(raw)
            if 'packet_sha256' in value:
                value['historical_packet_sha256'] = value['packet_sha256']
            value.update(status='complete', no_optimizer=historical['no_optimizer'],
                         packet_sha256=current, checkpoint_sha256=historical['checkpoint_sha256'],
                         independent_closure=copy.deepcopy(comparison),
                         historical_closure=copy.deepcopy(historical), origin=copy.deepcopy(origin),
                         comparison_join=copy.deepcopy(join),
                         original_packet_sha256_semantics=join['semantics'])
            # Stronger envelope forecasts lack seed/arm/status in the old ABI.
            # Add identity only; do not cast, round, replace or recompute numbers.
            for prediction in value['predictions']:
                for key, wanted in (('seed', pair[0]), ('arm', pair[1]), ('status', 'complete')):
                    need(key not in prediction or (type(prediction[key]) is type(wanted) and
                         prediction[key] == wanted), 'forecast_existing_identity')
                    prediction[key] = wanted
            validate_population(value['predictions'], packet, *pair)
            need([(r['ordinal'], r['horizon'], r['target'], r['group']) for r in value['predictions']] ==
                 [(r['ordinal'], r['horizon'], r['target'], r['group']) for r in item['records']],
                 'forecast_report_join')
            out.append(value)
        return {'reused_results': out[:6], 'strong_results': out[6:],
                'origins': copy.deepcopy(decoded_origins)}

    return project_comparators
