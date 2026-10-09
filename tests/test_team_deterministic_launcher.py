"""Standalone launcher contract; no real data, CUDA allocation, or fitting."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


WRAPPER = Path(__file__).resolve().parents[1] / "research/2026-10-09/phase3/run_team_deterministic.py"
FAKE_TORCH = '''
import os
from types import SimpleNamespace
assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8", "workspace was set too late"
__version__ = "test-torch"
version = SimpleNamespace(cuda="test-cuda")
backends = SimpleNamespace(cudnn=SimpleNamespace(deterministic=False,benchmark=True,allow_tf32=True),
                           cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=False)))
_enabled = False
def use_deterministic_algorithms(enabled):
    global _enabled
    _enabled = enabled
def are_deterministic_algorithms_enabled(): return _enabled
def is_deterministic_algorithms_warn_only_enabled(): return False
def get_float32_matmul_precision(): return "highest"
'''
RUNNER = '''
import json, os, pathlib, sys, torch
assert torch.are_deterministic_algorithms_enabled()
assert not torch.is_deterministic_algorithms_warn_only_enabled()
assert torch.backends.cudnn.deterministic
assert not torch.backends.cudnn.benchmark
assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
assert sys.path[0] == str(pathlib.Path(__file__).parent)
print("RUNNER_ARGUMENTS", json.dumps(sys.argv[1:]), flush=True)
'''


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.wrapper = self.root / WRAPPER.name
        shutil.copyfile(WRAPPER, self.wrapper)
        (self.root / "torch.py").write_text(FAKE_TORCH)
        (self.root / "train_team_lm.py").write_text(RUNNER)
        self.audit = self.root / "audit.json"

    def tearDown(self):
        self.temp.cleanup()

    def launch(self, *arguments):
        environment = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "2",
                       "CUBLAS_WORKSPACE_CONFIG": ":16:8"}
        return subprocess.run([sys.executable, str(self.wrapper), "--determinism-audit", str(self.audit),
                               "--", *arguments], capture_output=True, text=True, env=environment, timeout=45)

    def test_preimport_flags_forwarding_hashes_and_tf32_preserved(self):
        arguments = ["--cache", "a path with spaces.hdf5", "--epochs", "100", "--skip-dev"]
        result = self.launch(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        audit = json.loads(self.audit.read_text())
        self.assertEqual(audit["runner_arguments"], arguments)
        self.assertEqual(audit["wrapper_sha256"], hashlib.sha256(WRAPPER.read_bytes()).hexdigest())
        self.assertEqual(audit["runner_sha256"], hashlib.sha256(RUNNER.encode()).hexdigest())
        self.assertEqual(audit["previous_cublas_workspace_config"], ":16:8")
        self.assertEqual(audit["cublas_workspace_config"], ":4096:8")
        self.assertTrue(audit["deterministic_algorithms"])
        self.assertFalse(audit["deterministic_warn_only"])
        self.assertTrue(audit["cudnn_deterministic"])
        self.assertFalse(audit["cudnn_benchmark"])
        self.assertTrue(audit["cudnn_allow_tf32"])
        self.assertFalse(audit["cuda_matmul_allow_tf32"])
        self.assertEqual(audit["float32_matmul_precision"], "highest")
        forwarded = next(line for line in result.stdout.splitlines() if line.startswith("RUNNER_ARGUMENTS "))
        self.assertEqual(json.loads(forwarded.removeprefix("RUNNER_ARGUMENTS ")), arguments)
        logged = next(line for line in result.stdout.splitlines() if line.startswith("DETERMINISTIC_RUNTIME "))
        self.assertEqual(json.loads(logged.removeprefix("DETERMINISTIC_RUNTIME ")), audit)

    def test_existing_audit_is_not_overwritten_or_runner_executed(self):
        self.audit.write_text("original evidence")
        result = self.launch("--epochs", "100")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.audit.read_text(), "original evidence")
        self.assertNotIn("RUNNER_ARGUMENTS", result.stdout)

    def test_missing_runner_fails_before_audit_and_training(self):
        (self.root / "train_team_lm.py").unlink()
        result = self.launch("--epochs", "100")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.audit.exists())

    def test_already_imported_torch_is_rejected(self):
        code = ("import runpy,sys,types; sys.modules['torch']=types.ModuleType('torch');"
                f"sys.argv=[{str(self.wrapper)!r},'--determinism-audit',{str(self.audit)!r},'--','--epochs','100'];"
                f"runpy.run_path({str(self.wrapper)!r},run_name='__main__')")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fresh Python process", result.stderr)
        self.assertFalse(self.audit.exists())

    def test_runner_failure_propagates_and_preserves_audit(self):
        (self.root / "train_team_lm.py").write_text("raise SystemExit(17)\n")
        result = self.launch("--epochs", "100")
        self.assertEqual(result.returncode, 17)
        self.assertTrue(self.audit.exists())

    @unittest.skipUnless(importlib.util.find_spec("torch"), "Real Torch is not installed")
    def test_real_torch_cpu_runtime_flags(self):
        (self.root / "torch.py").unlink()
        result = self.launch("--epochs", "100")
        self.assertEqual(result.returncode, 0, result.stderr)
        audit = json.loads(self.audit.read_text())
        self.assertTrue(audit["deterministic_algorithms"])
        self.assertFalse(audit["deterministic_warn_only"])
        self.assertTrue(audit["cudnn_deterministic"])


if __name__ == "__main__":
    unittest.main()
