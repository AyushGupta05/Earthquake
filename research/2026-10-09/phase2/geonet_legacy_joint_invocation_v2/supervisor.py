"""Bounded process-group supervisor; no event inputs or authorization are read here."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time

OUTPUT_CAP = 8 * 1024 * 1024
STDERR_CAP = 128 * 1024
PROTOCOL = "geonet_legacy_joint_invocation_v2"


def read_code(path, cap):
    p = Path(path)
    if not isinstance(path, str) or str(p) != path or not p.is_absolute() or p.resolve() != p or p.is_symlink():
        raise ValueError("noncanonical executable source path")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > cap:
            raise ValueError("unbounded executable source")
        body = stream.read(cap + 1)
    if len(body) > cap:
        raise ValueError("executable source grew beyond bound")
    return body


def file_sha(path, cap):
    return hashlib.sha256(read_code(path, cap)).hexdigest()


def exclusive(path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb")


def finalize_owned_receipt(path, owned, receipt):
    fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "wb") as stream:
        current = os.fstat(stream.fileno())
        if (current.st_dev, current.st_ino) != (owned.st_dev, owned.st_ino):
            raise ValueError("exclusive receipt was replaced")
        stream.truncate(0)
        stream.write(json.dumps(receipt, sort_keys=True, allow_nan=False).encode() + b"\n")


def terminate_group(proc, deadline):
    # Kill the session even if its leader exited: inherited pipes can belong to descendants.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        return False
    try:
        proc.wait(timeout=max(0.001, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        return False
    until = deadline
    while time.monotonic() < until:
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        time.sleep(0.01)
    return False


def supervise(runtime, runtime_sha256, child, child_sha256, supervisor_sha256,
              plan, plan_sha256, authorization, authorization_sha256, out_dir,
              max_seconds=120):
    start = time.monotonic()
    if type(max_seconds) not in (int, float) or not 0 < max_seconds <= 120:
        raise ValueError("deadline must be within 120 seconds")
    deadline = start + max_seconds
    # Reserve cleanup time inside the whole invocation ceiling. Expiry stays incomplete.
    processing_deadline = deadline - min(3, max_seconds / 4)
    root = Path(out_dir)
    if not isinstance(out_dir, str) or str(root) != out_dir or not root.is_absolute() or root.parent.resolve() != root.parent:
        raise ValueError("output parent must be canonical")
    # Existing directories, symlinks and prior failures are never reused or overwritten.
    root.mkdir(mode=0o700)
    receipt = {"protocol_id": PROTOCOL, "complete": False, "reason": "preflight_failed",
               "elapsed_seconds": None, "returncode": None, "group_termination_confirmed": None,
               "stdout_bytes": 0, "stderr_bytes": 0, "start_gate_released": False,
               "whole_invocation_limit_seconds": max_seconds,
               "plan_sha256": plan_sha256, "authorization_sha256": authorization_sha256,
               "adapter_sha256": child_sha256, "supervisor_sha256": supervisor_sha256,
               "runtime_sha256": runtime_sha256, "result_sha256": None,
               "no_network_actions_in_supervisor": True}
    proc = None
    interrupted = None
    try:
        for value in (runtime_sha256, child_sha256, supervisor_sha256, plan_sha256, authorization_sha256):
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("invalid invocation digest")
        child_bytes = read_code(child, 64 * 1024)
        if file_sha(runtime, 128 * 1024 * 1024) != runtime_sha256 or hashlib.sha256(child_bytes).hexdigest() != child_sha256:
            raise ValueError("runtime/child pin mismatch")
        if file_sha(str(Path(__file__).resolve()), 2 * 1024 * 1024) != supervisor_sha256:
            raise ValueError("supervisor pin mismatch")
        if time.monotonic() >= processing_deadline:
            raise ValueError("preflight elapsed deadline")
        # Launch the verified UTF-8 entry buffer, not a second read of a mutable script path.
        entry = "__file__ = " + repr(child) + "\n" + child_bytes.decode("utf-8")
        argv = [runtime, "-I", "-B", "-c", entry, "--plan", plan, "--authorization", authorization,
                "--plan-sha256", plan_sha256, "--authorization-sha256", authorization_sha256,
                "--adapter-sha256", child_sha256, "--supervisor-sha256", supervisor_sha256,
                "--runtime-sha256", runtime_sha256, "--runtime-path", runtime, "--deadline", str(processing_deadline)]
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True, close_fds=True,
                                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
        receipt["reason"] = "incomplete"
        # Popen may return late; never release reads after a stalled launch consumed the deadline.
        if time.monotonic() >= processing_deadline:
            receipt["reason"] = "launch_deadline"
        else:
            proc.stdin.write(b"G")
            proc.stdin.flush()
            receipt["start_gate_released"] = True
        proc.stdin.close()
        with exclusive(root / "stdout.part") as stdout, exclusive(root / "stderr.part") as stderr:
            selector = selectors.DefaultSelector()
            for stream, name, target, cap in ((proc.stdout, "stdout", stdout, OUTPUT_CAP), (proc.stderr, "stderr", stderr, STDERR_CAP)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, (name, target, cap))
            try:
                while selector.get_map() and receipt["reason"] == "incomplete":
                    remaining = processing_deadline - time.monotonic()
                    if remaining <= 0:
                        receipt["reason"] = "deadline"
                        break
                    for key, mask in selector.select(min(remaining, 0.05)):
                        name, target, cap = key.data
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                            continue
                        before = receipt[name + "_bytes"]
                        receipt[name + "_bytes"] += len(chunk)
                        target.write(chunk[:max(0, cap - before)])
                        if receipt[name + "_bytes"] > cap:
                            receipt["reason"] = name + "_overflow"
                            break
                if receipt["reason"] == "incomplete":
                    remaining = processing_deadline - time.monotonic()
                    if remaining <= 0:
                        receipt["reason"] = "deadline"
                    else:
                        try:
                            proc.wait(timeout=remaining)
                        except subprocess.TimeoutExpired:
                            receipt["reason"] = "deadline"
                        else:
                            if time.monotonic() >= processing_deadline:
                                receipt["reason"] = "deadline"
                            else:
                                receipt["reason"] = "child_failed" if proc.returncode else "candidate_complete"
            finally:
                selector.close()
        receipt["group_termination_confirmed"] = terminate_group(proc, deadline)
        receipt["returncode"] = proc.returncode
        if receipt["reason"] == "candidate_complete" and not receipt["group_termination_confirmed"]:
            receipt["reason"] = "group_termination_unconfirmed"
        if receipt["reason"] == "candidate_complete" and receipt["group_termination_confirmed"]:
            if time.monotonic() >= deadline:
                receipt["reason"] = "deadline"
            else:
                body = (root / "stdout.part").read_bytes()  # already capped on disk
                def pairs(items):
                    obj = {}
                    for key, value in items:
                        if key in obj:
                            raise ValueError("duplicate result field")
                        obj[key] = value
                    return obj
                def invalid_constant(value):
                    raise ValueError("nonfinite result field")
                result = json.loads(body, object_pairs_hook=pairs, parse_constant=invalid_constant)
                if not isinstance(result, dict) or set(result) != {"protocol_id", "private", "public_aggregate"} or result["protocol_id"] != PROTOCOL:
                    raise ValueError("invalid result envelope")
                aggregate = json.dumps(result["public_aggregate"], sort_keys=True, allow_nan=False).encode() + b"\n"
                if len(aggregate) > 65536 or time.monotonic() >= deadline:
                    raise ValueError("aggregate serialization limit/deadline")
                with exclusive(root / "public_aggregate.json") as stream:
                    stream.write(aggregate)
                os.link(root / "stdout.part", root / "private_result.json")
                os.unlink(root / "stdout.part")
                receipt.update(complete=True, reason="complete", result_sha256=hashlib.sha256(body).hexdigest())
    except BaseException as error:
        receipt["complete"] = False
        if not isinstance(error, Exception):
            interrupted = error
            receipt["reason"] = "supervisor_interrupted"
        if receipt["reason"] in ("incomplete", "candidate_complete"):
            receipt["reason"] = "supervisor_failure"
        if proc is not None:
            receipt["group_termination_confirmed"] = terminate_group(proc, deadline)
            receipt["returncode"] = proc.returncode
    finally:
        if proc is not None:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
        receipt["elapsed_seconds"] = time.monotonic() - start
        if receipt["elapsed_seconds"] >= max_seconds:
            receipt["complete"] = False
            receipt["reason"] = "whole_invocation_limit_elapsed"
        owned = None
        try:
            # The first persisted receipt is fail-closed even if write/close is interrupted.
            with exclusive(root / "receipt.json") as stream:
                owned = os.fstat(stream.fileno())
                initial = dict(receipt, complete=False, reason="receipt_finalization_incomplete")
                stream.write(json.dumps(initial, sort_keys=True, allow_nan=False).encode() + b"\n")
            receipt["elapsed_seconds"] = time.monotonic() - start
            if receipt["elapsed_seconds"] >= max_seconds:
                receipt.update(complete=False, reason="whole_invocation_limit_elapsed")
            finalize_owned_receipt(root / "receipt.json", owned, receipt)
            after_receipt = time.monotonic() - start
            if after_receipt >= max_seconds:
                receipt.update(complete=False, reason="whole_invocation_limit_elapsed", elapsed_seconds=after_receipt)
                finalize_owned_receipt(root / "receipt.json", owned, receipt)
        except BaseException:
            receipt.update(complete=False, reason="receipt_finalization_failed", elapsed_seconds=time.monotonic() - start)
            if owned is not None:
                try:
                    finalize_owned_receipt(root / "receipt.json", owned, receipt)
                except BaseException:
                    # No normal return/exit means publication is forbidden even if storage failed.
                    pass
            raise
    if interrupted is not None:
        raise interrupted
    return receipt


def main():
    parser = argparse.ArgumentParser()
    for field in ("runtime", "runtime-sha256", "child", "child-sha256", "supervisor-sha256", "plan",
                  "plan-sha256", "authorization", "authorization-sha256", "out-dir"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    receipt = supervise(**vars(args))
    # The receipt lives privately; stdout is aggregate process status only.
    print(json.dumps({"complete": receipt["complete"], "reason": receipt["reason"]}))
    return 0 if receipt["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
