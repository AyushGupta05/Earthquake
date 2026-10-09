import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

import audit_scores as a
import replay_gpu_grid as gpu


class CompleteArtifactTests(unittest.TestCase):
    def setUp(self):
        import torch
        from replay_checkpoint_sample import SavedHead
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        source = self.root / 'research/2026-10-09/phase2'
        source.mkdir(parents=True)
        (source / 'fixture.py').write_text('# Source identity fixture; never imported.\n')
        config = {'controls': list(a.CONTROLS), 'seeds': list(a.SEEDS), 'epochs': 15,
                  'seconds': 1, 'expected_train_records': 20, 'max_per_event': 0,
                  'runtime': {'torch': str(torch.__version__)}}
        identity = {'config': config, 'source_sha256': {'fixture.py': a.sha256(source / 'fixture.py')}}
        canonical = json.dumps(identity, sort_keys=True, allow_nan=False)
        digest = a.hashlib.sha256(canonical.encode()).hexdigest()[:12]
        self.run = self.root / f'instrument_scores_1s_{digest}_fixture'
        self.run.mkdir()
        self.write('identity.json', identity)
        centers = (np.arange(66) + .5) * .1
        targets = np.array([.1, 1.2, 4.3, 5.1])
        ids = np.array(['v0', 'v1', 'v2', 'v3'])
        names = np.array(['x0', 'x1', 'x2', 'x3'])
        self.ref = self.root / 'validation_1s.npz'
        np.savez(self.ref, targets=targets, event_ids=ids, trace_names=names, centers=centers)
        inputs = {'validation_reference_sha256': a.sha256(self.ref)}
        self.write('input_identities.json', inputs)
        train = {'targets': np.linspace(0, 6.5, 20, dtype=np.float32),
                 'event_ids': np.array([f't{i}' for i in range(20)]),
                 'trace_names': np.array([f'train{i}' for i in range(20)]),
                 'row_index': np.arange(20), 'weights': np.ones(20, dtype=np.float32)}
        np.savez(self.run / 'training_rows.npz', **train)
        label = np.floor(train['targets'].astype(float) / .1 + 1e-5).astype(int)
        mass = np.bincount(label, minlength=66)
        cdf = mass.cumsum()[:-1] / mass.sum()
        u = np.minimum(25, 1 / (.01 + cdf * (1 - cdf)))
        weight = (u / u.mean()).astype(np.float32)
        prior = dict(source_split='train', weighted_bin_mass=mass.tolist(), cdf=cdf.tolist(),
                     weights=weight.tolist(), input_identities=inputs)
        for key, name in {'targets': 'targets_sha256', 'weights': 'weights_sha256', 'row_index': 'row_index_sha256',
                          'event_ids': 'event_ids_sha256', 'trace_names': 'trace_names_sha256'}.items():
            prior[name] = a.array_digest(train[key])
        self.write('train_marginal_prior.json', prior)
        probabilities = [np.random.default_rng(seed).dirichlet(np.ones(66), size=4) for seed in a.SEEDS]
        prediction = dict(targets=targets, event_ids=ids, trace_names=names)
        reports, histories, traces = {}, {}, {}
        for decision, values in zip(('mean', 'median'), a.mean_and_median(probabilities[0], centers)):
            prediction['raw_' + decision] = values
            reports['raw_' + decision] = a.point_metrics(targets, values, ids)
            # Real reports contain only the runner's point metric subset.
        for control in a.CONTROLS:
            avg = np.mean(probabilities, axis=0)
            np.savez(self.run / f'{control}_probabilities.npz', targets=targets, event_ids=ids,
                trace_names=names, centers=centers, mean_probability=avg.astype(np.float32),
                **{f'seed{s}': p.astype(np.float32) for s, p in zip(a.SEEDS, probabilities)})
            for name, p in [(f'seed{s}', p) for s, p in zip(a.SEEDS, probabilities)] + [('ensemble', avg)]:
                for decision, values in zip(('mean', 'median'), a.mean_and_median(p, centers)):
                    key = f'{control}_{name}_{decision}'
                    prediction[key] = values
                    reports[key] = a.point_metrics(targets, values, ids)
                if name == 'ensemble':
                    continue
                seed = int(name[4:]); torch.manual_seed(seed)
                model = SavedHead()
                checkpoint = dict(model=model.state_dict(), feature_mean=torch.zeros(291),
                    feature_std=torch.ones(291), feature_mask=torch.tensor(np.r_[np.ones(279), np.zeros(12)], dtype=torch.float32),
                    training_prior_weights=torch.tensor(weight), config=config, seed=seed, control=control)
                torch.save(checkpoint, self.run / f'{control}_{name}.pth')
                rng = torch.Generator().manual_seed(seed)
                traces[f'{control}_{name}'] = dict(initial_model_sha256=a.model_digest(model.state_dict()),
                    final_model_sha256=a.model_digest(model.state_dict()),
                    parameters=sum(x.numel() for x in model.parameters()),
                    epoch_order_sha256=[a.array_digest(torch.randperm(20, generator=rng).numpy()) for _ in range(15)])
                histories[f'{control}_{name}'] = [1.] * 15
        np.savez(self.run / 'predictions.npz', **prediction)
        for name, value in [('metrics.json', reports), ('history.json', histories), ('training_traces.json', traces)]:
            self.write(name, value)
        self.refresh_manifest()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, value):
        (self.run / name).write_text(json.dumps(value, allow_nan=False))

    def refresh_manifest(self):
        self.write('artifacts.json', {p.name: {'bytes': p.stat().st_size, 'sha256': a.sha256(p)}
                   for p in self.run.iterdir() if p.name != 'artifacts.json'})

    def test_complete_grid_passes(self):
        report = a.audit_run(self.run, self.root, self.ref)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(len(report['metrics']), 32)
        self.assertTrue(report['seeded_epoch_orders_replayed'])

    def test_self_consistent_hashes_cannot_hide_reordered_trace_ids(self):
        path = self.run / 'huber_ce_probabilities.npz'
        data = a.load_npz(path)
        data['trace_names'] = data['trace_names'][::-1]
        np.savez(path, **data); self.refresh_manifest()
        with self.assertRaisesRegex(ValueError, 'alignment'):
            a.audit_run(self.run, self.root, self.ref)

    def test_self_consistent_hashes_cannot_hide_wrong_ensemble(self):
        path = self.run / 'huber_ce_probabilities.npz'
        data = a.load_npz(path)
        data['mean_probability'] = data['seed20261009']
        np.savez(path, **data); self.refresh_manifest()
        with self.assertRaisesRegex(ValueError, 'equal seed average'):
            a.audit_run(self.run, self.root, self.ref)

    def test_self_consistent_hashes_cannot_hide_changed_checkpoint(self):
        import torch
        path = self.run / 'huber_ce_seed20261009.pth'
        state = torch.load(path, map_location='cpu', weights_only=True)
        state['model']['net.0.bias'][0] += 1
        torch.save(state, path); self.refresh_manifest()
        with self.assertRaisesRegex(ValueError, 'Final model hash'):
            a.audit_run(self.run, self.root, self.ref)

    def test_replay_sample_bounds_and_stable_tail_inclusion(self):
        from replay_checkpoint_sample import sample_rows
        y = np.arange(100.)
        rows = sample_rows(y, 32)
        self.assertLessEqual(len(rows), 32)
        self.assertIn(99, rows)
        self.assertIn(0, rows)
        np.testing.assert_array_equal(rows, sample_rows(y, 32))
        with self.assertRaises(ValueError):
            sample_rows(y, 1000)


class MathematicalAuditTests(unittest.TestCase):
    def test_exact_crps_off_support_and_quantization(self):
        p = np.array([[.25, .75], [1., 0.], [0., 1.]])
        y = np.array([.5, -2., 4.])
        c = np.array([0., 2.])
        # E|X-y| - .5 E|X-X'|, calculated analytically for each row.
        np.testing.assert_allclose(a.continuous_crps(p, c, y), [.875, 2., 2.])
        np.testing.assert_allclose(a.continuous_crps(p, np.maximum(c, 1), np.maximum(y, 1)), [.5625, 0., 2.])

    def test_continuous_crps_matches_independent_pairwise_identity(self):
        rng = np.random.default_rng(719)
        p = rng.dirichlet(np.ones(4), size=17)
        c = np.array([.05, .15, .25, .35])
        y = rng.uniform(-.2, .7, size=17)
        expected = (p * np.abs(c[None] - y[:, None])).sum(1)
        expected -= .5 * np.einsum('ni,nj,ij->n', p, p, np.abs(c[:, None] - c[None]))
        np.testing.assert_allclose(a.continuous_crps(p, c, y), expected, atol=2e-16)

    def test_grid_target_is_not_continuous_target(self):
        p = np.zeros((2, 66)); p[:, 0] = 1
        scores = a.distribution_metrics(p, (np.arange(66) + .5) * .1,
            np.array([.01, .09]), np.array(['a', 'b']), np.ones(65))
        self.assertAlmostEqual(scores['quantized_grid_crps'], 0)
        self.assertAlmostEqual(scores['crps'], .04)
        self.assertIsNone(scores['intervals']['0.9']['m4_coverage'])
        self.assertEqual(scores['intervals']['0.9']['coverage'], 0)
        self.assertEqual(scores['intervals']['0.9']['quantized_bin_set_coverage'], 1)

    def test_event_macro_and_record_tail_are_distinct(self):
        result = a.point_metrics(np.array([4., 4., 4., 1.]), np.array([3., 3., 3., 4.]),
                                 np.array(['big', 'big', 'big', 'small']))
        self.assertAlmostEqual(result['mae'], 1.5)
        self.assertAlmostEqual(result['event_macro_mae'], 2.)
        self.assertEqual(result['fp4'], 1)
        self.assertEqual(result['m4_records'], 3)
        self.assertEqual(result['m4_events'], 1)
        self.assertEqual(result['cvar95'], 3)

    def test_pmf_roundoff_is_checked_not_arbitrarily_repaired(self):
        p, drift = a.validate_probability(np.array([[.2, .80000002]]), 1, 2)
        self.assertAlmostEqual(p.sum(), 1)
        self.assertGreater(drift, 0)
        for bad in ([[.2, .9]], [[-.1, 1.1]], [[np.nan, .2]]):
            with self.assertRaises(ValueError):
                a.validate_probability(bad, 1, 2)

    def test_median_tie_tolerance_does_not_accept_wrong_quantiles(self):
        p = np.array([[.5 + 1e-8, .5 - 1e-8]])
        c = np.array([0., 1.])
        result = a.validate_prediction(p, c, p @ c, np.array([1.]))
        self.assertEqual(result['float32_boundary_median_ambiguities'], 1)
        with self.assertRaises(ValueError):
            a.validate_prediction(np.array([[.75, .25]]), c, np.array([.25]), np.array([1.]))

    def test_zero_probability_reports_infinite_score_without_clipping(self):
        p = np.zeros((1, 66)); p[0, 0] = 1
        result = a.distribution_metrics(p, (np.arange(66) + .5) * .1,
            np.array([2.]), np.array(['a']), np.ones(65))
        self.assertEqual(result['categorical_nll'], {'mean': None, 'infinite_records': 1})
        self.assertEqual(result['quantized_ranked_log_score']['infinite_records'], 1)

    def test_reliability_bin_endpoint_and_event_weights(self):
        p = np.zeros((3, 66)); p[:2, 0] = 1; p[2, 65] = 1
        result = a.distribution_metrics(p, (np.arange(66) + .5) * .1,
            np.array([0., 0., 4.]), np.array(['a', 'a', 'b']), np.ones(65))
        calibration = result['tail_calibration']
        self.assertEqual(calibration['bins'][9]['records'], 1)
        self.assertEqual(calibration['event_macro_predicted'], .5)
        self.assertEqual(calibration['ece10'], 0)

    def test_manifest_rejects_corruption_and_unlisted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = {'config': {}, 'source_sha256': {}}
            canonical = json.dumps(identity, sort_keys=True, allow_nan=False)
            digest = a.hashlib.sha256(canonical.encode()).hexdigest()[:12]
            run = root / f'instrument_scores_1s_{digest}_fixture'; run.mkdir()
            (run / 'identity.json').write_text(canonical)
            (run / 'data.txt').write_text('complete')
            manifest = {p.name: {'bytes': p.stat().st_size, 'sha256': a.sha256(p)} for p in run.iterdir()}
            (run / 'artifacts.json').write_text(json.dumps(manifest))
            a.verify_manifest(run)
            (run / 'extra.txt').write_text('late')
            with self.assertRaisesRegex(ValueError, 'Unlisted'):
                a.verify_manifest(run)
            (run / 'extra.txt').unlink()
            (run / 'data.txt').write_text('corrupt!')
            with self.assertRaisesRegex(ValueError, 'hash'):
                a.verify_manifest(run)

    def test_reported_metric_change_fails(self):
        with self.assertRaisesRegex(ValueError, 'Metric mismatch'):
            a.compare_metrics({'mae': .4}, {'mae': .41})

    def test_gpu_replay_preserves_original_final_batch_sizes(self):
        self.assertEqual(gpu.batches(96993, 256)[-1], (96768, 96993))
        self.assertEqual(gpu.batches(96993, 2048)[-1], (96256, 96993))
        self.assertEqual(gpu.batches(2048, 2048), [(0, 2048)])
        with self.assertRaises(ValueError):
            gpu.batches(12, 0)

    def test_gpu_replay_model_equations_match_saved_architecture_on_cpu(self):
        import torch
        from replay_checkpoint_sample import SavedHead
        original = SavedHead().eval()
        replica = gpu.make_head().eval()
        replica.load_state_dict(original.state_dict(), strict=True)
        x, logits = torch.randn(7, 291), torch.randn(7, 66)
        with torch.inference_mode():
            self.assertTrue(torch.equal(original(x, logits), replica(x, logits)))
        self.assertFalse(torch.cuda.is_initialized())

    def test_gpu_replay_does_not_relax_failed_cpu_thresholds(self):
        self.assertEqual((gpu.LOGIT_ATOL, gpu.LOGIT_RTOL, gpu.PMF_ATOL, gpu.MEAN_ATOL),
                         (2e-3, 2e-4, 2e-4, 2e-3))
        with mock.patch.dict('os.environ', {'CUBLAS_WORKSPACE_CONFIG': 'wrong'}):
            with self.assertRaisesRegex(ValueError, 'cuBLAS workspace changed'):
                gpu.configure_runtime({'CUBLAS_WORKSPACE_CONFIG': ':4096:8'})

    def test_gpu_replay_rejects_nonfinite_batches_before_max_reduction(self):
        p = np.array([[.2, .8]])
        self.assertEqual(gpu.difference_metrics(p, p.copy(), np.array([0., 1.])), (0., 0.))
        for bad in (np.array([[np.nan, .8]]), np.array([[.2, np.inf]]), np.array([[.2, .7]])):
            with self.assertRaises(ValueError):
                gpu.difference_metrics(bad, p, np.array([0., 1.]))
            with self.assertRaises(ValueError):
                gpu.difference_metrics(p, bad, np.array([0., 1.]))


if __name__ == '__main__':
    unittest.main()
