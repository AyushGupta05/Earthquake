"""Only authored synthetic tests in the specifically authorized Linux user unit."""
import json
import os
from pathlib import Path
import sys
import unittest


def main():
    if sys.platform!="linux" or os.environ.get("CUDA_VISIBLE_DEVICES")!="":raise RuntimeError("invented_lane_controls")
    for name in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):
        if os.environ.get(name)!="1":raise RuntimeError("invented_lane_threads")
    entries=[line[3:] for line in Path("/proc/self/cgroup").read_text().splitlines() if line.startswith("0::")]
    if len(entries)!=1:raise RuntimeError("invented_lane_cgroup")
    base=Path("/sys/fs/cgroup").resolve();group=(base/entries[0].lstrip("/")).resolve()
    if group==base or base not in group.parents or group.name!="eew-information-pilot-invented-tests-v1-20261012.service":raise RuntimeError("invented_lane_owner")
    expected={"memory.max":"2147483648","memory.swap.max":"0","pids.max":"64","cpu.weight":"10"}
    for name,value in expected.items():
        if (group/name).read_text().strip()!=value:raise RuntimeError("invented_lane_limits")
    if str(os.getpid()) not in (group/"cgroup.procs").read_text().split():raise RuntimeError("invented_lane_membership")
    folder=Path(__file__).resolve().parent
    sys.path.insert(0,str(folder))
    tests=unittest.defaultTestLoader.discover(str(folder),pattern="test_*.py")
    result=unittest.TextTestRunner(verbosity=2).run(tests)
    import torch,numpy
    print(json.dumps(dict(schema="invented-information-pilot-tests-v1",tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),python=sys.version.split()[0],torch=torch.__version__,numpy=numpy.__version__,limits=expected,pid_membership=True,no_actual_inputs=True,no_fits=True),sort_keys=True))
    return 0 if result.wasSuccessful() and not result.skipped else 2


if __name__=="__main__":sys.exit(main())
