"""Invented XML only. No catalogue data, waveforms, files, network or author code."""
import copy
import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
import comparison as c
import projection as p
import shadow as s

T = '2020-01-01T00:00:00Z'
M = p.PREFIX


def node(parent, namespace, tag, text=None, **attrs):
    item = ET.SubElement(parent, '{' + namespace + '}' + tag, attrs)
    if text is not None:
        item.text = text
    return item


def fixture(native=False, version='0.11', event='invented', picks=True, status=None, weight='1', flags=None,
            modification=None, qc=None, qc_namespace=None, creation=T, station='A', network='NZ', pick_time=T):
    ns = p.SCML[version] if native else p.B
    root = ET.Element('{' + ns + '}seiscomp', version=version) if native else ET.Element('{' + p.Q + '}quakeml')
    params = node(root, ns, 'EventParameters' if native else 'eventParameters')
    ev = node(params, ns, 'event', publicID=event if native else M + event)
    node(ev, ns, 'preferredOriginID', 'o' if native else M + 'o')
    if native:
        node(ev, ns, 'originReference', 'o')
    ec = node(ev, ns, 'creationInfo')
    if creation is not None:
        node(ec, ns, 'creationTime', creation)
    origin = node(params if native else ev, ns, 'origin', publicID='o' if native else M + 'o')
    for name, value in (('time', T), ('latitude', '1'), ('longitude', '2'), ('depth', '3' if native else '3000')):
        node(node(origin, ns, name), ns, 'value', value)
    oc = node(origin, ns, 'creationInfo')
    if creation is not None:
        node(oc, ns, 'creationTime', creation)
    if modification is not None:
        node(oc, p.SCML[version], 'modificationTime', modification)
    arr = node(origin, ns, 'arrival')
    node(arr, ns, 'phase', 'P')
    node(arr, ns, 'pickID', 'p' if native else M + 'p')
    if weight is not None:
        node(arr, ns, 'weight' if native else 'timeWeight', weight)
    for key, value in (flags or {}).items():
        node(arr, ns, key, value)
    if picks:
        pick = node(params if native else ev, ns, 'pick', publicID='p' if native else M + 'p')
        if pick_time is not None:
            node(node(pick, ns, 'time'), ns, 'value', pick_time)
        node(pick, ns, 'waveformID', networkCode=network, stationCode=station)
        if status is not None:
            node(pick, ns, 'evaluationStatus', status)
    if qc is not None:
        mag = node(origin if native else ev, ns, 'stationMagnitude', publicID='m' if native else M + 'm')
        node(mag, ns, 'amplitudeID', 'missing' if native else M + 'missing')
        expected = ns if native else p.SCML[version] if version == '0.11' else p.B
        node(mag, qc_namespace or expected, 'passedQC', qc)
    return root


def body(root):
    return ET.tostring(root, encoding='utf-8')


def project(native=False, version='0.11', profile=None, **kwargs):
    return p.project(body(fixture(native, version, **kwargs)), kwargs.get('event', 'invented'),
                     'scml' if native else 'qml', profile)


def modify(root, name, text, native=False, version='0.11'):
    ns = p.SCML[version] if native else p.B
    root.find('.//{' + ns + '}' + name).text = text
    return root


class LegacyProjectionTests(unittest.TestCase):
    def test_contradictory_xml_encoding_declaration_unknown(self):
        for native in (True, False):
            data = b'<?xml version="1.0" encoding="UTF-16"?>' + body(fixture(native))
            self.assertEqual(p.project(data, 'invented', 'scml' if native else 'qml')['status'],
                             'unknown_representation')

    def test_non_utf8_encoding_declaration_unknown(self):
        for encoding in ('ISO-8859-1', 'US-ASCII', 'UTF-32'):
            data = ('<?xml version="1.0" encoding="' + encoding + '"?>').encode() + body(fixture())
            self.assertEqual(p.project(data, 'invented', 'qml')['status'], 'unknown_representation')
        root = fixture(); node(root.find('.//{' + p.B + '}event/{' + p.B + '}creationInfo'), p.B, 'author', '\u00e9')
        data = b'<?xml version="1.0" encoding="ISO-8859-1"?>' + body(root)
        self.assertEqual(p.project(data, 'invented', 'qml')['status'], 'unknown_representation')

    def test_utf8_declaration_and_bom_keep_projection(self):
        for native in (True, False):
            representation = 'scml' if native else 'qml'; clean = body(fixture(native))
            for encoding in ('UTF-8', 'utf-8'):
                for bom in (b'', b'\xef\xbb\xbf'):
                    data = bom + ('<?xml version="1.0" encoding="' + encoding + '"?>').encode() + clean
                    self.assertEqual(p.project(data, 'invented', representation),
                                     p.project(clean, 'invented', representation))

    def test_ignored_outside_metadata_encoding_text_not_a_declaration(self):
        clean = body(fixture())
        data = b'<!-- <?xml version="1.0" encoding="UTF-16"?> --><?invented encoding="UTF-16"?>' + clean
        self.assertEqual(p.project(data, 'invented', 'qml'), p.project(clean, 'invented', 'qml'))

    def test_outside_comment_declaration_like_text_ignored(self):
        for native in (True, False):
            clean = body(fixture(native)); representation = 'scml' if native else 'qml'
            for text in (b'<!DOCTYPE invented>', b'<!ENTITY invented "text">'):
                data = b'<!-- ' + text + b' -->' + clean + b'<!-- ' + text + b' -->'
                self.assertEqual(p.project(data, 'invented', representation),
                                 p.project(clean, 'invented', representation))

    def test_outside_pi_declaration_like_text_ignored(self):
        for native in (True, False):
            clean = body(fixture(native)); representation = 'scml' if native else 'qml'
            data = b'<?invented <!DOCTYPE invented> <!ENTITY invented "text">?>' + clean
            self.assertEqual(p.project(data, 'invented', representation),
                             p.project(clean, 'invented', representation))

    def test_real_doctype_rejected_before_internal_subset_or_external_reference(self):
        for declaration in (b'<!DOCTYPE invented>',
                            b'<!DOCTYPE invented [<!ENTITY e "text">]>',
                            b'<!DOCTYPE invented SYSTEM "http://example.invalid/not-requested">'):
            self.assertEqual(p.project(declaration + body(fixture()), 'invented', 'qml')['reason'],
                             'unsafe_XML')
        self.assertEqual(p.project(b'<!ENTITY e "text">' + body(fixture()), 'invented', 'qml')['status'],
                         'unknown_representation')

    def test_inside_comment_declaration_like_text_stays_unknown(self):
        root = fixture(); root.insert(0, ET.Comment(' <!DOCTYPE invented> <!ENTITY e "text"> '))
        self.assertEqual(p.project(body(root), 'invented', 'qml')['reason'],
                         'unsupported_XML_comment_or_PI_inside_root')

    def test_foreign_extension_collision_is_unknown(self):
        for native in (True, False):
            root = fixture(native)
            node(root, 'http://example.invalid/invented-extension', 'object', publicID=M + 'p')
            self.assertEqual(p.project(body(root), 'invented', 'scml' if native else 'qml')['reason'],
                             'wrong_typed_publicID_collision')

    def test_unrelated_foreign_extension_identity_not_projected(self):
        for native in (True, False):
            root = fixture(native)
            node(root, 'http://example.invalid/invented-extension', 'object', publicID=M + 'outside')
            result = p.project(body(root), 'invented', 'scml' if native else 'qml')
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(len(result['accepted_picks']), 1)

    def test_canonical_geometry_signed_zero(self):
        for value in ('0', '-0', '+0', '-0.0', '-0e-8'):
            for scale in (1, 1000):
                self.assertEqual(p.canonical_number(value, scale), '0')

    def test_signed_zero_geometry_does_not_break_content_guard(self):
        roots = [fixture(False), fixture(True)]
        for root, native in zip(roots, (False, True)):
            ns = p.SCML['0.11'] if native else p.B
            for name in ('latitude', 'longitude', 'depth'):
                root.find('.//{' + ns + '}' + name + '/{' + ns + '}value').text = '-0' if native else '0'
        left = p.project(body(roots[0]), 'invented', 'qml')
        right = p.project(body(roots[1]), 'invented', 'scml')
        self.assertIs(c.compare(left, right)['same_record_content'], True)

    def test_native_creation_whitespace_only_candidate_stripped_raw_retained(self):
        for name in ('agencyID', 'agencyURI', 'author', 'authorURI', 'creationTime', 'modificationTime', 'version'):
            root = fixture(True, creation=None)
            ns = p.SCML['0.11']; ci = root.find('.//{' + ns + '}event/{' + ns + '}creationInfo')
            node(ci, ns, name, ' \t ')
            result = p.project(body(root), 'invented', 'scml')
            expected = M + 'NA' if name in ('agencyURI', 'authorURI') else ''
            self.assertEqual(result['event_creation'][name], expected)
            self.assertEqual(result['raw_event_creation']['{' + ns + '}' + name], ' \t ')

    def test_native_creation_non_XML_whitespace_not_stripped(self):
        root = fixture(True); ns = p.SCML['0.11']
        node(root.find('.//{' + ns + '}event/{' + ns + '}creationInfo'), ns, 'author', '\u00a0')
        result = p.project(body(root), 'invented', 'scml')
        self.assertEqual(result['event_creation']['author'], '\u00a0')

    def test_xml_space_inside_root_is_unknown(self):
        for native in (True, False):
            for value in ('preserve', 'default', 'unsupported'):
                root = fixture(native)
                root.set('{http://www.w3.org/XML/1998/namespace}space', value)
                self.assertEqual(p.project(body(root), 'invented', 'scml' if native else 'qml')['reason'],
                                 'unsupported_XML_space_attribute')

    def test_root_sibling_identity_collision_is_unknown(self):
        for native in (True, False):
            ns = p.SCML['0.11'] if native else p.B
            for kind in ('pick', 'origin', 'amplitude'):
                root = fixture(native)
                node(root, ns, kind, publicID='p' if native else M + 'p')
                self.assertEqual(p.project(body(root), 'invented', 'scml' if native else 'qml')['status'],
                                 'unknown_representation')

    def test_root_sibling_unrelated_identity_does_not_broaden_projection(self):
        for native in (True, False):
            root = fixture(native); ns = p.SCML['0.11'] if native else p.B
            node(root, ns, 'pick', publicID='outside' if native else M + 'outside')
            result = p.project(body(root), 'invented', 'scml' if native else 'qml')
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(len(result['accepted_picks']), 1)

    def referenced_other_origin(self, root):
        ns = p.SCML['0.11']; params = root.find('{' + ns + '}EventParameters')
        node(params.find('{' + ns + '}event'), ns, 'originReference', 'o2')
        other = copy.deepcopy(params.find('{' + ns + '}origin'))
        other.set('publicID', 'o2'); params.append(other)
        return other.find('{' + ns + '}arrival')

    def test_nonpreferred_referenced_arrival_bad_use_flag_unknown(self):
        root = fixture(True); arrival = self.referenced_other_origin(root)
        node(arrival, p.SCML['0.11'], 'timeUsed', 'yes')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'invalid_native_use_flag')

    def test_nonpreferred_referenced_arrival_duplicate_flag_weight_unknown(self):
        for name in ('timeUsed', 'horizontalSlownessUsed', 'backazimuthUsed', 'weight'):
            root = fixture(True); arrival = self.referenced_other_origin(root); ns = p.SCML['0.11']
            if name != 'weight': node(arrival, ns, name, 'true')
            node(arrival, ns, name, '1')
            self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'duplicate_singleton:' + name)

    def test_valid_nonpreferred_arrival_not_added_to_preferred_comparison(self):
        root = fixture(True); arrival = self.referenced_other_origin(root)
        node(arrival, p.SCML['0.11'], 'timeUsed', 'false')
        result = p.project(body(root), 'invented', 'scml')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['arrivals']), 1)
        self.assertEqual(len(result['accepted_picks']), 1)

    def test_inside_root_comment_scalar_boundary_is_unknown(self):
        for native in (True, False):
            root = fixture(native, weight='0', flags={'timeUsed': ' '} if native else None)
            ns = p.SCML['0.11'] if native else p.B
            scalar = root.find('.//{' + ns + '}' + ('timeUsed' if native else 'pickID'))
            scalar.text = ' '
            comment = ET.Comment('invented boundary')
            comment.tail = 'true' if native else M + 'p'
            scalar.append(comment)
            data = body(root)
            # Default ElementTree discards this boundary and merges text.
            merged = ET.fromstring(data).find('.//{' + ns + '}' + ('timeUsed' if native else 'pickID')).text
            self.assertEqual(merged, ' ' + comment.tail)
            result = p.project(data, 'invented', 'scml' if native else 'qml')
            self.assertEqual(result['reason'], 'unsupported_XML_comment_or_PI_inside_root')
            self.assertIsNone(result['denominators'])
            self.assertIsNone(result['accepted_picks'])

    def test_inside_root_pi_scalar_boundary_is_unknown(self):
        for native in (True, False):
            root = fixture(native)
            ns = p.SCML['0.11'] if native else p.B
            scalar = root.find('.//{' + ns + '}pickID')
            scalar.text = ' '
            instruction = ET.ProcessingInstruction('invented', 'boundary')
            instruction.tail = 'p' if native else M + 'p'
            scalar.append(instruction)
            result = p.project(body(root), 'invented', 'scml' if native else 'qml')
            self.assertEqual(result['reason'], 'unsupported_XML_comment_or_PI_inside_root')

    def test_inside_root_structural_comment_and_pi_are_unknown(self):
        for native in (True, False):
            for item in (ET.Comment('invented'), ET.ProcessingInstruction('invented', 'boundary')):
                root = fixture(native)
                root.insert(0, item)
                self.assertEqual(p.project(body(root), 'invented', 'scml' if native else 'qml')['reason'],
                                 'unsupported_XML_comment_or_PI_inside_root')

    def test_outside_root_comment_and_pi_do_not_enter_projection(self):
        for native in (True, False):
            clean = body(fixture(native))
            outside = b'<!--invented--><?invented outside?>' + clean + b'<?invented outside?><!--invented-->'
            representation = 'scml' if native else 'qml'
            self.assertEqual(p.project(outside, 'invented', representation), p.project(clean, 'invented', representation))

    def test_exact_native_versions(self):
        for version in p.SCML:
            result = project(True, version)
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['source_profile'], version)
            self.assertEqual(result['origin']['depth_m'], '3E+3')

    def test_unsupported_older_newer_roots(self):
        for version in ('0.9', '0.13', '0.14'):
            data = body(fixture(True)).replace(p.SCML['0.11'].encode(), ('http://example.invalid/' + version).encode()).replace(b'version="0.11"', ('version="' + version + '"').encode())
            self.assertEqual(p.project(data, 'invented', 'scml')['status'], 'unknown_representation')

    def test_native_profile_conflict(self):
        self.assertEqual(project(True, profile='0.10')['reason'], 'profile_root_conflict')

    def test_native_root_version_conflict(self):
        root = fixture(True); root.set('version', '0.10')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['status'], 'unknown_representation')

    def test_unsupported_qml_profile(self):
        self.assertEqual(project(profile='0.13')['reason'], 'unsupported_profile')

    def test_plain_core_qml_profileless(self):
        self.assertEqual(project()['status'], 'ok')

    def test_modification_requires_profile(self):
        self.assertEqual(project(modification=T)['reason'], 'version_extension_requires_bound_profile')

    def test_modification_both_versions(self):
        for version in p.SCML:
            for native in (True, False):
                r = project(native, version, profile=version, modification=T)
                self.assertEqual(r['status'], 'ok')
                self.assertEqual(r['origin']['creation']['modificationTime'], T)

    def test_foreign_extension_profile(self):
        self.assertEqual(project(profile='0.10', modification=T)['status'], 'unknown_representation')

    def test_bed_modification_unsupported(self):
        root = fixture(modification=T)
        root.find('.//{' + p.SCML['0.11'] + '}modificationTime').tag = '{' + p.B + '}modificationTime'
        self.assertEqual(p.project(body(root), 'invented', 'qml', '0.11')['status'], 'unknown_representation')

    def test_modification_wrong_placement(self):
        root = fixture(modification=T); ns = p.SCML['0.11']
        mod = root.find('.//{' + ns + '}modificationTime')
        oc = root.find('.//{' + p.B + '}origin/{' + p.B + '}creationInfo')
        oc.remove(mod); root.find('.//{' + p.B + '}pick').append(mod)
        self.assertEqual(p.project(body(root), 'invented', 'qml', '0.11')['status'], 'unknown_representation')

    def test_duplicate_extension(self):
        root = fixture(modification=T)
        ci = root.find('.//{' + p.B + '}origin/{' + p.B + '}creationInfo')
        node(ci, p.SCML['0.11'], 'modificationTime', T)
        self.assertEqual(p.project(body(root), 'invented', 'qml', '0.11')['status'], 'unknown_representation')

    def test_native010_qc_unsupported(self):
        self.assertEqual(project(True, '0.10', qc='true')['reason'], 'unsupported_010_passedQC')

    def test_bed010_qc_unsupported(self):
        self.assertEqual(project(False, '0.10', profile='0.10', qc='true')['reason'], 'unsupported_010_passedQC')

    def test_known011_qc_metadata(self):
        for native in (False, True):
            for value in ('true', 'false', '1', '0', ' true \n'):
                r = project(native, profile='0.11', qc=value)
                self.assertEqual(r['status'], 'ok')
                self.assertEqual(r['magnitude_metadata'][0]['passedQC']['raw'], value)
                self.assertEqual(r['denominators']['accepted_NZ_P_picks'], 1)

    def test_invalid_qc_boolean(self):
        for value in ('yes', '', 'TRUE', '1 0', '\u00a0true\u00a0'):
            self.assertEqual(project(True, qc=value)['reason'], 'invalid_passedQC_lexical')

    def test_qc_wrong_namespace(self):
        self.assertEqual(project(profile='0.11', qc='true', qc_namespace=p.B)['status'], 'unknown_representation')

    def test_qc_missing_profile(self):
        self.assertEqual(project(qc='false')['reason'], 'version_extension_requires_bound_profile')

    def test_qc_wrong_magnitude_parent(self):
        root = fixture(True, qc='true')
        root.find('.//{' + p.SCML['0.11'] + '}stationMagnitude').tag = '{' + p.SCML['0.11'] + '}magnitude'
        self.assertEqual(p.project(body(root), 'invented', 'scml')['status'], 'unknown_representation')

    def test_reported_exact_suppression(self):
        r = project(True, status='reported')
        pick = r['accepted_picks'][0]
        self.assertEqual(pick['evaluation_status'], 'missing')
        self.assertEqual(pick['raw_evaluation_status'], 'reported')
        self.assertTrue(pick['reported_suppressed_candidate'])

    def test_reported_padded_not_suppressed(self):
        r = project(True, status=' reported ')
        self.assertEqual(r['accepted_picks'][0]['evaluation_status'], 'reported')
        self.assertFalse(r['accepted_picks'][0]['reported_suppressed_candidate'])

    def test_rejected_both_formats(self):
        for native in (True, False):
            r = project(native, status='rejected')
            self.assertEqual(r['denominators']['accepted_P_picks'], 0)

    def test_literal_flag_false_drops_weight(self):
        r = project(True, weight='0', flags={'timeUsed': 'false'})
        self.assertIsNone(r['arrivals'][0]['time_weight'])
        self.assertEqual(r['accepted_picks'][0]['network'], 'NZ')
        self.assertEqual(r['arrivals'][0]['native_flags']['weight'], '0')

    def test_missing_weight_default_true(self):
        for text in ('true', '1'):
            r = project(True, weight=None, flags={'timeUsed': text})
            self.assertEqual(r['arrivals'][0]['time_weight'], '1')

    def test_padded_literal_true_false_xpath(self):
        r = project(True, weight='0', flags={'timeUsed': ' true '})
        self.assertIsNone(r['arrivals'][0]['time_weight'])
        self.assertEqual(r['denominators']['accepted_P_picks'], 1)

    def test_horizontal_flag_does_not_default_time(self):
        r = project(True, weight='0', flags={'horizontalSlownessUsed': '1'})
        self.assertIsNone(r['arrivals'][0]['time_weight'])

    def test_unrecognized_flag_unknown(self):
        for key in ('timeUsed', 'horizontalSlownessUsed', 'backazimuthUsed'):
            self.assertEqual(project(True, flags={key: 'yes'})['reason'], 'invalid_native_use_flag')

    def test_empty_weight_is_missing_predicate(self):
        for native in (True, False):
            self.assertEqual(project(native, weight='')['denominators']['accepted_P_picks'], 1)

    def test_invalid_nonfinite_underflow_weights(self):
        for value in ('0', '-1', 'NaN', 'Inf', 'wrong', '1e-9999'):
            for native in (True, False):
                self.assertEqual(project(native, weight=value)['denominators']['accepted_P_picks'], 0)

    def test_all_flags_absent_present_weight(self):
        self.assertEqual(project(True, weight='0')['denominators']['accepted_P_picks'], 0)

    def test_missing_flags_weight_accepted(self):
        self.assertEqual(project(True, weight=None)['denominators']['accepted_P_picks'], 1)

    def test_preferred_not_referenced_unknown(self):
        root = fixture(True); ns = p.SCML['0.11']
        root.find('.//{' + ns + '}originReference').text = 'other'
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'preferred_origin_not_event_referenced')

    def test_dangling_origin(self):
        root = fixture(True); ns = p.SCML['0.11']
        node(root.find('.//{' + ns + '}event'), ns, 'originReference', 'dangling')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'event_origin_reference_ambiguous')

    def test_duplicate_origin_unknown(self):
        root = fixture(True); ns = p.SCML['0.11']
        root.find('{' + ns + '}EventParameters').append(copy.deepcopy(root.find('.//{' + ns + '}origin')))
        self.assertEqual(p.project(body(root), 'invented', 'scml')['status'], 'unknown_representation')

    def test_multiple_event_parameters(self):
        root = fixture(True); root.append(copy.deepcopy(root[0]))
        self.assertEqual(p.project(body(root), 'invented', 'scml')['status'], 'unknown_representation')

    def test_multiple_events(self):
        root = fixture(); ev = root.find('.//{' + p.B + '}event')
        root[0].append(copy.deepcopy(ev))
        self.assertEqual(p.project(body(root), 'invented', 'qml')['status'], 'unknown_representation')

    def test_foreign_structural(self):
        root = fixture(); root.find('.//{' + p.B + '}pick').tag = '{http://invented.invalid}pick'
        self.assertEqual(p.project(body(root), 'invented', 'qml')['reason'], 'foreign_structural_namespace')

    def test_event_identity_not_substituted(self):
        self.assertEqual(p.project(body(fixture()), 'another', 'qml')['status'], 'unknown_representation')

    def test_native_raw_event_translation_substitution_unknown(self):
        r = p.project(body(fixture(True, event='invented a')), 'invented:a', 'scml')
        self.assertEqual(r['reason'], 'event_identity_or_cardinality')

    def test_native_raw_arrival_trimming_cannot_resolve_amplitude_pick(self):
        root = fixture(True); ns = p.SCML['0.11']; origin = root.find('.//{' + ns + '}origin')
        root.find('.//{' + ns + '}pick').set('publicID', 'smi:invented/p')
        modify(root, 'pickID', 'smi:invented/p ', True)
        node(node(origin, ns, 'stationMagnitude', publicID='m'), ns, 'amplitudeID', 'a')
        amp = node(root[0], ns, 'amplitude', publicID='a'); node(amp, ns, 'pickID', 'smi:invented/p')
        r = p.project(body(root), 'invented', 'scml')
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(r['arrivals'][0]['pick_id'], 'smi:invented/p')
        self.assertEqual(r['arrivals'][0]['native_raw_reference_matches'], 0)
        self.assertEqual(r['denominators']['accepted_P_picks'], 0)
        self.assertEqual(r['denominators']['unique_resolved_qualifying_P_reference_ids'], 0)
        self.assertFalse(r['NZ_coverage_known'])

    def test_native_exact_raw_target_cannot_be_substituted_after_trimming(self):
        for prefix in ('smi:', 'quakeml:'):
            for status in ('rejected', None):
                root = fixture(True, status=status); ns = p.SCML['0.11']; base = prefix + 'invented/p'
                target = root.find('.//{' + ns + '}pick'); target.set('publicID', base + ' ')
                modify(root, 'pickID', base + ' ', True)
                other = copy.deepcopy(target); other.set('publicID', base)
                evaluation = other.find('{' + ns + '}evaluationStatus')
                if evaluation is not None: other.remove(evaluation)
                other.find('{' + ns + '}waveformID').set('stationCode', 'SUBSTITUTE')
                root[0].append(other)
                origin = root.find('.//{' + ns + '}origin')
                node(node(origin, ns, 'stationMagnitude', publicID='m'), ns, 'amplitudeID', 'a')
                amplitude = node(root[0], ns, 'amplitude', publicID='a')
                node(amplitude, ns, 'pickID', base)
                result = p.project(body(root), 'invented', 'scml')
                self.assertEqual(result['status'], 'ok')
                self.assertEqual(result['arrivals'][0]['native_raw_reference_matches'], 1)
                self.assertEqual(result['denominators']['accepted_P_picks'], 0)
                self.assertEqual(result['denominators']['unique_resolved_qualifying_P_reference_ids'], 0)
                self.assertTrue(result['incomplete_associated_P_structure'])
                self.assertFalse(result['NZ_coverage_known'])
                self.assertIsNone(result['nz']['t0_us'])

    def test_qml_preserved_trimmed_reference_predicate_unchanged(self):
        root = fixture(); modify(root, 'pickID', ' ' + M + 'p ', False)
        result = p.project(body(root), 'invented', 'qml')
        self.assertEqual(result['denominators']['accepted_P_picks'], 1)

    def test_unique_object_gain_does_not_require_right_arrival_acceptance(self):
        base = 'smi:invented/p'; ns = p.SCML['0.11']
        left_root = fixture(False, picks=False); modify(left_root, 'pickID', base, False)
        right_root = fixture(True); right_root.find('.//{' + ns + '}pick').set('publicID', base)
        modify(right_root, 'pickID', base + ' ', True)
        origin = right_root.find('.//{' + ns + '}origin')
        node(node(origin, ns, 'stationMagnitude', publicID='m'), ns, 'amplitudeID', 'a')
        amplitude = node(right_root[0], ns, 'amplitude', publicID='a'); node(amplitude, ns, 'pickID', base)
        left = p.project(body(left_root), 'invented', 'qml')
        right = p.project(body(right_root), 'invented', 'scml')
        self.assertEqual(right['arrivals'][0]['native_raw_reference_matches'], 0)
        self.assertEqual(right['accepted_picks'], [])
        result = c.compare(left, right)
        self.assertIs(result['same_record_content'], True)
        self.assertEqual(result['newly_unique_reference_object_count'], 1)
        self.assertEqual(result['newly_resolved_reference_count'], 0)
        self.assertEqual(result['newly_accepted_NZ_reference_count'], 0)
        self.assertEqual(result['content_matched_resolution_candidate_count'], 0)
        self.assertEqual(result['paired_recorded_revision_resolution_count'], 0)

    def test_duplicate_picks_unresolved(self):
        root = fixture(); ev = root.find('.//{' + p.B + '}event')
        ev.append(copy.deepcopy(ev.find('{' + p.B + '}pick')))
        r = p.project(body(root), 'invented', 'qml')
        self.assertEqual(r['status'], 'ok'); self.assertEqual(r['denominators']['accepted_P_picks'], 0)
        self.assertFalse(r['NZ_coverage_known'])

    def test_cross_type_public_id_unknown(self):
        for native in (True, False):
            root = fixture(native); ns = p.SCML['0.11'] if native else p.B
            root.find('.//{' + ns + '}pick').set('publicID', 'o' if native else M + 'o')
            root.find('.//{' + ns + '}pickID').text = 'o' if native else M + 'o'
            self.assertEqual(p.project(body(root), 'invented', 'scml' if native else 'qml')['reason'], 'wrong_typed_publicID_collision')

    def test_qml_arrival_cross_type_publicID_unknown(self):
        root = fixture(); root.find('.//{' + p.B + '}arrival').set('publicID', M + 'p')
        self.assertEqual(p.project(body(root), 'invented', 'qml')['reason'], 'wrong_typed_publicID_collision')

    def test_qml_parameter_wrapper_cross_type_publicID_unknown(self):
        root = fixture(); root[0].set('publicID', M + 'invented')
        self.assertEqual(p.project(body(root), 'invented', 'qml')['reason'], 'wrong_typed_publicID_collision')

    def test_noncolliding_qml_arrival_publicID_retained(self):
        root = fixture(); root.find('.//{' + p.B + '}arrival').set('publicID', M + 'arrival_p_o')
        r = p.project(body(root), 'invented', 'qml')
        self.assertEqual(r['status'], 'ok')
        self.assertEqual(r['arrivals'][0]['raw_public_id'], M + 'arrival_p_o')

    def test_outside_qml_same_type_duplicate_pick_is_unknown(self):
        root = fixture(); root[0].append(copy.deepcopy(root.find('.//{' + p.B + '}pick')))
        self.assertEqual(p.project(body(root), 'invented', 'qml')['reason'], 'outside_scope_duplicate_publicID')

    def test_outside_native_nested_same_type_pick_is_unknown(self):
        root = fixture(True); ns = p.SCML['0.11']
        root.find('.//{' + ns + '}origin').append(copy.deepcopy(root.find('.//{' + ns + '}pick')))
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'outside_scope_duplicate_publicID')

    def test_raw_pick_timestamp_padding_is_preserved(self):
        for native in (True, False):
            value = '  ' + T + ' \n'
            r = project(native, pick_time=value)
            self.assertEqual(r['accepted_picks'][0]['raw_time'], value)
            self.assertEqual(r['accepted_picks'][0]['time'], '2020-01-01T00:00:00+00:00')

    def test_qml_raw_preferred_origin_padding_is_preserved(self):
        root = fixture(); modify(root, 'preferredOriginID', '  ' + M + 'o \n')
        r = p.project(body(root), 'invented', 'qml')
        self.assertEqual(r['raw_preferred_origin_id'], '  ' + M + 'o \n')
        self.assertEqual(r['preferred_origin_id'], M + 'o')

    def test_placeholder_reference_unresolved(self):
        for native in (True, False):
            for value in ('', 'NA', M + 'NA'):
                root = fixture(native, picks=False)
                modify(root, 'pickID', value, native)
                r = p.project(body(root), 'invented', 'scml' if native else 'qml')
                self.assertEqual(r['status'], 'ok'); self.assertFalse(r['NZ_coverage_known'])

    def test_placeholder_pick_object_unknown(self):
        root = fixture(); root.find('.//{' + p.B + '}pick').set('publicID', M + 'NA')
        self.assertEqual(p.project(body(root), 'invented', 'qml')['reason'], 'missing_or_placeholder_identity')

    def test_native_outside_scope_not_selected(self):
        root = fixture(True); ns = p.SCML['0.11']
        other = copy.deepcopy(root.find('.//{' + ns + '}pick')); other.set('publicID', 'outside')
        root[0].append(other)
        r = p.project(body(root), 'invented', 'scml')
        self.assertEqual(r['scope']['outside_scope_pick_records'], 1)
        self.assertEqual(len(r['picks']), 1)

    def test_unreferenced_origin_cannot_collide_with_selected_pick(self):
        root = fixture(True); ns = p.SCML['0.11']; node(root[0], ns, 'origin', publicID='p')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'wrong_typed_publicID_collision')

    def test_unselected_amplitude_cannot_collide_with_selected_pick(self):
        root = fixture(True); ns = p.SCML['0.11']; node(root[0], ns, 'amplitude', publicID='p')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'wrong_typed_publicID_collision')

    def test_unreferenced_origin_mapping_collision_unknown(self):
        root = fixture(True); ns = p.SCML['0.11']
        root.find('.//{' + ns + '}origin').set('publicID', 'o:a')
        modify(root, 'preferredOriginID', 'o:a', True); modify(root, 'originReference', 'o:a', True)
        node(root[0], ns, 'origin', publicID='o a')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'ID_mapping_collision')

    def test_unrelated_outside_bad_identity_does_not_broaden_scope(self):
        root = fixture(True); ns = p.SCML['0.11']; node(root[0], ns, 'origin', publicID='NA')
        r = p.project(body(root), 'invented', 'scml')
        self.assertEqual(r['status'], 'ok'); self.assertEqual(r['scope']['outside_scope_origin_records'], 1)

    def test_amplitude_only_no_value_selects_pick(self):
        root = fixture(True); ns = p.SCML['0.11']
        origin = root.find('.//{' + ns + '}origin')
        sm = node(origin, ns, 'stationMagnitude', publicID='m'); node(sm, ns, 'amplitudeID', 'a')
        amp = node(root[0], ns, 'amplitude', publicID='a'); node(amp, ns, 'pickID', 'extra')
        extra = copy.deepcopy(root.find('.//{' + ns + '}pick')); extra.set('publicID', 'extra'); root[0].append(extra)
        r = p.project(body(root), 'invented', 'scml')
        self.assertEqual(r['scope']['selected_amplitude_without_value_count'], 1)
        self.assertEqual(r['scope']['candidate_emitted_amplitude_records'], 0)
        self.assertEqual(r['picks'][M + 'extra'][0]['selection_paths'], ['amplitude'])
        self.assertEqual(r['magnitude_metadata'][0]['candidate_origin_id'], M + 'o')

    def test_repeated_amplitude_reference_emission_count(self):
        root = fixture(True); ns = p.SCML['0.11']; origin = root.find('.//{' + ns + '}origin')
        for name in ('m1','m2'):
            node(node(origin, ns, 'stationMagnitude', publicID=name), ns, 'amplitudeID', 'a')
        amp = node(root[0], ns, 'amplitude', publicID='a'); node(amp, ns, 'pickID', 'p'); node(node(amp, ns, 'amplitude'), ns, 'value', '2')
        r = p.project(body(root), 'invented', 'scml')
        self.assertEqual(r['scope']['candidate_emitted_amplitude_records'], 2)
        self.assertEqual(r['scope']['selected_pick_records'], 1)
        self.assertEqual(r['picks'][M + 'p'][0]['selection_paths'], ['arrival', 'amplitude'])

    def test_duplicate_amplitude_unknown(self):
        root = fixture(True); ns = p.SCML['0.11']; origin = root.find('.//{' + ns + '}origin')
        node(node(origin, ns, 'stationMagnitude', publicID='m'), ns, 'amplitudeID', 'a')
        node(root[0], ns, 'amplitude', publicID='a'); node(root[0], ns, 'amplitude', publicID='a')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'ambiguous_amplitude_reference')

    def test_duplicate_qml_amplitude_unknown(self):
        root = fixture(); ev = root.find('.//{' + p.B + '}event')
        node(ev, p.B, 'amplitude', publicID=M+'a'); node(ev, p.B, 'amplitude', publicID=M+'a')
        self.assertEqual(p.project(body(root), 'invented', 'qml')['reason'], 'ambiguous_amplitude_reference')

    def test_id_translation_collision(self):
        root = fixture(True); ns = p.SCML['0.11']; origin = root.find('.//{' + ns + '}origin')
        root.find('.//{' + ns + '}pick').set('publicID', 'x y'); modify(root, 'pickID', 'x y', True)
        extra = copy.deepcopy(root.find('.//{' + ns + '}pick')); extra.set('publicID', 'x:y'); root[0].append(extra)
        arr = node(origin, ns, 'arrival'); node(arr, ns, 'pickID', 'x:y'); node(arr, ns, 'phase', 'P')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'ID_mapping_collision')

    def test_id_prefixes_preserved(self):
        self.assertEqual(p.mapped_id('smi:invented/x'), 'smi:invented/x')
        self.assertEqual(p.mapped_id('quakeml:invented/x'), 'quakeml:invented/x')
        self.assertEqual(p.mapped_id('a:b c'), M + 'a_b_c')

    def test_missing_station_and_naive_time_not_accepted(self):
        self.assertEqual(project(station='')['reasons']['missing_station_identity'], 1)
        self.assertEqual(project(pick_time='2020-01-01T00:00:00')['reasons']['invalid_or_naive_pick_time'], 1)

    def test_xml_malformed_encoding_and_entities(self):
        for data in (b'<bad', b'\xff', b'<!DOCTYPE x><x/>', b'<!ENTITY x "a"><x/>', b'<x>\x00</x>'):
            self.assertEqual(p.project(data, 'invented', 'qml')['status'], 'unknown_representation')

    def test_body_and_structure_bounds(self):
        self.assertEqual(p.project(b' ' * (4*p.MIB+1), 'invented', 'qml')['reason'], 'body_bound')
        self.assertEqual(p.project(b'<x>'*65+b'</x>'*65, 'invented', 'qml')['reason'], 'XML_structure_bound')
        self.assertEqual(p.project(b'<x>'+b'<n/>'*100000+b'</x>', 'invented', 'qml')['reason'], 'XML_structure_bound')

    def test_invalid_numeric_origin_unknown_content(self):
        root = fixture()
        root.find('.//{' + p.B + '}depth/{' + p.B + '}value').text = '1e-9999999'
        r = p.project(body(root), 'invented', 'qml')
        self.assertIsNone(r['origin']['depth_m'])
        self.assertIsNone(c.compare(r, r)['same_record_content'])

    def test_raw_native_creation_uri_mapping_separate(self):
        root = fixture(True); ns = p.SCML['0.11']; ci = root.find('.//{' + ns + '}event/{' + ns + '}creationInfo')
        node(ci, ns, 'agencyURI', 'plain:id')
        r = p.project(body(root), 'invented', 'scml')
        self.assertEqual(r['event_creation']['agencyURI'], M + 'plain_id')
        self.assertEqual(r['raw_event_creation']['{' + ns + '}agencyURI'], 'plain:id')

    def test_duplicate_arrival_is_one_accepted_reference(self):
        root = fixture(); origin = root.find('.//{' + p.B + '}origin')
        origin.append(copy.deepcopy(origin.find('{' + p.B + '}arrival')))
        r = p.project(body(root), 'invented', 'qml')
        self.assertEqual(r['denominators']['qualifying_P_references'], 2)
        self.assertEqual(r['denominators']['accepted_P_picks'], 1)

    def test_other_phase_is_known_zero_not_missing_P(self):
        root = fixture(picks=False); modify(root, 'phase', 'S')
        r = p.project(body(root), 'invented', 'qml')
        self.assertEqual(r['denominators']['qualifying_P_references'], 0)
        self.assertTrue(r['NZ_coverage_known'])

    def test_valid_P_phase_family(self):
        for phase in ('P', 'Pg', 'Pn', 'Pb'):
            root = fixture(); modify(root, 'phase', phase)
            self.assertEqual(p.project(body(root), 'invented', 'qml')['denominators']['accepted_P_picks'], 1)

    def test_source_optional_empty_ID_candidate_is_placeholder(self):
        self.assertEqual(p.source_id_candidate(''), M + 'NA')
        self.assertEqual(p.source_id_candidate(None), M + 'NA')
        for value in ('', 'NA', M + 'NA'):
            with self.assertRaises(p.RepresentationError): p.mapped_id(value)

    def test_duplicate_native_use_flag_unknown(self):
        root = fixture(True, flags={'timeUsed':'true'}); ns = p.SCML['0.11']
        node(root.find('.//{' + ns + '}arrival'), ns, 'timeUsed', 'false')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'duplicate_singleton:timeUsed')

    def test_non_scalar_reference_unknown(self):
        root = fixture(True); ns = p.SCML['0.11']
        node(root.find('.//{' + ns + '}originReference'), ns, 'value', 'o')
        self.assertEqual(p.project(body(root), 'invented', 'scml')['reason'], 'non_scalar:originReference')


class ComparisonTests(unittest.TestCase):
    def test_distinct_new_object_and_acceptance_counts(self):
        left = project(picks=False); right = project()
        r = c.compare(left, right)
        self.assertEqual(r['newly_unique_reference_object_count'], 1)
        self.assertEqual(r['newly_resolved_reference_count'], 1)
        self.assertEqual(r['newly_accepted_NZ_reference_count'], 1)
        self.assertEqual(r['paired_recorded_revision_resolution_count'], 1)

    def test_existing_unique_time_repair(self):
        left = project(pick_time=None); right = project()
        r = c.compare(left, right)
        self.assertEqual(r['newly_unique_reference_object_count'], 0)
        self.assertEqual(r['newly_resolved_reference_count'], 1)

    def test_existing_unique_station_repair(self):
        r = c.compare(project(station=''), project())
        self.assertEqual(r['newly_unique_reference_object_count'], 0)
        self.assertEqual(r['newly_accepted_NZ_reference_count'], 1)

    def test_non_NZ_recovery_is_separate(self):
        r = c.compare(project(picks=False), project(network='XX'))
        self.assertEqual(r['newly_resolved_reference_count'], 1)
        self.assertEqual(r['newly_accepted_NZ_reference_count'], 0)

    def test_already_accepted_XX_to_NZ_is_not_newly_resolved_recovery(self):
        r = c.compare(project(network='XX'), project(network='NZ'))
        self.assertEqual(r['newly_resolved_reference_count'], 0)
        self.assertEqual(r['newly_accepted_NZ_reference_count'], 0)

    def test_rejected_right_is_not_accepted_recovery(self):
        r = c.compare(project(picks=False), project(status='rejected'))
        self.assertEqual(r['newly_unique_reference_object_count'], 1)
        self.assertEqual(r['newly_resolved_reference_count'], 0)

    def test_missing_revision_unknown(self):
        r = c.compare(project(picks=False, creation=None), project(creation=None))
        self.assertEqual(r['revision_evidence'], 'missing_or_incomplete')
        self.assertEqual(r['paired_recorded_revision_resolution_count'], 0)

    def test_conflicting_revision_blocks_candidate(self):
        r = c.compare(project(picks=False), project(creation='2020-01-02T00:00:00Z'))
        self.assertEqual(r['revision_evidence'], 'conflict')
        self.assertEqual(r['content_matched_resolution_candidate_count'], 0)

    def test_invalid_present_revision_blocks_match(self):
        left = project(profile='0.11', modification='bad', picks=False)
        right = project(profile='0.11', modification='bad')
        r = c.compare(left, right)
        self.assertFalse(r['all_present_recorded_times_valid'])
        self.assertEqual(r['revision_evidence'], 'missing_or_incomplete')

    def test_lexical_primary_canonical_diagnostic(self):
        r = c.compare(project(weight='1'), project(weight='1.0'))
        self.assertFalse(r['arrival_multiset_match'])
        self.assertTrue(r['canonical_arrival_multiset_diagnostic_match'])
        self.assertFalse(r['same_record_content'])

    def test_preserved_clock_does_not_follow_new_earliest(self):
        r = project(); future = project(pick_time='2020-01-01T00:00:04Z')
        result = c.event_result(r, future, future, p.stamp_us(T))
        clock = result['shadow_clocks']['fresh_qml']
        self.assertEqual(clock['own_clock']['strict_horizon_station_counts']['1'], 1)
        self.assertEqual(clock['at_preserved_original_T0']['strict_horizon_station_counts']['3'], 0)
        self.assertEqual(clock['at_preserved_original_T0']['strict_horizon_station_counts']['5'], 1)

    def test_null_preserved_clock_never_falls_back(self):
        r = project(); result = c.event_result(r, r, r, None)
        self.assertIsNone(result['preserved_original_T0_us'])
        self.assertIsNone(result['shadow_clocks']['fresh_qml']['at_preserved_original_T0'])

    def test_strict_deadline_station_dedup(self):
        picks = [dict(project()['accepted_picks'][0]) for _ in range(3)]
        picks[1]['time'] = '2020-01-01T00:00:01Z'; picks[1]['station'] = 'B'
        picks[2]['time'] = '2020-01-01T00:00:03Z'; picks[2]['station'] = 'C'
        r = p.clock(picks, p.stamp_us(T))
        self.assertEqual(r['strict_horizon_station_counts'], {'1':1,'3':2,'5':3})
        self.assertEqual(p.clock([picks[0],picks[0]])['station_count'], 1)

    def test_network_station_tuple_is_injective_for_nonempty_codes(self):
        first = dict(project()['accepted_picks'][0], network='NZ.A', station='B')
        second = dict(first, network='NZ', station='A.B')
        r = p.clock([first, second])
        self.assertEqual(r['station_count'], 2)
        self.assertEqual(r['strict_horizon_station_counts'], {'1':2,'3':2,'5':2})

    def test_unknown_representation_keeps_null_denominators(self):
        unknown = p.project(b'bad', 'invented', 'qml')
        self.assertIsNone(unknown['denominators']); self.assertIsNone(c.compare(unknown, project())['newly_resolved_reference_count'])


class CohortTests(unittest.TestCase):
    def inputs(self):
        provenance = {key: 'a'*64 for key in s.PROVENANCE_KEYS}; provenance['pushed_freeze'] = 'a'*40
        events = []
        for i in range(6):
            event = {'event_id':'invented'+str(i),'original_t0_us':p.stamp_us(T),'native_profile':'0.11'}
            for member in s.MEMBERS:
                event[member] = body(fixture(member == 'native_scml', event=event['event_id']))
            event['body_pins'] = {key:{'bytes':len(event[key]),'sha256':hashlib.sha256(event[key]).hexdigest()} for key in s.MEMBERS}
            events.append(event)
        return events, provenance

    def test_cohort_exact18_and_no_mutation(self):
        events, provenance = self.inputs(); before = copy.deepcopy(events)
        output = s.run_shadow(events, provenance)
        self.assertEqual(output['aggregate']['representation_denominator'], 18)
        self.assertEqual(output['aggregate']['source_event_denominator'], 6)
        self.assertEqual(events, before)
        self.assertEqual(output['network_requests'], 0)

    def test_denominator_not_replaced(self):
        events, provenance = self.inputs()
        with self.assertRaisesRegex(ValueError, 'fixed_six'): s.run_shadow(events[:-1], provenance)

    def test_duplicate_event_not_replaced(self):
        events, provenance = self.inputs(); events[1]['event_id'] = events[0]['event_id']
        with self.assertRaisesRegex(ValueError, 'duplicate_event'): s.run_shadow(events, provenance)

    def test_distinct_raw_cohort_event_mapping_collision_rejected(self):
        events, provenance = self.inputs(); events[0]['event_id'] = 'invented a'; events[1]['event_id'] = 'invented:a'
        with self.assertRaisesRegex(ValueError, 'event_ID_mapping_collision'): s.run_shadow(events, provenance)

    def test_bad_body_pin_rejected_before_project(self):
        events, provenance = self.inputs(); events[0]['body_pins']['fresh_qml']['sha256'] = 'b'*64
        with self.assertRaisesRegex(ValueError, 'body_pin_mismatch'): s.run_shadow(events, provenance)

    def test_source_provenance_required(self):
        events, provenance = self.inputs(); del provenance['runtime_sha256']
        with self.assertRaisesRegex(ValueError, 'provenance_schema'): s.run_shadow(events, provenance)

    def test_T0_bool_not_integer(self):
        events, provenance = self.inputs(); events[0]['original_t0_us'] = True
        with self.assertRaisesRegex(ValueError, 'original_T0_type'): s.run_shadow(events, provenance)

    def test_T0_range(self):
        events, provenance = self.inputs(); events[0]['original_t0_us'] = 10**30
        with self.assertRaisesRegex(ValueError, 'original_T0_range'): s.run_shadow(events, provenance)

    def test_profile_required(self):
        events, provenance = self.inputs(); events[0]['native_profile'] = None
        with self.assertRaisesRegex(ValueError, 'explicit_native_profile'): s.run_shadow(events, provenance)

    def test_unknown_native_preserves_all_slots(self):
        events, provenance = self.inputs(); events[0]['native_scml'] = b'bad'
        events[0]['body_pins']['native_scml'] = {'bytes':3,'sha256':hashlib.sha256(b'bad').hexdigest()}
        r = s.run_shadow(events, provenance)
        self.assertEqual(r['aggregate']['representation_denominator'], 18)
        self.assertEqual(r['events'][0]['representations']['native_scml']['status'], 'unknown_representation')
        self.assertEqual(r['events'][0]['representations']['fresh_qml']['status'], 'ok')
        self.assertFalse(r['events'][0]['native_profile_binding']['bound'])

    def test_unsupported_native_never_lends_extension_profile(self):
        events, provenance = self.inputs()
        event = events[0]; event['native_scml'] = b'bad'
        event['fresh_qml'] = body(fixture(event=event['event_id'], modification=T))
        for member in ('native_scml','fresh_qml'):
            event['body_pins'][member] = {'bytes':len(event[member]),'sha256':hashlib.sha256(event[member]).hexdigest()}
        r = s.run_shadow(events, provenance)
        self.assertEqual(r['events'][0]['representations']['fresh_qml']['reason'], 'version_extension_requires_bound_profile')

    def test_bad_size_pin_and_oversized_body(self):
        events, provenance = self.inputs(); events[0]['body_pins']['fresh_qml']['bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'body_pin_mismatch'): s.run_shadow(events, provenance)
        events, provenance = self.inputs(); events[0]['fresh_qml'] = b' ' * (4*p.MIB+1)
        with self.assertRaisesRegex(ValueError, 'body_bound'): s.run_shadow(events, provenance)

    def test_null_original_clock_retained(self):
        events, provenance = self.inputs(); events[0]['original_t0_us'] = None
        r = s.run_shadow(events, provenance)
        self.assertIsNone(r['events'][0]['shadow_clocks']['original_qml']['at_preserved_original_T0'])

    def test_large_invented_output_fails_without_input_mutation(self):
        events, provenance = self.inputs(); event = events[0]
        for member in s.MEMBERS:
            native = member == 'native_scml'; ns = p.SCML['0.11'] if native else p.B
            root = fixture(native, event=event['event_id'])
            for ci in root.findall('.//{' + ns + '}creationInfo'):
                node(ci, ns, 'author', 'a' * p.MIB)
            event[member] = body(root)
            event['body_pins'][member] = {'bytes':len(event[member]),'sha256':hashlib.sha256(event[member]).hexdigest()}
        before = copy.deepcopy(events)
        with self.assertRaisesRegex(ValueError, 'output_bound'): s.run_shadow(events, provenance)
        self.assertEqual(events, before)


if __name__ == '__main__':
    unittest.main()
