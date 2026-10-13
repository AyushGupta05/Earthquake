"""Runs only this packet's invented tests; writes generic result to stdout."""
import hashlib
import json
import pathlib
import platform
import sys
import time
import unittest
import numpy as np
import scipy


def run():
    here=pathlib.Path(__file__).resolve().parent
    sys.path.insert(0,str(here))
    suite=unittest.defaultTestLoader.discover(str(here),pattern='test_*.py')
    start=time.perf_counter();r=unittest.TextTestRunner(verbosity=2,stream=sys.stderr).run(suite)
    pins={p.name:dict(bytes=len(p.read_bytes()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in sorted(here.glob('*.py'))}
    receipt=dict(schema='renewal-score-audit-v3-invented-test-receipt-v1',actual_data=False,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,tests=r.testsRun,errors=len(r.errors),failures=len(r.failures),skipped=len(r.skipped),normal=bool(r.wasSuccessful()),seconds=time.perf_counter()-start,source_pins=pins)
    print(json.dumps(receipt,allow_nan=False,sort_keys=True,indent=2))
    return 0 if r.wasSuccessful()and not r.skipped else 1


if __name__=='__main__':raise SystemExit(run())
