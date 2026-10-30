# Relabelled Northern-Chile caches (label-construct check, AUDIT_2026-10-30.md M1)

Built 30 Oct 2026 with `tailrisk/chile_relabel.py`. The original cache was not touched. Nothing
has been trained on these caches yet.

| cache | label | events / records with the label |
|---|---|---|
| `/mnt/scratch/chile_relabel_mext/` | `M_EXT` (external catalogue magnitude) | 73 / 669 |
| `/mnt/scratch/chile_relabel_mwsippl/` | `MW_SIPPL` (moment magnitude) | 360 / 3,452 |

The original cache has 67,284 events and 505,666 records, all labelled `MA`.

## Layout

Each directory holds:
- `meta.npz`: a copy of the Chile `meta.npz` with these changes:
  - `mag` = the new label where the event has it, else the original MA;
  - `mag_type` = `M_EXT` / `MW_SIPPL` or `MA` accordingly;
  - `label_ok` (bool) marks records whose `mag` is the new label;
  - `mag_MA` keeps the original.
- `events.csv`, rewritten the same way.
- Symlinks to the original `wave16.npy`, `scale.npy` and `folds.json`.
- `relabel_summary.json` with the counts below.

`fold` and `cluster` are unchanged, so the CV splits are the same as for the MA arms. The GK
clusters were built from MA magnitudes. All other `meta.npz` arrays are identical to the original.

## Why the records without the label are flagged, not dropped

The independent labels exist only for the larger events. M_EXT covers 73 events, all with
M_EXT ≥ 4.86. MW_SIPPL covers 360 events, almost all with MA ≥ 3. Dropping the unlabelled records
would leave 669 or 3,452 training records, too few to train on.

Because `wave16.npy` is shared by symlink and row-aligned with `meta.npz`, rows cannot be dropped
without copying the waveforms anyway. So every record keeps a label: the new one where it exists,
MA otherwise. Training therefore sees **a mixed label**: the independent magnitude for the large
events and MA for the bulk. Score the tail on relabelled events only:

    TAILWORK_DIR=/mnt/scratch/chile_relabel_mext TAILWORK_MAXMAG=9.5 \
      python tailrisk/robust_tail.py --pairs eqdgr_nll:mix_nll --thr 5,6 \
      --tail-mask meta:label_ok --out tailrisk/results/robust_chile_mext.json

## Counts

| | M_EXT ≥ 5 | M_EXT ≥ 6 | MW_SIPPL ≥ 5 | MW_SIPPL ≥ 6 |
|---|---|---|---|---|
| events with the label at or above t | 65 | 9 | 44 | 6 |
| their records | 589 | 81 | 432 | 63 |
| their GK clusters | 29 | 7 | 21 | 5 |
| MA ≥ t events lacking the label (they keep MA) | 12 of 67 | 1 of 12 | 17 of 67 | 5 of 12 |
| events at or above t in the mixed label | 77 | 10 | 61 | 11 |

At ≥ 4: 73 M_EXT events (669 records, 31 clusters) and 341 MW_SIPPL events (3,283 records,
109 clusters).

On MA ≥ 5 events that have both labels:
- M_EXT − MA = −.065 ± .133 (55 events);
- MW_SIPPL − MA = −.106 ± .119 (50 events).

So the new labels sit about 0.1 below MA at the top. The mixed label therefore steps down where
the new label takes over.

## Caveats

1. Tail events without the new label stay in training with their MA label: 12 events for
   M_EXT, 17 for MW_SIPPL. That includes the largest event: MA 8.05, M_EXT 7.72, no MW_SIPPL.
   These events are excluded from the tail score by `--tail-mask meta:label_ok`.
2. With 6–9 events at ≥ 6, the M≥6 results will be very noisy. The ≥ 5 tail (44–65 events in
   21–29 clusters) is the more informative test.
3. `ML` covers every event and is on the 0.1 grid. A fully relabelled ML cache is possible with
   the same script after a one-line change, but ML is itself an amplitude magnitude.
