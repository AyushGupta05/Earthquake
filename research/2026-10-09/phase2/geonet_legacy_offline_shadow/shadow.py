"""Pure offline cohort processing. The parent owns authorization and bounded I/O.

This module has no file reader, CLI, network, process launcher or write operation.
A caller must not read real inputs before its separate post-freeze authorization.
"""
import hashlib
import json
import re
import comparison
import projection

PROTOCOL = 'geonet_legacy_offline_shadow_v1'
MEMBERS = ('original_qml', 'fresh_qml', 'native_scml')
PROVENANCE_KEYS = ('original_plan_sha256', 'original_manifest_sha256',
                   'original_census_clock_source_sha256', 'processing_source_mapping_sha256',
                   'runtime_sha256', 'pushed_freeze', 'parent_authorization_receipt_sha256')
HEX = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')


def verify_inputs(events, provenance):
    if not isinstance(provenance, dict) or set(provenance) != set(PROVENANCE_KEYS):
        raise ValueError('provenance_schema')
    for name in PROVENANCE_KEYS:
        pattern = COMMIT if name == 'pushed_freeze' else HEX
        if not isinstance(provenance[name], str) or not pattern.fullmatch(provenance[name]):
            raise ValueError('provenance_pin:' + name)
    if not isinstance(events, list) or len(events) != 6:
        raise ValueError('fixed_six_event_denominator')
    seen = set()
    seen_candidates = set()
    total = 0
    for event in events:
        if not isinstance(event, dict) or set(event) != {
                'event_id', 'original_t0_us', 'native_profile', 'body_pins', *MEMBERS}:
            raise ValueError('event_input_schema')
        identifier = event['event_id']
        candidate = projection.mapped_id(identifier)
        if identifier in seen:
            raise ValueError('duplicate_event_identity')
        seen.add(identifier)
        if candidate in seen_candidates:
            raise ValueError('event_ID_mapping_collision')
        seen_candidates.add(candidate)
        t0 = event['original_t0_us']
        if t0 is not None:
            if type(t0) is not int:
                raise ValueError('original_T0_type')
            try:
                projection.iso_us(t0)
            except (OverflowError, ValueError):
                raise ValueError('original_T0_range') from None
        if event['native_profile'] not in projection.SCML:
            raise ValueError('explicit_native_profile_required')
        pins = event['body_pins']
        if not isinstance(pins, dict) or set(pins) != set(MEMBERS):
            raise ValueError('body_pin_schema')
        for name in MEMBERS:
            body, pin = event[name], pins[name]
            if not isinstance(body, bytes) or len(body) > 4 * projection.MIB:
                raise ValueError('body_bound:' + name)
            total += len(body)
            if not isinstance(pin, dict) or set(pin) != {'sha256', 'bytes'} or type(pin['bytes']) is not int:
                raise ValueError('body_pin_schema:' + name)
            if not isinstance(pin['sha256'], str) or not HEX.fullmatch(pin['sha256']):
                raise ValueError('body_pin_hash_format:' + name)
            if pin['bytes'] != len(body) or pin['sha256'] != hashlib.sha256(body).hexdigest():
                raise ValueError('body_pin_mismatch:' + name)
    if total > 96 * projection.MIB:
        raise ValueError('cohort_input_bound')
    return total


def run_shadow(events, provenance):
    """Return private JSON-compatible results; no mutation of caller inputs.

    Provenance is declarative. This function cannot prove pre-read authorization,
    a push, a parent's watchdog or historical clocks: parent receipts must bind
    and independently verify those before loading any actual bytes.
    """
    total = verify_inputs(events, provenance)
    results = []
    for event in events:
        profile = event['native_profile']
        native = projection.project(event['native_scml'], event['event_id'], 'scml', profile)
        # A contradictory native root never lends its supplied profile to QML.
        bound = native.get('source_profile') == profile and native.get('status') == 'ok'
        parsed = {}
        for name in ('original_qml', 'fresh_qml'):
            if bound:
                parsed[name] = projection.project(event[name], event['event_id'], 'qml', profile)
            else:
                # Plain core QML can still be parsed; version-specific fields
                # must remain unknown without a independently recognized pair.
                parsed[name] = projection.project(event[name], event['event_id'], 'qml')
        item = comparison.event_result(parsed['original_qml'], parsed['fresh_qml'], native,
                                       event['original_t0_us'])
        item['native_profile_binding'] = {'supplied': profile, 'recognized': native.get('source_profile'),
                                          'bound': bound, 'deployed_converter_proved': False}
        item['input_body_pins'] = {name: dict(event['body_pins'][name]) for name in MEMBERS}
        results.append(item)
    output = {'protocol_id': PROTOCOL, 'stage': 'post_collection_exploratory_compatibility_shadow',
              'provenance': dict(provenance), 'input_body_bytes': total,
              'events': results, 'aggregate': comparison.aggregate(results),
              'original_results_mutated': False, 'network_requests': 0,
              'parent_pre_read_authorization_independently_verified_here': False,
              'parent_watchdog_independently_verified_here': False}
    serialized = json.dumps(output, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(serialized) > 8 * projection.MIB:
        # No partial/truncated diagnostic is promoted; caller retains the
        # untouched eighteen input pins and writes a separate bounded failure.
        raise ValueError('output_bound')
    return output
