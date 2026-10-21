"""Markdown tables from multistation.py JSONs.

  python tailrisk/multistation_table.py results/multistation_instance_s1.json [more.json ...]

For each file: event-level MAE (median action) of the top-tail events and of all events versus
the number of combined stations k, for every arm:rule, and the paired differences of the
factorized rule against the free mixture's best-available rules.
"""
import json
import sys
from pathlib import Path


def fd(v):
    if v is None:
        return 'n/a'
    b = '**' if (v['lo'] > 0 or v['hi'] < 0) else ''
    return f"{b}{v['mean']:+.3f} [{v['lo']:+.3f},{v['hi']:+.3f}]{b}"


def main():
    for path in sys.argv[1:]:
        r = json.loads(Path(path).read_text())
        ks = list(r['ks'])
        thr = r['thr']
        top = f'M>={thr[-1]:g}'
        mid = f'M>={thr[0]:g}'
        print(f'\n## {Path(path).stem}  (events with ≥ k usable stations; stations ordered by hypocentral distance; median action)\n')
        print('| k | ' + ' | '.join(ks) + ' |')
        print('|---|' + '---|' * len(ks))
        for sub in ('n_events', f'n_{mid}', f'n_{top}'):
            print(f'| {sub} | ' + ' | '.join(str(r['ks'][k][sub]) for k in ks) + ' |')
        for d in ('1s', '3s', '5s'):
            for sub, title in ((top, f'{top} events, event-level MAE'), (mid, f'{mid} events, event-level MAE'), ('all', 'all events, event-level MAE')):
                print(f'\n### {d[0]} s — {title}\n')
                print('| arm : rule | ' + ' | '.join(f'k={k}' for k in ks) + ' |')
                print('|---|' + '---|' * len(ks))
                for key, by_k in r['metrics'].items():
                    if not key.endswith(':median'):
                        continue
                    vals = [by_k[k][d][sub] for k in ks]
                    print(f'| {key[:-7]} | ' + ' | '.join('n/a' if v is None else f'{v:.3f}' for v in vals) + ' |')
            for ref_rule, ref_title in (('post_prod', 'posterior product (naive)'), ('hist_adj', 'histogram-adjusted product')):
                print(f'\n### {d[0]} s — paired differences vs the free mixture\'s {ref_title}, {top} events / all events\n')
                print('| arm : rule | ' + ' | '.join(f'k={k}' for k in ks) + ' |')
                print('|---|' + '---|' * len(ks))
                for key, refs in r['vs_ref'].items():
                    if not key.endswith(':median'):
                        continue
                    ref = f"{r['arms'][0]}:{ref_rule}:median"
                    if ref not in refs:
                        continue
                    by_k = refs[ref]
                    cells = []
                    for k in ks:
                        c = by_k.get(k, {}).get(d, {})
                        cells.append(fd(c.get(top)) + ' / ' + fd(c.get('all')))
                    print(f'| {key[:-7]} | ' + ' | '.join(cells) + ' |')

if __name__ == '__main__':
    main()
