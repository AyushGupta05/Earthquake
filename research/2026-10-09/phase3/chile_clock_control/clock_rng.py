"""Paired random streams for the fixed clock-only continuation.

Station masking and MA>4 smoothing follow the pinned port equations. Only their
random streams are separated; clock draws never consume augmentation/model RNG.
"""
import hashlib
import json

import torch


def stream_seed(seed, name):
    return int.from_bytes(hashlib.sha256(f'chile-clock-v1/{seed}/{name}'.encode()).digest()[:8], 'little') % (2**63 - 1)


def tensor_bytes(value):
    value = value.detach().cpu().contiguous()
    header = json.dumps([str(value.dtype), list(value.shape)], separators=(',', ':')).encode()
    return header + b'\0' + value.numpy().tobytes()


def state_digest(state):
    digest = hashlib.sha256()
    for name in sorted(state):
        digest.update(name.encode() + b'\0' + tensor_bytes(state[name]))
    return digest.hexdigest()


class Streams:
    NAMES = ('clock', 'station_count', 'station_rank', 'label')

    def __init__(self, seed, device):
        self.generators = {name: torch.Generator(device=device).manual_seed(stream_seed(seed, name)) for name in self.NAMES}

    def state_dict(self):
        return {name: gen.get_state() for name, gen in self.generators.items()}

    def cutoffs(self, count, device, arm):
        gen = self.generators['clock']
        if arm == 'source_uniform':
            samples = torch.randint(100, 3000, (count,), device=device, generator=gen)
            return (samples.double() + .5) / 100. - 5., samples
        if arm == 'discrete_1_3_5':
            values = torch.tensor([600, 800, 1000], device=device)
            samples = values[torch.randint(3, (count,), device=device, generator=gen)]
            return samples.double() / 100. - 5., samples
        raise ValueError('Unknown frozen clock arm')

    def augmentation(self, mask, targets):
        uniform = torch.rand(len(mask), device=mask.device, generator=self.generators['station_count'])
        rank = torch.rand(mask.shape, device=mask.device, generator=self.generators['station_rank'])
        noise = torch.randn(targets.shape, dtype=targets.dtype, device=targets.device, generator=self.generators['label'])
        return uniform, rank, noise


def apply_augmentation(waveforms, coords, mask, targets, cutoffs, draws, prepare_prefix):
    """Same source masking law from identical base randomness; prefix-only active."""
    uniform, scores, noise = draws
    if uniform.shape != (len(mask),) or scores.shape != mask.shape or noise.shape != targets.shape:
        raise ValueError('Augmentation draw shape mismatch')
    with torch.no_grad():
        _, active = prepare_prefix(waveforms, mask, cutoffs)
        active = active & coords.ne(0).any(-1)
        count = active.sum(-1)
        hidden_count = (uniform * count).long()
        ranks = scores.masked_fill(~active, float('inf')).argsort(-1).argsort(-1)
        result = mask & ~(active & (ranks < hidden_count[:, None]))
    labels = targets + noise * (targets - 4).clamp_min(0) * .05
    return result, labels


class Trace:
    FIELDS = ('event_order', 'station_order', 'station_count_draw', 'station_rank_draw', 'label_draw', 'model_rng', 'clock', 'final_mask')
    PAIRED = ('event_order', 'station_order', 'station_count_draw', 'station_rank_draw', 'label_draw', 'model_rng')

    def __init__(self):
        self.hashes = {name: hashlib.sha256() for name in self.FIELDS}
        self.batches = self.examples = 0
        self.batch_sizes = []
        self.clock_counts = [0] * 3000

    def tensor(self, key, tensor):
        self.hashes[key].update(tensor_bytes(tensor))

    def records(self, key, value):
        self.hashes[key].update(json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode() + b'\n')

    def result(self):
        return {'sha256': {key: h.hexdigest() for key, h in self.hashes.items()}, 'batches': self.batches,
                'examples': self.examples, 'batch_sizes': self.batch_sizes, 'clock_counts': self.clock_counts}


def assert_paired(left, right):
    for field in ('examples', 'batches', 'batch_sizes'):
        if left[field] != right[field]:
            raise ValueError('Paired draw budget changed: ' + field)
    for field in Trace.PAIRED:
        if left['sha256'][field] != right['sha256'][field]:
            raise ValueError('Clock perturbed a non-clock stream: ' + field)
