"""Synthetic CPU-only comparison against the existing pinned Torch51 formulas."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import torch
from features import prefix51

torch.set_num_threads(1)
path = Path(sys.argv[1])
source = path.read_text()
function = next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='prefix_features')
namespace = {'np':np,'torch':torch}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),'exec'),namespace)
results = []
for seconds in (1,3,5):
    for scale in (0.,1e-5,1.,1e5):
        x = np.random.default_rng(20261009).normal(size=(3,100*seconds))*scale
        expected = namespace['prefix_features'](torch.from_numpy(x[None]))[0].numpy()
        actual = prefix51(x)
        # Existing Torch crossing fraction deliberately casts to float32, and
        # its FFT frequency grid is float32. NumPy diagnostic uses float64.
        np.testing.assert_allclose(actual,expected,rtol=1e-7,atol=5e-8)
        results.append({'seconds':seconds,'scale':scale,'max_abs_difference':float(np.abs(actual-expected).max())})
print(json.dumps({'scope':'synthetic arrays only, CPU; no real data or target access',
                  'source':str(path),'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
                  'torch_version':torch.__version__,'cases':results},indent=2))
