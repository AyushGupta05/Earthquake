# Exact one-off scalar arithmetic record

Ran once after the protocol was saved. Interpreter `/Users/ayush/.venvs/ml/bin/python3` (the existing research environment); arithmetic uses only Python standard-library math. Exit0; no warnings. No learned model, author code, waveforms, real labels or stored predictions are involved. Algebraic phase/circular-boundary examples in the protocol/report are hand derivations, not numerical waveform tests. The following was the exact calculation body; the original tool command supplied it through a shell heredoc.

```python
import math, json
from pathlib import Path
from hashlib import sha256
p = Path('work/geonet_spectral_mechanism_research/SCALAR_PROTOCOL.md')
eps = 1e-5
q = 10**1.5
fc1, fc2 = 0.1, 0.1/math.sqrt(q)
def spectrum(omega, fc, f):
    return omega/(1+(f/fc)**2)
result = {
    'protocol_sha256': sha256(p.read_bytes()).hexdigest(),
    'amplitude_compression': [
        {'c': c, 'instance_norm_factor': c/math.sqrt(c*c+eps), 'log10_amplitude_bypass': math.log10(c)}
        for c in [1, 10, 100]
    ],
    'slot_order': {'weighted_1_3': 1+2*3, 'weighted_3_1': 3+2*1, 'symmetric_1_3': 1+3, 'symmetric_3_1': 3+1},
    'first32_mode_max_hz': [{'length': n, 'hz': 31*100/n} for n in [600, 800, 1000]],
    'fixed1000_mode_max_hz_all_horizons': 31*100/1000,
    'rms_frequency_period': {'clean': math.sqrt(1/0.5**2), 'contaminated': math.sqrt(1.01/(0.5**2+0.01*20**2)), 'ideal_known_noise_removed': math.sqrt(1/0.5**2)},
    'source_spectrum': {'omega_ratio': q, 'fc1': fc1, 'fc2': fc2, 'high_frequency_product1': fc1**2, 'high_frequency_product2': q*fc2**2, 'ratios': [{'f': f, 'ratio': spectrum(q,fc2,f)/spectrum(1,fc1,f)} for f in [1,3,5]]}
}
print(json.dumps(result, indent=2, allow_nan=False))
```

Complete output (retained without selecting favorable panels):

```json
{
  "protocol_sha256": "51871018a31b400cfaef24a9fa8b9e1bb7befae56906c8d21f7d54c8e6285b36",
  "amplitude_compression": [
    {
      "c": 1,
      "instance_norm_factor": 0.9999950000374997,
      "log10_amplitude_bypass": 0.0
    },
    {
      "c": 10,
      "instance_norm_factor": 0.9999999500000037,
      "log10_amplitude_bypass": 1.0
    },
    {
      "c": 100,
      "instance_norm_factor": 0.9999999995000001,
      "log10_amplitude_bypass": 2.0
    }
  ],
  "slot_order": {
    "weighted_1_3": 7,
    "weighted_3_1": 5,
    "symmetric_1_3": 4,
    "symmetric_3_1": 4
  },
  "first32_mode_max_hz": [
    {
      "length": 600,
      "hz": 5.166666666666667
    },
    {
      "length": 800,
      "hz": 3.875
    },
    {
      "length": 1000,
      "hz": 3.1
    }
  ],
  "fixed1000_mode_max_hz_all_horizons": 3.1,
  "rms_frequency_period": {
    "clean": 2.0,
    "contaminated": 0.48749057306119203,
    "ideal_known_noise_removed": 2.0
  },
  "source_spectrum": {
    "omega_ratio": 31.622776601683793,
    "fc1": 0.1,
    "fc2": 0.01778279410038923,
    "high_frequency_product1": 0.010000000000000002,
    "high_frequency_product2": 0.010000000000000002,
    "ratios": [
      {
        "f": 1,
        "ratio": 1.0096807109243942
      },
      {
        "f": 3,
        "ratio": 1.0010759368880962
      },
      {
        "f": 5,
        "ratio": 1.000387345989777
      }
    ]
  }
}
```

This record preserves source and arithmetic rather than providing a training runner. No author code was executed or persistent production Python implementation introduced, and no learned result is asserted.
