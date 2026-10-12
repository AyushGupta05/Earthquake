"""Bounded-reader API. No filesystem enumeration or producer implementation."""
from plan_validation import validate
from replay import replay, CLAIMS, MAX_PRIVATE
from strict import Reject, canonical, keys, load, member, pin, sha

PROTOCOL = 'geonet-TRAIN50-prefix-independent-audit-v1'
PROPOSAL_SHA='36aafbb99d01c269593aae3e86725cccb6e01de88edd9ff5e7fad38f610363f4'
SCHEMA_SHA='3467cb013d8e8b3487edd6b7c0dfee3e94cdd172e8b188dc7db38ab47e8aef3f'
ADDENDUM_SHA='a86adf23e5e18bdb396b01331340c4416796f8962357e4a614b27ce47f27ce11'
BUDGET_SHA='b21ecf0031af32b8c5b80270e48d7bd1ad081c68afc0b4f64c73d3e4a7a06a6b'


def audit(plan_bytes, producer_bytes, bounded_reader, expected):
    """Authenticate declared bytes and fresh replay; external facts remain external.

    expected is exactly {plan,producer}, each {bytes,sha256}. Reader is called
    only for fixed NNN.body.private members from an already validated projection.
    Returns private fresh-result evidence and strict byte/JSON comparison.
    """
    keys(expected, ('plan', 'producer'))
    for name, raw, cap in (('plan', plan_bytes, 131_072), ('producer', producer_bytes, MAX_PRIVATE)):
        pin(expected[name], cap)
        if type(raw) is not bytes or len(raw) != expected[name]['bytes'] or sha(raw) != expected[name]['sha256']:
            raise Reject('input_pin')
    plan = validate(load(plan_bytes, 131_072))
    producer = load(producer_bytes, MAX_PRIVATE)
    keys(producer, ('schema', 'study', 'disposition', 'reason', 'batches', 'records', 'rows', 'aggregate', 'claims'))
    for field, expected_value in (('schema', 'geonet-TRAIN50-prefix-qualification-v1'),
                                  ('study', plan['study']), ('reason', 'supported')):
        if type(producer[field]) is not str or producer[field] != expected_value:
            raise Reject('producer_identity')
    if (type(producer['batches']) is not list or len(producer['batches']) != 13
            or type(producer['rows']) is not list or len(producer['rows']) != 50
            or type(producer['records']) is not list or type(producer['aggregate']) is not dict):
        raise Reject('producer_structure')
    keys(producer['claims'], CLAIMS)
    if any(producer['claims'][key] is not False for key in CLAIMS):
        raise Reject('claim')
    if producer['disposition'] != 'complete' or type(producer['disposition']) is not str:
        raise Reject('producer_incomplete')
    def body(ordinal, size):
        batch = plan['batches'][ordinal]
        return member(bounded_reader, '%03d.body.private' % ordinal,
                      {'bytes': size, 'sha256': batch['body_sha256']}, 8_388_608)
    fresh = replay(plan, body)
    # Comparing canonical JSON rather than Python equality keeps bool/int and
    # scalar types distinct. All fresh scientific decisions were independently
    # computed; producer values are used only for this final equality check.
    matches = canonical(fresh) == canonical(producer)
    complete = matches and fresh['disposition'] == 'complete'
    verdict = {'protocol': PROTOCOL, 'agreement': matches, 'fresh_complete': fresh['disposition'] == 'complete',
            'audit_pass': complete, 'reason': 'supported' if complete else 'replay_disagreement' if not matches else 'fresh_incomplete',
            'rows':50,'cells':150, 'fresh_result': fresh}
    if len(canonical(verdict)) > MAX_PRIVATE:
        raise Reject('bounded_audit_output_unavailable')
    return verdict
