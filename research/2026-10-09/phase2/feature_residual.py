"""Matched 1/3/5-second waveform-evidence residual distribution experiments.

All fits use training events only. Existing validation is reused exploratory
material. Five event folds separate each decision selection from its evaluation.
Published physical-feature fusion motivates controls; novelty is not asserted.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import time

import h5py
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_artifacts import create_run

PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARENT))
from audit_and_export import EarthquakeCNN, sha256, require_checkpoint_preprocessing
from distribution_experiment import event_folds, metrics, median, safe_choice
from frozen_head_pilot import choose_rows

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'results/2026-10-09/phase2'


def prefix_features(x):
    """Dimensionless and log-amplitude summaries of ONLY the provided prefix.

    Inputs retain the original training global scaling. These are waveform
    descriptors, not physical displacement/velocity without response removal.
    Temporal demeaning and FFT use only the observed prefix.
    """
    x = x - x.mean(-1, keepdim=True)
    eps = 1e-12
    rms = x.square().mean(-1).add(eps).sqrt()
    peak = x.abs().amax(-1).add(eps)
    amplitude = torch.cat([rms.log10(), peak.log10(),
                           x.abs().mean(-1).add(eps).log10()], 1)
    quarters = torch.stack([q.square().mean(-1).add(eps).sqrt()
                            for q in torch.tensor_split(x, 4, dim=-1)], -1)
    growth = (quarters / rms[..., None]).clamp(max=10).flatten(1)
    frequency = torch.fft.rfftfreq(x.shape[-1], d=.01, device=x.device)
    power = torch.fft.rfft(x, dim=-1).abs().square()
    power = power / power.sum(-1, keepdim=True).clamp_min(eps)
    bands = torch.stack([power[..., (frequency >= low) & (frequency < high)].sum(-1)
                         for low, high in [(0, 2), (2, 5), (5, 10), (10, 20), (20, 51)]], -1).flatten(1)
    centroid = (power * frequency / 50).sum(-1)
    entropy = -(power * power.clamp_min(eps).log()).sum(-1) / np.log(power.shape[-1])
    crossings = (x[..., :-1] * x[..., 1:] < 0).float().mean(-1)
    roughness = ((x[..., 1:] - x[..., :-1]).square().mean(-1).sqrt() / rms).clamp(max=10)
    crest = (peak / rms).clamp(max=30)
    return torch.cat([amplitude, growth, bands, centroid, entropy, crossings, roughness, crest], 1)


def population_weights(meta, rows):
    """Inverse sampling weights recover the recording population in expectation."""
    counts = meta.groupby('source_id').size()
    selected_counts = meta.iloc[rows].groupby('source_id').size()
    ids = meta.source_id.iloc[rows]
    weight = (ids.map(counts) / ids.map(selected_counts)).to_numpy(float)
    return weight / weight.mean()


def extract(seconds, device):
    audit = json.loads((ROOT/'results/2026-10-09/audit.json').read_text())
    info = audit['windows'][str(seconds)]
    require_checkpoint_preprocessing({info['preprocessing']})
    meta = pd.read_csv(ROOT/'train_full_metadata.csv', usecols=['source_id','source_magnitude'])
    if sha256(ROOT/'train_full_metadata.csv') != audit['train']['metadata_sha256']:
        raise ValueError('Training metadata changed')
    if sha256(ROOT/'val_metadata.csv') != audit['val']['metadata_sha256']:
        raise ValueError('Validation metadata changed')
    selected = choose_rows(meta)
    # Preserve all rare-event recordings; population weights correct unequal sampling.
    rows = np.union1d(selected, np.flatnonzero(meta.source_magnitude.to_numpy() >= 4))
    checkpoint_path = ROOT/'bayesianprior/data'/info['checkpoint']
    if sha256(checkpoint_path) != info['checkpoint_sha256']:
        raise ValueError('Checkpoint changed')
    model = EarthquakeCNN().to(device)
    model.load_state_dict(torch.load(checkpoint_path, map_location='cpu', weights_only=True)['model_state_dict'])
    model.eval()
    baseline = np.load(ROOT/f'results/2026-10-09/validation_{seconds}s.npz', allow_pickle=False)
    if set(meta.source_id.astype(str)) & set(baseline['event_ids']):
        raise ValueError('Event overlap')
    result = {}
    with h5py.File(Path('/data')/info['cache'], 'r') as h:
        for split, indices in [('train', rows), ('val', np.arange(len(baseline['targets'])))]:
            ds = h[f'{split}/waveforms']
            if ds.shape[1:] != (3, seconds*100):
                raise ValueError('Incorrect causal duration')
            hidden, physical, logits = [], [], []
            with torch.inference_mode():
                for start in range(0, len(indices), 256):
                    ix = indices[start:start+256]
                    x = torch.from_numpy(ds[ix]).to(device)
                    z = model.classifier[:-1](model.global_pool(model.features(x)))
                    hidden.append(z.cpu().numpy())
                    physical.append(prefix_features(x).cpu().numpy())
                    logits.append(model.classifier[-1](z).cpu().numpy())
            result[split+'_hidden'] = np.concatenate(hidden)
            result[split+'_physical'] = np.concatenate(physical)
            result[split+'_logits'] = np.concatenate(logits)
    if not np.allclose(result['val_logits'], baseline['logits'], atol=2e-3, rtol=2e-4):
        raise ValueError('Reproduced logits disagree with duration-audited reference')
    result.update(train_y=meta.source_magnitude.to_numpy()[rows].astype('float32'),
                  train_ids=meta.source_id.to_numpy(dtype=str)[rows],
                  weights=population_weights(meta, rows).astype('float32'),
                  val_y=baseline['targets'], val_ids=baseline['event_ids'], centers=baseline['centers'])
    return result


class ResidualDistribution(nn.Module):
    def __init__(self, n_features):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_features, 128), nn.SiLU(), nn.Dropout(.1),
                                 nn.Linear(128, 64), nn.SiLU(), nn.Linear(64, 66))
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, features, original_logits):
        # Zero initial correction; bounded log-odds movement discourages explosions.
        return original_logits + 5 * torch.tanh(self.net(features) / 5)


def inputs(data, family):
    arrays = []
    for split in ['train', 'val']:
        logits = data[split+'_logits']
        z = logits - logits.mean(1, keepdims=True)
        if family == 'evidence':
            z = np.concatenate([z, data[split+'_hidden'], data[split+'_physical']], 1)
        arrays.append(z.astype('float32'))
    # Training-only normalizer, even when validation extremes are outside this range.
    mean, std = arrays[0].mean(0), np.maximum(arrays[0].std(0), 1e-5)
    return [np.clip((a-mean)/std, -15, 15) for a in arrays], mean, std


def fit(data, family, beta, anchor, device, epochs, seed):
    torch.manual_seed(seed)
    arrays, feature_mean, feature_std = inputs(data, family)
    train_x, val_x = [torch.as_tensor(a, device=device) for a in arrays]
    original = torch.as_tensor(data['train_logits'], device=device)
    val_original = torch.as_tensor(data['val_logits'], device=device)
    y = torch.as_tensor(data['train_y'], device=device)
    w = torch.as_tensor(data['weights'], device=device)
    centers = torch.as_tensor(data['centers'], dtype=torch.float32, device=device)
    labels = (y/.1 + 1e-5).floor().long().clamp(0,65)
    original_mean = original.softmax(1) @ centers
    model = ResidualDistribution(train_x.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
    losses = []
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(y), device=device)
        total = 0.
        for ix in order.split(2048):
            logits = model(train_x[ix], original[ix])
            pred = logits.softmax(1) @ centers
            # This is an explicitly decision-oriented objective, not a claim of calibration.
            magnitude_loss = F.huber_loss(pred, y[ix], reduction='none', delta=.5)
            emphasis = 1 + beta * (y[ix]-3.5).clamp_min(0)
            ce = F.cross_entropy(logits, labels[ix], reduction='none')
            keep = (pred-original_mean[ix]).square()
            loss = (w[ix] * (emphasis*magnitude_loss + .075*ce + anchor*keep)).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.)
            optimizer.step()
            total += loss.item()*len(ix)
        losses.append(total/len(y))
    model.eval()
    with torch.inference_mode():
        p = torch.cat([model(val_x[i:i+2048], val_original[i:i+2048]).double().softmax(1).cpu()
                       for i in range(0,len(val_x),2048)]).numpy()
    state = dict(model=model.state_dict(), feature_mean=torch.tensor(feature_mean),
                 feature_std=torch.tensor(feature_std), family=family, beta=beta, anchor=anchor,
                 seed=seed, epochs=epochs)
    return p, state, losses


def select_crossfit(y, ids, raw, candidates):
    folds = event_folds(y, ids)
    result = raw.copy()
    choices = []
    for k in range(5):
        evaluation = folds == k
        calibration = ~evaluation
        name = safe_choice(y[calibration], ids[calibration], raw[calibration],
                           {name: p[calibration] for name,p in candidates.items()})
        if name != 'raw_fallback':
            result[evaluation] = candidates[name][evaluation]
        choices.append({'fold':k, 'choice':name})
    return result, choices, folds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=int, choices=[1,3,5], required=True)
    ap.add_argument('--epochs', type=int, default=15)
    ap.add_argument('--seed', type=int, default=20261009)
    args = ap.parse_args()
    torch.set_num_threads(2)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    here = Path(__file__).resolve().parent
    destination = create_run(OUT, f'feature_residual_{args.seconds}s', vars(args),
        list(here.glob('*.py')) + list(here.parent.glob('*.py')) +
        [ROOT/'results/2026-10-09/audit.json'])
    print('RUN_DIRECTORY', destination, flush=True)
    started = time.monotonic()
    data = extract(args.seconds, device)
    y, ids, c = data['val_y'], data['val_ids'], data['centers']
    raw_p = torch.from_numpy(data['val_logits']).double().softmax(1).numpy()
    raw = raw_p @ c
    results = {'raw_mean':metrics(y,raw,ids,raw_p,c)}
    predictions = {'raw_mean':raw}
    history = {}
    candidates = {}
    # Fixed sweep specified before inspecting any phase-2 result.
    for family in ['posterior','evidence']:
        for beta, anchor in [(0.,0.),(5.,0.),(15.,0.),(5.,.25)]:
            name = f'{family}_beta{beta:g}_anchor{anchor:g}'
            p, state, losses = fit(data,family,beta,anchor,device,args.epochs,args.seed)
            pred = p @ c
            results[name] = metrics(y,pred,ids,p,c)
            predictions[name] = pred
            history[name] = losses
            torch.save(state,destination/f'{name}.pth')
            # All families have the same bounded blend policy search.
            for blend in [.25,.5,1.]:
                candidates[f'{name}_blend{blend:g}'] = raw + blend*(pred-raw)
            print(args.seconds,name,{k:results[name][k] for k in ['mae','medae','m4_mae','m4_event_macro_mae','cvar95','fp4']},flush=True)
    selected, choices, folds = select_crossfit(y,ids,raw,candidates)
    predictions['selected'] = selected
    results['selected'] = metrics(y,selected,ids)
    run = dict(seconds=args.seconds, epochs=args.epochs, seed=args.seed,
               train_records=len(data['train_y']), train_events=len(np.unique(data['train_ids'])),
               wall_seconds=time.monotonic()-started, validation_status='Reused exploratory validation',
               objective_status='Weighted Huber + CE + optional anchor; no posterior-calibration guarantee')
    for filename, obj in [('metrics.json',results),('choices.json',choices),('history.json',history),('run.json',run)]:
        (destination/filename).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    np.savez_compressed(destination/'predictions.npz', targets=y,event_ids=ids,fold=folds,**predictions)
    print('SELECTED',args.seconds,results['selected'],run,flush=True)


if __name__ == '__main__':
    main()
