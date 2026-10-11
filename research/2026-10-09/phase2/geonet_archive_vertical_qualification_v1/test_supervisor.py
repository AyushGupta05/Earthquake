"""Invented supervisor lifecycle fixtures preserved from reviewed joint V2."""
import json,os,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import importlib.util
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("supervisor",ROOT/"supervisor.py")
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
VALID_RESULT = {"protocol_id": "geonet-archive-vertical-qualification-v1", "private": {
    "slots": [{"slot_index": i, "status": "failed", "reason": "invented",
               "windows": {str(h): {"core": {"available": None}} for h in (1,3,5)}} for i in range(4)],
    "provenance": {"plan_sha256": "1"*64, "authorization_sha256": "2"*64,
        "source_files": {k: "0"*64 for k in ("core.py", "qualification.py", "child_harness.py", "supervisor.py", "PROTOCOL.md", "SCHEMAS.md", "RUNTIME_PINS.json")},
        "pushed_source_commit": "a"*40, "validated_body_count": 4, "advertised_samples_decoded": 0}},
    "public_aggregate": {"slots":4, "decoded_slots":0, "failed_slots":4,
        "literal_identity_matching_slots":0, "consistent_observed_rate_slots":0,
        "complete_decoded_trace_windows":{"1":0,"3":0,"5":0},"filename_boundary_crossing_trace_count":0,
        "metadata_rate_verified":False,"filename_partition_verified":False,"response_calibration_verified":False,
        "physical_clipping_verified":False,"three_component_available_verified":False,
        "operational_availability_verified":False,"model_improvement_verified":False}}

class SupervisorTests(unittest.TestCase):
    def run_child(self, root, code, max_seconds=2, **overrides):
        root = Path(root).resolve()
        child = root / "invented_child.py"
        child.write_text("import sys, time, os, subprocess, json\nif sys.stdin.buffer.read(1) != b'G': sys.exit(1)\n" + "RESULT = " + repr(VALID_RESULT) + "\nRESULT['private']['provenance']['source_files']['child_harness.py'] = sys.argv[sys.argv.index('--adapter-sha256')+1]\nRESULT['private']['provenance']['source_files']['supervisor.py'] = sys.argv[sys.argv.index('--supervisor-sha256')+1]\n" + code)
        runtime = str(Path(sys.executable).resolve())
        kwargs = dict(runtime=runtime, runtime_sha256=s.file_sha(runtime, 128 * 1024 * 1024),
            child=str(child), child_sha256=s.file_sha(str(child), 2 * 1024 * 1024),
            supervisor_sha256=s.file_sha(str(ROOT / "supervisor.py"), 2 * 1024 * 1024),
            plan=str(root / "never_read_plan"), plan_sha256="1" * 64,
            authorization=str(root / "never_read_auth"), authorization_sha256="2" * 64,
            out_dir=str(root / "exclusive_output"), max_seconds=max_seconds)
        kwargs.update(overrides)
        return s.supervise(**kwargs), kwargs

    def test_site_startup_disabled_before_child_gate(self):
        import sysconfig
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            venv = root / "invented_venv"
            (venv / "bin").mkdir(parents=True)
            executable = venv / "bin/python"
            executable.symlink_to(Path(sys.executable).resolve())
            (venv / "pyvenv.cfg").write_text("home = " + str(Path(sys.executable).resolve().parent) + "\ninclude-system-site-packages = false\n")
            packages = venv / ("lib/python%d.%d/site-packages" % sys.version_info[:2])
            packages.mkdir(parents=True)
            marker = root / "startup_marker"
            (packages / "invented.pth").write_text("import pathlib; pathlib.Path(" + repr(str(marker)) + ").write_text('PTH_SENTINEL')\n")
            # The invented hook demonstrably executes under the old launch flags.
            subprocess.run([str(executable), "-I", "-B", "-c", "pass"], check=True)
            self.assertTrue(marker.exists()); marker.unlink()
            receipt, kwargs = self.run_child(root,
                "assert sys.flags.no_site == 1\nprint(json.dumps(RESULT))\n",
                runtime=str(executable))
            self.assertTrue(receipt["complete"])
            self.assertFalse(marker.exists())

    def test_incomplete_or_public_leaking_result_never_published(self):
        mutations = ("RESULT['private']['slots'] = []", "RESULT['private']['slots'].pop()",
                     "RESULT['private']['slots'][3]['slot_index'] = 2",
                     "RESULT['public_aggregate']['PRIVATE_SENTINEL'] = 'AAA'",
                     "RESULT['public_aggregate']['decoded_slots'] = True",
                     "RESULT['public_aggregate']['operational_availability_verified'] = True",
                     "RESULT['private']['slots'][0]['windows'].pop('3')",
                     "RESULT['private']['slots'][0]['windows']['1']['core']['available'] = True",
                     "RESULT['private']['slots'][0]['literal_identity_matches'] = True")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                receipt, kwargs = self.run_child(directory, mutation + "\nprint(json.dumps(RESULT))\n")
                self.assertFalse(receipt["complete"])
                self.assertFalse((Path(kwargs["out_dir"])/"public_aggregate.json").exists())

    def test_success_exclusive_and_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt, kwargs = self.run_child(directory, "print(json.dumps(RESULT))\n")
            self.assertTrue(receipt["complete"])
            root = Path(kwargs["out_dir"])
            self.assertTrue((root / "private_result.json").is_file())
            self.assertEqual(json.loads((root / "public_aggregate.json").read_bytes()), VALID_RESULT["public_aggregate"])
            self.assertFalse((root / "stdout.part").exists())
            with self.assertRaises(FileExistsError):
                s.supervise(**kwargs)

    def test_timeout_retains_partial_and_confirms_kill(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt, kwargs = self.run_child(directory, "print('partial', flush=True)\ntime.sleep(10)\n", max_seconds=0.4)
            self.assertFalse(receipt["complete"])
            self.assertTrue(receipt["group_termination_confirmed"])
            self.assertEqual(receipt["returncode"], -signal.SIGKILL)
            self.assertEqual((Path(kwargs["out_dir"]) / "stdout.part").read_bytes(), b"partial\n")

    def test_stdout_and_stderr_overflow(self):
        for stream in ("stdout", "stderr"):
            with self.subTest(stream=stream), tempfile.TemporaryDirectory() as directory:
                with patch.object(s, "OUTPUT_CAP", 100), patch.object(s, "STDERR_CAP", 100):
                    receipt, kwargs = self.run_child(directory, f"sys.{stream}.buffer.write(b'x' * 1000); sys.{stream}.flush(); time.sleep(10)\n")
                self.assertEqual(receipt["reason"], stream + "_overflow")
                self.assertFalse(receipt["complete"])
                self.assertTrue(receipt["group_termination_confirmed"])
                self.assertEqual((Path(kwargs["out_dir"]) / (stream + ".part")).stat().st_size, 100)

    def test_invalid_result_failed_exit_and_pin(self):
        for code in ("print('not json')\n", "sys.exit(3)\n", "print('{\"protocol_id\":\"x\",\"private\":{},\"public_aggregate\":{}}')\n",
                     "print('{\"protocol_id\":\"geonet-archive-vertical-qualification-v1\",\"private\":{},\"public_aggregate\":{},\"private\":{}}')\n"):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                receipt, kwargs = self.run_child(directory, code)
                self.assertFalse(receipt["complete"])
                self.assertFalse((Path(kwargs["out_dir"]) / "private_result.json").exists())
        with tempfile.TemporaryDirectory() as directory:
            receipt, kwargs = self.run_child(directory, "raise Exception('never launched')\n", runtime_sha256="0" * 64)
            self.assertFalse(receipt["start_gate_released"])
            self.assertIsNone(receipt["returncode"])

    def test_launch_stall_does_not_release_gate(self):
        original = subprocess.Popen
        def stalled(*args, **kwargs):
            time.sleep(0.16)
            return original(*args, **kwargs)
        with tempfile.TemporaryDirectory() as directory, patch.object(s.subprocess, "Popen", side_effect=stalled):
            receipt, kwargs = self.run_child(directory, "raise Exception('gate must remain closed')\n", max_seconds=0.2)
        self.assertFalse(receipt["start_gate_released"])
        self.assertFalse(receipt["complete"])
        self.assertTrue(receipt["group_termination_confirmed"])

    def test_successful_wait_crosses_processing_deadline(self):
        original = subprocess.Popen
        def late_wait(*args, **kwargs):
            proc = original(*args, **kwargs)
            wait = proc.wait
            delayed = False
            def wrapped(timeout=None):
                nonlocal delayed
                result = wait(timeout=timeout)
                if not delayed:
                    delayed = True
                    time.sleep(0.31)
                return result
            proc.wait = wrapped
            return proc
        with tempfile.TemporaryDirectory() as directory, patch.object(s.subprocess, "Popen", side_effect=late_wait):
            receipt, kwargs = self.run_child(directory, "print(json.dumps(RESULT))\n", max_seconds=0.4)
            self.assertFalse(receipt["complete"])
            self.assertIn(receipt["reason"], ("deadline", "whole_invocation_limit_elapsed"))

    def test_keyboard_interrupt_terminates_group_before_reraise(self):
        original_popen = subprocess.Popen
        original_selector = s.selectors.DefaultSelector
        processes = []
        def captured(*args, **kwargs):
            proc = original_popen(*args, **kwargs)
            processes.append(proc)
            return proc
        class InterruptedSelector:
            def __init__(self):
                self.delegate = original_selector()
            def register(self, *args):
                return self.delegate.register(*args)
            def get_map(self):
                return self.delegate.get_map()
            def select(self, *args):
                raise KeyboardInterrupt()
            def close(self):
                return self.delegate.close()
        with tempfile.TemporaryDirectory() as directory:
            try:
                with patch.object(s.subprocess, "Popen", side_effect=captured), patch.object(s.selectors, "DefaultSelector", InterruptedSelector):
                    with self.assertRaises(KeyboardInterrupt):
                        self.run_child(directory, "time.sleep(10)\n")
                receipt = json.loads((Path(directory).resolve() / "exclusive_output/receipt.json").read_bytes())
                self.assertTrue(receipt["group_termination_confirmed"])
                self.assertEqual(processes[0].returncode, -signal.SIGKILL)
            finally:
                for proc in processes:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()

    def test_descendant_inherits_pipe_group_killed(self):
        original_killpg = os.killpg
        with tempfile.TemporaryDirectory() as directory, patch.object(s.os, "killpg", wraps=original_killpg) as group_signal:
            # Descendant retains the pipe. Completion must wait/expire and kill the entire session.
            receipt, kwargs = self.run_child(directory, "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])\nsys.exit(0)\n", max_seconds=0.5)
            self.assertFalse(receipt["complete"])
            self.assertIn(receipt["reason"], ("deadline", "whole_invocation_limit_elapsed"))
            self.assertIsInstance(receipt["group_termination_confirmed"], bool)
            self.assertTrue(any(call.args[1] == signal.SIGKILL for call in group_signal.call_args_list))
            self.assertFalse((Path(kwargs["out_dir"]) / "private_result.json").exists())

    def test_symlink_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "target"
            target.mkdir()
            (root / "exclusive_output").symlink_to(target)
            with self.assertRaises(FileExistsError):
                self.run_child(directory, "print('{}')\n")

    def test_unconfirmed_group_never_complete(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(s, "terminate_group", return_value=False):
            receipt, kwargs = self.run_child(directory, "print(json.dumps(RESULT))\n")
            self.assertFalse(receipt["complete"])
            self.assertEqual(receipt["reason"], "group_termination_unconfirmed")
            self.assertFalse((Path(kwargs["out_dir"]) / "private_result.json").exists())

    def test_slow_final_receipt_is_incomplete_on_disk(self):
        original = s.exclusive
        class SlowReceipt:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self.stream
            def __exit__(self, *args):
                self.stream.close()
                time.sleep(0.5)
        def delayed(path):
            stream = original(path)
            return SlowReceipt(stream) if Path(path).name == "receipt.json" else stream
        with tempfile.TemporaryDirectory() as directory, patch.object(s, "exclusive", side_effect=delayed):
            receipt, kwargs = self.run_child(directory, "print(json.dumps(RESULT))\n", max_seconds=0.4)
            saved = json.loads((Path(kwargs["out_dir"]) / "receipt.json").read_bytes())
            self.assertFalse(receipt["complete"])
            self.assertFalse(saved["complete"])
            self.assertGreaterEqual(saved["elapsed_seconds"], 0.4)

    def test_interrupt_on_initial_receipt_close_cannot_leave_complete(self):
        original = s.exclusive
        class InterruptedReceipt:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self.stream
            def __exit__(self, *args):
                self.stream.close()
                raise KeyboardInterrupt()
        def interrupted(path):
            stream = original(path)
            return InterruptedReceipt(stream) if Path(path).name == "receipt.json" else stream
        with tempfile.TemporaryDirectory() as directory, patch.object(s, "exclusive", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.run_child(directory, "print(json.dumps(RESULT))\n")
            saved = json.loads((Path(directory).resolve() / "exclusive_output/receipt.json").read_bytes())
            self.assertFalse(saved["complete"])

    def test_interrupt_after_candidate_receipt_commit_invalidates(self):
        original = s.finalize_owned_receipt
        count = 0
        def interrupted(path, owned, receipt):
            nonlocal count
            count += 1
            original(path, owned, receipt)
            if count == 1:
                raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as directory, patch.object(s, "finalize_owned_receipt", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.run_child(directory, "print(json.dumps(RESULT))\n")
            saved = json.loads((Path(directory).resolve() / "exclusive_output/receipt.json").read_bytes())
            self.assertFalse(saved["complete"])
            self.assertEqual(saved["reason"], "receipt_finalization_failed")

    def test_receipt_finalization_never_overwrites_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "receipt.json"
            with s.exclusive(path) as stream:
                owned = os.fstat(stream.fileno())
                stream.write(b"owned")
            replacement = root / "replacement"
            replacement.write_bytes(b"unrelated")
            os.replace(replacement, path)
            with self.assertRaises(ValueError):
                s.finalize_owned_receipt(path, owned, {"complete": False})
            self.assertEqual(path.read_bytes(), b"unrelated")



if __name__ == "__main__": unittest.main()
