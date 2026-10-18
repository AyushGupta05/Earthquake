"""Convert the 5 s INSTANCE cache to a compact GPU-friendly float16 array.

For every record r: scale[r] = max |x[r]| over 3 x 500 standardized samples,
wave16[r] = float16(x[r] / scale[r]). Exact float32 values are recovered to
about 1e-3 relative precision as wave16 * scale. 1 s and 3 s inputs are the
first 100 / 300 samples (verified identical to the dedicated caches).
Row order: train, val, test (matches meta.npz).
"""
import argparse
from pathlib import Path

import h5py
import numpy as np

CACHE = '/data/Instance_windows_5s.hdf5'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/mnt/eew-research/runs/tailwork')
    ap.add_argument('--chunk', type=int, default=40000)
    args = ap.parse_args()
    out = Path(args.out)
    with h5py.File(CACHE, 'r') as h5:
        sizes = [h5[s + '/waveforms'].shape[0] for s in ('train', 'val', 'test')]
        total = sum(sizes)
        wave = np.lib.format.open_memmap(out / 'wave16.npy', 'w+', np.float16, (total, 3, 500))
        scale = np.zeros(total, np.float32)
        offset = 0
        for split, n in zip(('train', 'val', 'test'), sizes):
            ds = h5[split + '/waveforms']
            for start in range(0, n, args.chunk):
                x = ds[start:start + args.chunk]
                if not np.isfinite(x).all():
                    raise ValueError(f'nonfinite waveform in {split} chunk {start}')
                s = np.abs(x).reshape(len(x), -1).max(1)
                s = np.where(s > 0, s, 1.0).astype(np.float32)
                wave[offset + start:offset + start + len(x)] = (x / s[:, None, None]).astype(np.float16)
                scale[offset + start:offset + start + len(x)] = s
                print(split, start, flush=True)
            offset += n
        wave.flush()
    np.save(out / 'scale.npy', scale)
    print('done', total)


if __name__ == '__main__':
    main()
