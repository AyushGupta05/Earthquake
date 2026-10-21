"""Cross-seed summary of fusion_timeline.py JSONs (one per seed, same dataset).

  python tailrisk/timeline_summary.py results/fusion_timeline_instance_s1.json results/fusion_timeline_instance_s2.json ...

Event-level MAE (median action) of the top-tail events and of all events versus time since the
first P arrival, mean over seeds with per-seed values in brackets, for every arm:rule.
"""
import json
import re
import sys
from pathlib import Path


def base(key):
    arm, rule, act = key.split(':')
    return re.sub(r'_s\d+$', '', arm) + ':' + rule + ':' + act


def main():
    reps = [json.loads(Path(p).read_text()) for p in sys.argv[1:]]
    r0 = reps[0]
    top = f"M>={r0['thr'][-1]:g}"
    times = r0['times']
    print(f"\n## {Path(sys.argv[1]).stem.rsplit('_s', 1)[0]} — {len(reps)} seed(s); {r0['n_events']} events, {r0['n_tail'][top]} {top}; "
          f"timing: {r0.get('timing', 'proxy')} (V_P = {r0['v_p']} km/s); median stations with data: "
          + ', '.join(f"T={T}s: {r0['stations_used'][str(T)]['median_k']:.0f}" for T in times))
    keys = [k for k in r0['metrics'] if k.endswith(':median')]
    for sub, title in ((top, f'{top} events'), ('all', 'all events')):
        print(f'\n### {title}, event-level MAE (median action) vs seconds after the first P: mean over seeds [per seed]\n')
        print('| arm : rule | ' + ' | '.join(f'T={T}' for T in times) + ' |')
        print('|---|' + '---|' * len(times))
        for key in keys:
            cells = []
            for T in times:
                vals = []
                for r in reps:
                    kk = next((x for x in r['metrics'] if base(x) == base(key)), None)
                    v = r['metrics'][kk][str(T)][sub] if kk else None
                    if v is not None:
                        vals.append(v)
                cells.append((f'{sum(vals) / len(vals):.3f}' + (' [' + ' '.join(f'{v:.3f}' for v in vals) + ']' if len(vals) > 1 else '')) if vals else 'n/a')
            print(f'| {base(key)[:-7]} | ' + ' | '.join(cells) + ' |')
    print(f'\n### {top} events: Δ vs the free mixture\'s histogram-adjusted product (seed 1), bold = 95% CI excludes zero\n')
    print('| arm : rule | ' + ' | '.join(f'T={T}' for T in times) + ' |')
    print('|---|' + '---|' * len(times))
    for key, refs in r0['vs_ref'].items():
        if not key.endswith(':median'):
            continue
        ref = next((x for x in refs if x.endswith(':hist_adj:median')), None)
        if ref is None:
            continue
        cells = []
        for T in times:
            v = refs[ref].get(str(T), {}).get(top)
            if v is None:
                cells.append('n/a')
            else:
                b = '**' if (v['lo'] > 0 or v['hi'] < 0) else ''
                cells.append(f"{b}{v['mean']:+.3f} [{v['lo']:+.3f},{v['hi']:+.3f}]{b}")
        print(f'| {key[:-7]} | ' + ' | '.join(cells) + ' |')


if __name__ == '__main__':
    main()
