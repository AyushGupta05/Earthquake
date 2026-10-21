"""Cross-seed summary of multistation.py JSONs (one JSON per seed, same dataset).

  python tailrisk/multistation_summary.py results/multistation_instance_s1.json results/multistation_instance_s2.json ...

For each deadline and subset (top tail, all events): event-level MAE per arm:rule at k = 1, 4
and all stations, as mean over seeds with the per-seed values; then, at k = all, the paired
difference of each arm:rule against the free mixture's histogram-adjusted product per seed
(bold = 95% CI excludes zero) and the number of seeds with the same sign.
"""
import json
import re
import sys
from pathlib import Path


def base(key):
    arm, rule, act = key.split(':')
    return re.sub(r'_s\d+$', '', arm) + ':' + rule + ':' + act


def fd(v):
    if v is None:
        return 'n/a'
    b = '**' if (v['lo'] > 0 or v['hi'] < 0) else ''
    return f"{b}{v['mean']:+.3f} [{v['lo']:+.3f},{v['hi']:+.3f}]{b}"


def main():
    reps = [json.loads(Path(p).read_text()) for p in sys.argv[1:]]
    thr = reps[0]['thr']
    top = f'M>={thr[-1]:g}'
    ks = [k for k in ('1', '4', 'all') if k in reps[0]['ks']]
    print(f'\n## {Path(sys.argv[1]).stem.rsplit("_s", 1)[0]} — {len(reps)} seeds; n events (seed 1): '
          + ', '.join(f'k={k}: {reps[0]["ks"][k]["n_events"]} ({reps[0]["ks"][k]["n_" + top]} {top})' for k in ks))
    keys = [k for k in reps[0]['metrics'] if k.endswith(':median')]
    for d in ('1s', '3s', '5s'):
        for sub in (top, 'all'):
            print(f'\n### {d[0]} s — {sub} events, event-level MAE (median action): mean over seeds [per seed]\n')
            print('| arm : rule | ' + ' | '.join(f'k={k}' for k in ks) + ' |')
            print('|---|' + '---|' * len(ks))
            for key in keys:
                cells = []
                for k in ks:
                    vals = []
                    for r in reps:
                        kk = next((x for x in r['metrics'] if base(x) == base(key)), None)
                        v = r['metrics'][kk][k][d][sub] if kk else None
                        vals.append(v)
                    fin = [v for v in vals if v is not None]
                    cells.append((f'{sum(fin) / len(fin):.3f} [' + ' '.join(f'{v:.3f}' for v in fin) + ']') if fin else 'n/a')
                print(f'| {base(key)[:-7]} | ' + ' | '.join(cells) + ' |')
        print(f'\n### {d[0]} s — k = all: Δ vs free mixture, histogram-adjusted product ({top} / all), per seed; same-sign count\n')
        print('| arm : rule | ' + ' | '.join(f'seed {i + 1}' for i in range(len(reps))) + f' | sign {top} | sign all |')
        print('|---|' + '---|' * (len(reps) + 2))
        for key in keys:
            cells, s_top, s_all = [], [], []
            for r in reps:
                kk = next((x for x in r['metrics'] if base(x) == base(key)), None)
                ref = next((x for x in r['vs_ref'].get(kk, {}) if x.endswith(':hist_adj:median')), None) if kk else None
                c = r['vs_ref'][kk][ref]['all'][d] if ref else {}
                cells.append(fd(c.get(top)) + ' / ' + fd(c.get('all')))
                if c.get(top): s_top.append(c[top]['mean'] < 0)
                if c.get('all'): s_all.append(c['all']['mean'] < 0)
            sg = lambda s: (f'{sum(s)}/{len(s)} neg' if s else 'ref')
            print(f'| {base(key)[:-7]} | ' + ' | '.join(cells) + f' | {sg(s_top)} | {sg(s_all)} |')


if __name__ == '__main__':
    main()
