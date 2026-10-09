"""Render completed exploratory comparisons without selecting a best run."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    root=Path(__file__).resolve().parents[3]
    base=root/'results/2026-10-09/phase2'
    independent=base/'independent_weighted_drift0_seed20261009_a017bcb6dfbd_4eb61e46f5b9/metrics.json'
    compact=json.loads(independent.read_text())
    rows={'Original CNN':{},'CNN + CVaR residual':{},'Compact model, full data':compact}
    sources=[str(independent.relative_to(root))]
    for seconds in [1,3,5]:
        reference=base/f'feature_residual_{seconds}s/metrics.json'
        # These exact first runs are intentional, not a search over later seeds.
        names={1:'robust_residual_1s_15eebefc26b8_70f2a780847a',
               3:'robust_residual_3s_0ac3e09f99a1_d70c809a89b0',
               5:'robust_residual_5s_f5a608c9ce33_155218402380'}
        robust=base/names[seconds]/'metrics.json'
        rows['Original CNN'][str(seconds)]=json.loads(reference.read_text())['raw_mean']
        rows['CNN + CVaR residual'][str(seconds)]=json.loads(robust.read_text())['beta15_cvar0.1']
        sources.extend([str(reference.relative_to(root)),str(robust.relative_to(root))])
    fig,axes=plt.subplots(2,2,figsize=(10,7))
    colors=['#7A7A7A','#D47920','#087F8C']
    for ax,(key,title) in zip(axes.flat,[('mae','Mean absolute error'),('medae','Median absolute error'),
                                       ('m4_mae','M ≥ 4 mean absolute error'),('cvar95','Worst 5% error average')]):
        for (label,values),color in zip(rows.items(),colors):
            ys=[values[str(t)][key] for t in [1,3,5]]
            ax.plot([1,3,5],ys,marker='o',lw=2,color=color,label=label)
            if label=='Compact model, full data':
                for t,y in zip([1,3,5],ys):
                    ax.annotate(f'{y:.3f}',(t,y),xytext=(0,-14),textcoords='offset points',
                                ha='center',fontsize=9,color=color)
        ax.set_title(title,loc='left',fontsize=12)
        ax.set_xticks([1,3,5]); ax.set_xlabel('Seconds after station P arrival')
        ax.set_ylabel('Magnitude units'); ax.grid(alpha=.18)
        ax.spines[['top','right']].set_visible(False)
        ax.margins(x=.12,y=.25)
    fig.suptitle('Exploratory INSTANCE validation: a stronger baseline',x=.06,ha='left',fontsize=16)
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.53,.935),ncol=3,frameon=False)
    fig.text(.06,.025,'3,711 validation events; 13 M ≥ 4; one seed. Reused validation, not independent confirmation.\n'
             'CVaR setting highlighted after the sweep. No external-benchmark or novelty claim.',fontsize=9,color='#444444')
    fig.tight_layout(rect=[.025,.08,.99,.89])
    out=base/'figures'; out.mkdir(exist_ok=True)
    fig.savefig(out/'exploratory_comparison.png',dpi=180)
    fig.savefig(out/'exploratory_comparison.pdf')
    (out/'sources.json').write_text(json.dumps({'sources':sources,'values':rows},indent=2)+'\n')


if __name__=='__main__':
    main()
