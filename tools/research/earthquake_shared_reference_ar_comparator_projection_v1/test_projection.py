"""Invented fixtures only; selected frozen functions execute without producer imports."""
import ast
import copy
import math
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'public_contracts'))
import math_core as core
import packet as pkt
import transport as tx
import packet_digest as pd
import metrics
from projection import make_projector, pin, need, REUSED, STRONG


def functions(file, names, namespace):
    tree = ast.parse((ROOT / 'public_contracts' / file).read_text())
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(selected) == len(names)
    exec(compile(ast.Module(body=selected, type_ignores=[]), file, 'exec'), namespace)
    return types.SimpleNamespace(**namespace)


old = functions('auditor.py', {'close', 'hashstr'}, {'core': core, 'np': core.np, 'math': math})
old.IDS = REUSED
audit = functions('l_auditor.py', {'record_set', 'comparators_checked'},
                  {'core': core, 'pkt': pkt, 'tx': tx, 'old': old, 'metrics': metrics, 'math': math})
producer = functions('l_processor.py', {'validate_forecast', 'validate_population'},
                     {'need': need, 'math': math, 'ARMS': ('L',), 'HORIZONS': (1, 3, 5)})


def fixture():
    rows = []
    for i in range(87):
        ctx = core.np.zeros(34, dtype='<f8'); ctx[14] = 1.
        rows.append(dict(ordinal=i, common=True, partition='TRAIN' if i < 65 else 'DEV',
                         mw=5.0 if i % 2 else 6.0, group=i % 4, precontext=ctx,
                         noise={'rate': [100, 1]}))
    packet = {'rows': rows}
    current = pd.sha(packet)
    admission = 'a' * 64
    sources = {k: {'bytes': 1, 'sha256': str(j) * 64} for j, k in enumerate(
        ('operator', 'native_validator', 'reference', 'processor', 'protocol'), 1)}
    six, strong, fits, stronger, origins, joins = [], [], [], [], [], []
    for j, (seed, arm) in enumerate(REUSED + STRONG):
        predictions = []
        for row in rows[65:]:
            for h in (1, 3, 5):
                # Includes a signed zero to detect numerical coercion.
                p = dict(ordinal=row['ordinal'], horizon=h, target=row['mw'], group=row['group'],
                         mean=-0.0, median=5., nll=1.2345678901234567, crps=1., pit=.5,
                         coverage_50=True, coverage_80=True, coverage_95=True)
                if arm not in ('B', 'F'):
                    p['quantiles'] = dict(zip(('0.025', '0.1', '0.25', '0.5', '0.75', '0.9', '0.975'),
                                              (1., 2., 3., 5., 7., 8., 9.)))
                if j < 6:
                    p.update(seed=seed, arm=arm, status='complete', source={'invented': True})
                predictions.append(p)
        records = []
        for p in predictions:
            row = rows[p['ordinal']]
            records.append(dict(p, family='ENZ', receiver=row['precontext'][8:11].tolist(), rate=[100, 1]))
        item = dict(seed=seed, arm=arm, records=records,
                    metrics={str(h): metrics.panel([p for p in records if p['horizon'] == h]) for h in (1, 3, 5)})
        (fits if j < 6 else stronger).append(item)
        historical_packet = current if j < 6 else 'e' * 64
        historical = dict(verified=True, no_optimizer=True, checkpoint_sha256='c' * 64,
                          source_sha256='d' * 64, packet_sha256=historical_packet,
                          independent_audit_sha256='f' * 64)
        comparison = dict(historical, packet_sha256=current)
        origin = dict(seed=seed, arm=arm, **{k: v for k, v in historical.items() if k not in ('verified', 'no_optimizer')},
                      origin_sha256='b' * 64, records_sha256=tx.sha(records),
                      original_packet_pins={'archive': 'invented-storage-pair-archive', 'manifest': 'invented-storage-pair-manifest'},
                      original_result_pin={'bytes': 1, 'sha256': '9' * 64})
        origins.append(origin)
        joins.append(dict(seed=seed, arm=arm, historical_closure=historical,
                          comparison_closure=comparison, comparison_packet_sha256=current,
                          records_sha256=origin['records_sha256'],
                          semantics='same-cohort-only; historical-fit-packet-retained'))
        if j < 6:
            six.append(dict(status='complete', study='earthquake-TRAIN115-marked-noise-fitting-v2',
                            seed=seed, arm=arm, predictions=predictions, no_optimizer=True,
                            packet_sha256=historical_packet, checkpoint_sha256='c' * 64,
                            source_pins=copy.deepcopy(sources), admission_sha256=admission, metrics=item['metrics']))
        else:
            strong.append(dict(seed=seed, arm=arm, predictions=predictions, closure=comparison))
    report = dict(schema='marked-sixfit-independent-aggregate-v1', status='pass', checked=396,
                  fits=fits, stronger=stronger, paired={'invented': []},
                  advance=metrics.guards(fits, stronger), authority_sha256='8' * 64)
    inputs = dict(reused_scores=[pin(tx.canonical(v)) for v in six], stronger_envelope=pin(tx.canonical(strong)),
                  closed_comparator_report=pin(tx.canonical(report)), comparator_origins=pin(tx.canonical(origins)))
    scope = dict(schema='L-bridge-input-scope-v1', historical_pins={k: inputs[k] for k in ('reused_scores', 'stronger_envelope')},
                 input_pins={k: inputs[k] for k in ('closed_comparator_report', 'comparator_origins')},
                 source_pins={'invented_new_sources': '7' * 64}, original_source_pins=sources)
    scope['input_pins']['original_admission'] = {'bytes': 1, 'sha256': admission}
    receipt = dict(schema='root-L-bridge-input-authentication-v1', scope=scope, decision='authorized',
                   packet_sha256=current, original_execution_closure_sha256='7' * 64,
                   source_pins=scope['source_pins'], original_source_pins=sources,
                   proof_pin={'bytes': 1, 'sha256': '6' * 64})
    expected = dict(schema='root-held-L-comparator-projection-v1', scope=scope, receipt=receipt, inputs=inputs, joins=joins)
    return expected, [scope, packet, six, strong, report, origins, receipt]


def build(expected, args, **overrides):
    authority = {'closed_comparator_report_sha256': tx.sha(args[4]), 'origins_sha256': tx.sha(args[5])}
    deps = dict(expected_pin=pin(tx.canonical(expected)), canonical=tx.canonical,
                packet_digest=pd.sha, validate_population=producer.validate_population,
                check_closed=lambda report, origins, packet: audit.comparators_checked(
                    report, origins, packet, {'dev': list(range(65, 87))}, authority))
    deps.update(overrides)
    return make_projector(expected, **deps)


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.expected, self.args = fixture()

    def reject(self, mutate, repin=False):
        mutate(self.expected, self.args)
        if repin:
            # Simulate an authenticated but structurally bad contract too.
            e, a = self.expected, self.args
            e['inputs'].update(reused_scores=[pin(tx.canonical(v)) for v in a[2]],
                stronger_envelope=pin(tx.canonical(a[3])), closed_comparator_report=pin(tx.canonical(a[4])),
                comparator_origins=pin(tx.canonical(a[5])))
            a[0]['historical_pins'] = {k: e['inputs'][k] for k in ('reused_scores', 'stronger_envelope')}
            a[0]['input_pins'].update({k: e['inputs'][k] for k in ('closed_comparator_report', 'comparator_origins')})
        with self.assertRaises((ValueError, KeyError, TypeError)):
            build(self.expected, self.args)(*self.args)

    def test_preserves_numerics_provenance_and_inputs(self):
        before = tx.canonical(self.args)
        result = build(self.expected, self.args)(*self.args)
        self.assertEqual(tx.canonical(self.args), before)
        self.assertEqual(tx.canonical(result['origins']), tx.canonical(self.args[5]))
        for i, value in enumerate(result['reused_results'] + result['strong_results']):
            original = (self.args[2] + self.args[3])[i]
            for p, q in zip(value['predictions'], original['predictions']):
                for key in ('mean', 'median', 'nll', 'crps', 'pit'):
                    self.assertIs(type(p[key]), float)
                    self.assertEqual(p[key].hex(), q[key].hex())
            self.assertEqual(value['historical_closure']['packet_sha256'], self.args[5][i]['packet_sha256'])
            self.assertEqual(value['origin'], self.args[5][i])
        self.assertNotEqual(result['strong_results'][0]['historical_closure']['packet_sha256'],
                            result['strong_results'][0]['packet_sha256'])

    def test_frozen_bridge_acceptance(self):
        projection = build(self.expected, self.args)(*self.args)
        # Execute the exact frozen bridge acceptance statements, not a retyped facsimile.
        tree = ast.parse((ROOT / 'public_contracts/bridge.py').read_text())
        bind = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'bind')
        statements = [n for n in bind.body if 101 <= n.lineno <= 102]
        self.assertEqual(len(statements), 2)
        io = types.SimpleNamespace(need=need, pin=pin)
        env = dict(io=io, historical=types.SimpleNamespace(encode=tx.canonical), projection=projection,
                   self=types.SimpleNamespace(g={'input_pins': self.args[0]['input_pins']}),
                   packet_sha=pd.sha(self.args[1]), REUSED=REUSED, STRONG=STRONG)
        exec(compile(ast.Module(body=statements, type_ignores=[]), 'frozen_bridge_acceptance', 'exec'), env)

    def test_missing_or_wrong_contract(self):
        for e in (None, {}, dict(self.expected, schema='wrong')):
            with self.assertRaises((ValueError, TypeError)):
                make_projector(e, expected_pin=pin(tx.canonical(self.expected)), canonical=tx.canonical,
                    packet_digest=pd.sha, validate_population=producer.validate_population, check_closed=lambda *a: None)

    def test_wrong_raw_pin(self):
        self.reject(lambda e, a: a[0]['historical_pins']['reused_scores'][0].update(sha256='0'*64))

    def test_decoded_tamper_before_projection(self):
        calls = []
        mapper = build(self.expected, self.args, check_closed=lambda *a: calls.append(True))
        self.args[2][0]['predictions'][0]['nll'] += 1.
        with self.assertRaisesRegex(ValueError, 'canonical_input_binding'):
            mapper(*self.args)
        self.assertEqual(calls, [])

    def test_duplicate_and_reordered_arms(self):
        for index, operation in ((2, 'duplicate'), (2, 'reverse'), (3, 'duplicate'), (3, 'reverse')):
            with self.subTest(index=index, operation=operation):
                self.setUp()
                self.reject(lambda e, a: a[index].__setitem__(slice(None),
                    [a[index][0]] * len(a[index]) if operation == 'duplicate' else a[index][::-1]), True)

    def test_bad_source_admission_checkpoint(self):
        for field, value in (('source_pins', {}), ('admission_sha256', '0'*64), ('checkpoint_sha256', '0'*64)):
            with self.subTest(field=field):
                self.setUp()
                self.reject(lambda e, a: a[2][0].update({field: value}), True)

    def test_bad_join_and_fabricated_flags(self):
        for key, value in (('comparison_packet_sha256', '0'*64), ('records_sha256', '0'*64), ('semantics', 'rerun')):
            with self.subTest(key=key):
                self.setUp()
                self.reject(lambda e, a: e['joins'][6].update({key: value}))
        self.setUp()
        self.reject(lambda e, a: e['joins'][0]['comparison_closure'].update(verified=False))

    def test_report_and_forecast_event_join(self):
        mutations = [lambda e, a: a[4]['fits'][0]['records'].reverse(),
                     lambda e, a: a[4]['fits'][0]['records'].pop(),
                     lambda e, a: a[2][0]['predictions'].reverse(),
                     lambda e, a: a[3][0]['predictions'][0].update(target=4.),
                     lambda e, a: a[3][0]['predictions'][0].update(mean=0),
                     lambda e, a: a[3][0]['predictions'][0].update(seed=True),
                     lambda e, a: a[5][0].update(packet_sha256='0'*64)]
        for n, mutation in enumerate(mutations):
            with self.subTest(mutation=n):
                self.setUp(); self.reject(mutation, True)

    def test_receipt_native_and_origin_fail_closed(self):
        self.reject(lambda e, a: a[6].update(decision='denied'))
        self.setUp(); self.reject(lambda e, a: a[1]['rows'][0].update(mw=7.))
        self.setUp(); self.reject(lambda e, a: a[5].reverse(), True)

    def test_contract_snapshot_is_held(self):
        mapper = build(self.expected, self.args)
        self.expected['joins'][0]['comparison_closure']['verified'] = False
        self.assertEqual(len(mapper(*self.args)['reused_results']), 6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
