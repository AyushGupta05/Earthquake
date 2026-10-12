"""Bounded-reader API. No filesystem enumeration or producer implementation."""
from plan_validation import validate
from replay import replay, CLAIMS, MAX_PRIVATE
from strict import Reject, canonical, keys, load, member, pin, sha

PROTOCOL = 'geonet-POST-prefix-independent-audit-v2'
PROPOSAL_SHA = 'b22e1245440622f6939073a56081b4e29bbbf23e940e12b128515d76463536be'
SCHEMA_SHA = '68d23689b41ba79939e7e06442c8092ea936e868f730d446740786e707c4b5f6'
ADDENDUM_SHA = 'c75953d38d2f99a903c2089a6722c2695af5e86e4ee63bc11ffa2844278a4548'


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
    for field, expected_value in (('schema', 'geonet-POST-prefix-qualification-v2'),
                                  ('study', plan['study']), ('reason', 'supported')):
        if type(producer[field]) is not str or producer[field] != expected_value:
            raise Reject('producer_identity')
    if (type(producer['batches']) is not list or len(producer['batches']) != 17
            or type(producer['rows']) is not list or len(producer['rows']) != 65
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
            'rows': 65, 'cells': 195, 'fresh_result': fresh}
    if len(canonical(verdict)) > MAX_PRIVATE:
        raise Reject('bounded_audit_output_unavailable')
    return verdict
