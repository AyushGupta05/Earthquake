"""Relabelled copies of the Northern-Chile cache (label-construct check of AUDIT_2026-10-30.md, M1).

For LABEL in M_EXT, MW_SIPPL (columns of the TEAM-LM event table next to the MA used by
chile_prep.py) writes <out>/meta.npz, a copy of the Chile meta.npz in which

  mag        = LABEL where the event has it, else the original MA (training needs every row,
               because wave16.npy is shared by symlink and row-aligned with meta.npz)
  mag_type   = LABEL or 'MA' accordingly
  label_ok   = True where mag is LABEL (use it to score the tail on relabelled events only:
               robust_tail.py --tail-mask meta:label_ok)
  mag_MA     = the original MA label

fold and cluster are unchanged, so CV is comparable with the MA arms. wave16.npy, scale.npy and
folds.json are symlinks to the original cache; events.csv is rewritten with the same columns plus
mag_MA and label_ok.

  python tailrisk/chile_relabel.py --label M_EXT --out /mnt/scratch/chile_relabel_mext
"""
import argparse
import json
import os
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

SRC = Path('/mnt/eew-research/runs/tailwork/chile')
TABLE = Path('/mnt/eew-research/chile/chile_train_dev_full3000.hdf5')


def event_table():
    with h5py.File(TABLE, 'r') as h:
        t = h['metadata/event_metadata/table'][:]
    v = pd.DataFrame(t['values_block_0'], columns=['LAT', 'LON', 'DEPTH', 'TIME', 'ML', 'MW_SIPPL', 'M_EXT', 'MA', 'std_MA'])
    v.index = [x[0].decode() if isinstance(x[0], bytes) else str(x[0]) for x in t['values_block_2']]
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--label', required=True, choices=['M_EXT', 'MW_SIPPL'])
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    m = np.load(SRC / 'meta.npz', allow_pickle=True)
    meta = {k: m[k] for k in m.files}
    ev = pd.read_csv(SRC / 'events.csv')
    alt = event_table().reindex(ev.source_id.astype(str))
    assert np.allclose(alt.MA.to_numpy(), ev.mag.to_numpy(), atol=1e-4), 'event table not aligned with events.csv'
    lab_ev = alt[args.label].to_numpy(float)
    ok_ev = np.isfinite(lab_ev)
    new_ev = np.where(ok_ev, lab_ev, ev.mag.to_numpy(float))
    e = meta['event']
    assert np.allclose(ev.mag.to_numpy()[e], meta['mag'], atol=1e-4), 'events.csv not aligned with meta.npz'
    meta['mag_MA'] = meta['mag'].copy()
    meta['mag'] = new_ev[e].astype(np.float32)
    meta['label_ok'] = ok_ev[e]
    meta['mag_type'] = np.where(ok_ev[e], args.label, 'MA').astype('<U8')
    np.savez(out / 'meta.npz', **meta)
    ev2 = ev.copy()
    ev2['mag_MA'] = ev2.mag
    ev2['mag'] = new_ev
    ev2['mag_type'] = np.where(ok_ev, args.label, 'MA')
    ev2['label_ok'] = ok_ev
    ev2.to_csv(out / 'events.csv', index=False)
    for f in ('wave16.npy', 'scale.npy', 'folds.json'):
        os.symlink(SRC / f, out / f)

    rec = ev.records.to_numpy()
    summary = {'label': args.label, 'source': str(SRC), 'records': int(len(e)), 'events': int(len(ev)),
               'events_with_label': int(ok_ev.sum()), 'records_with_label': int(rec[ok_ev].sum())}
    for t in (4, 5, 6):
        lab = ok_ev & (lab_ev >= t - 1e-6)
        ma = ev.mag.to_numpy() >= t - 1e-6
        summary[f'>={t}'] = {
            'label: events': int(lab.sum()), 'label: records': int(rec[lab].sum()),
            'label: clusters': int(ev.cluster[lab].nunique()),
            'MA: events': int(ma.sum()), 'MA: records': int(rec[ma].sum()),
            'MA events without the label (keep MA)': int((ma & ~ok_ev).sum()),
            'mixed label: events': int((new_ev >= t - 1e-6).sum())}
    both = ok_ev & (ev.mag.to_numpy() >= 5 - 1e-6)
    d = lab_ev[both] - ev.mag.to_numpy()[both]
    summary['label - MA on MA>=5 events with the label'] = [round(float(d.mean()), 3), round(float(d.std()), 3), int(both.sum())]
    (out / 'relabel_summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
