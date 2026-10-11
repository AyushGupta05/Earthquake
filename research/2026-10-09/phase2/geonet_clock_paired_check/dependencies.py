"""Pinned existing source/runtime, with no installs or data discovery."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import types

BASE = Path(__file__).resolve().parent


def read(path, cap):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
        raise ValueError("bounded nonsymlink file required")
    with path.open("rb") as source:
        body = source.read(cap + 1)
    if len(body) > cap:
        raise ValueError("bounded file grew")
    return body


def sha(body):
    return hashlib.sha256(body).hexdigest()


def pins():
    return json.loads(read(BASE / "reviewed_dependencies.json", 1024 * 1024))


def body(name):
    item = pins()[name]
    source = read(BASE.parent / item["relative_path"], 32 * 1024 * 1024)
    if sha(source) != item["sha256"]:
        raise ValueError("reviewed dependency changed")
    return source


def module(name):
    if name not in ("downloader", "transport"):
        raise ValueError("only reviewed transport code may execute")
    source = body(name)
    result = types.ModuleType("paired_pinned_" + name)
    result.__file__ = str(BASE.parent / pins()[name]["relative_path"])
    exec(compile(source, result.__file__, "exec"), result.__dict__)
    return result


def runtime():
    for name in pins():
        body(name)
    receipt = json.loads(body("dependency_receipt"))
    if (receipt.get("dependency_lock_sha256") != pins()["dependency_lock"]["sha256"] or
            receipt.get("published_wheels_receipt_sha256") != pins()["wheel_receipt"]["sha256"] or
            receipt.get("all_resolved_packages_match_lock_and_are_workspace_local") is not True or
            receipt.get("synthetic_adapter_smoke_passed") is not True):
        raise ValueError("original verified dependency provenance required")
    expected = BASE.parent / "geonet_waveform_feasibility/.venv"
    if Path(sys.executable).absolute() != Path(receipt["python_executable"]) or (
            sys.version != receipt["python_version"]):
        raise ValueError("exact existing Python runtime required")
    for name, version in receipt["installed_resolved_packages"].items():
        package = importlib.metadata.distribution(name)
        if package.version != version or not Path(package.locate_file("")).absolute().is_relative_to(expected):
            raise ValueError("installed runtime metadata changed")
    binary = Path(sys.executable).resolve()
    result = {
        "executable": str(Path(sys.executable).absolute()), "resolved_binary": str(binary),
        "binary_sha256": sha(read(binary, 128 * 1024 * 1024)),
        "python_version": sys.version, "cache_tag": sys.implementation.cache_tag,
        "machine": os.uname().machine, "package_versions": receipt["installed_resolved_packages"],
        "dependency_receipt_sha256": pins()["dependency_receipt"]["sha256"], "installations": 0,
    }
    if result["binary_sha256"] != "2477b47fa3ae65b9574eb18a15edb364e96948eaa1875ad3f1c80d780efc9c12":
        raise ValueError("original runtime binary changed")
    return result
