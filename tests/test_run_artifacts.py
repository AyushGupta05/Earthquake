import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('run_artifacts', Path(__file__).resolve().parents[1] / 'research/2026-10-09/phase2/run_artifacts.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ArtifactIdentityTests(unittest.TestCase):
    def test_repeated_and_changed_runs_preserve_old_artifacts(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'source.py'
            source.write_text('original')
            first = module.create_run(root, 'run', {'epochs': 1, 'seed': 2}, [source])
            (first / 'model.pth').write_bytes(b'old model')
            repeat = module.create_run(root, 'run', {'epochs': 1, 'seed': 2}, [source])
            changed = module.create_run(root, 'run', {'epochs': 2, 'seed': 2}, [source])
            source.write_text('changed')
            code_changed = module.create_run(root, 'run', {'epochs': 1, 'seed': 2}, [source])
            self.assertEqual(len({first, repeat, changed, code_changed}), 4)
            self.assertEqual((first / 'model.pth').read_bytes(), b'old model')
            self.assertEqual(first.name.split('_')[1], repeat.name.split('_')[1])
            self.assertNotEqual(first.name.split('_')[1], changed.name.split('_')[1])
            self.assertNotEqual(first.name.split('_')[1], code_changed.name.split('_')[1])
            self.assertEqual(json.loads((first / 'identity.json').read_text())['config'], {'epochs': 1, 'seed': 2})


if __name__ == '__main__':
    unittest.main()
