"""Run the byte-pinned predecessor's invented suite against its unchanged copy."""
import importlib.util
from pathlib import Path
import sys
import unittest
import v1_reference

_spec = importlib.util.spec_from_file_location("v1_invented_reference_tests", Path(__file__).with_name("v1_tests_reference.py"))
_previous = sys.modules.get("auditor")
sys.modules["auditor"] = v1_reference
try:
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
finally:
    if _previous is None:
        sys.modules.pop("auditor",None)
    else:
        sys.modules["auditor"] = _previous


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromModule(_module)
