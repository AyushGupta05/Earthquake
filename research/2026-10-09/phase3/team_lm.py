"""Fresh PyTorch implementation of the documented TEAM-LM magnitude architecture.

Primary references (Muenchmeyer, Bindi, Leser, and Tilmann):
  Paper: https://doi.org/10.1093/gji/ggab139
  Software: https://doi.org/10.5880/GFZ.2.4.2021.003
  Source: https://github.com/yetinam/TEAM/tree/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903
The authors' GPLv3 models.py, util.py and chile_mag_noloc.json were inspected;
this file implements their architecture/equations anew rather than embedding
upstream source text. This is not a numerical TensorFlow equivalence claim.

Preserved source behavior: 3000-sample station input, all-channel peak scaling
and log-amplitude/100, valid convolutions, time-major flatten, 500-dimensional
station embeddings, coordinate sinusoid interleaving, interleaved Q/K/V heads,
absolute attention output under regular masking, six post-norm transformer
blocks, and five Gaussian components with ReLU means/scales plus 1e-4.

Explicit scope/deviations:
* Magnitude-only Chile configuration; no location/PGA head, borehole channels,
  rotation, dataset offsets, or train-time event resampling is implemented here.
* Strict-prefix demeaning excludes the first future sample. The original
  generator used :cutout+1 before zeroing at cutout; that causal boundary bug
  is intentionally corrected and must be shared by every compared model.
* Compact input is padded to 3000 AFTER cutoff/centering. Requesting observations
  later than the supplied cache is rejected, not silently filled as observed.
* The optional pool comparator shares the encoder, coordinates and density
  head but has fewer parameters. Its max excludes unavailable stations; this
  repairs a mask-handling inconsistency in the author's skip-transformer path.
* Initialization follows source initializer families, not TensorFlow RNG draws.
* log_prob returns the normalized Gaussian-mixture density. nll can add the
  source's 1e-6 density floor (default), evaluated stably by logaddexp. That
  floored training score is not the log of a normalized density over R.

Inputs: B x S x T x 3 velocity waveforms (ZNE, m/s), 100 Hz, first sample at
network-first-P minus five seconds; coordinates B x S x 3 are latitude and
longitude in degrees and depth in km, unchanged. Chile uses continuous
stations, including pre-arrival noise: no P-pick gating is inferred here.
Caller supplies station availability, station selection, and benchmark split.
"""

import math

import torch
from torch import nn
from torch.nn import functional as F


TRACE_SAMPLES = 3000
SAMPLE_RATE = 100
PRE_P_SECONDS = 5
EMBED_DIM = 500
CHILE_WAVELENGTHS = ((.01, 15.), (.01, 15.), (.01, 10.))


def prepare_prefix(waveforms, station_mask, cutoff_seconds, *, demean=True):
    """Strictly causal station prefix, zero padded to the source encoder shape.

    Returns (B,S,3000,3) and availability intersected with nonzero *observed*
    waveform support. Masked stations/future suffix may contain arbitrary values
    without influencing the result. A scalar or per-event B-vector cutoff is
    measured relative to the network's first P arrival, not each station's P.
    """
    if waveforms.ndim != 4 or waveforms.shape[-1] != 3:
        raise ValueError("Expected B x S x T x 3 waveforms")
    if not waveforms.is_floating_point():
        raise TypeError("Waveforms must be floating point")
    batch, stations, samples, _ = waveforms.shape
    if batch < 1 or stations < 1 or samples < 1 or samples > TRACE_SAMPLES:
        raise ValueError("Require nonempty examples/stations and 1 <= T <= 3000")
    if station_mask is None:
        station_mask = torch.ones((batch, stations), dtype=torch.bool, device=waveforms.device)
    if station_mask.shape != (batch, stations) or station_mask.dtype != torch.bool:
        raise ValueError("station_mask must be boolean B x S")
    station_mask = station_mask.to(waveforms.device)
    cutoff = torch.as_tensor(cutoff_seconds, device=waveforms.device, dtype=torch.float64)
    if cutoff.ndim == 0:
        cutoff = cutoff.expand(batch)
    if cutoff.shape != (batch,) or not torch.isfinite(cutoff).all():
        raise ValueError("cutoff_seconds must be finite scalar or B-vector")
    counts = ((cutoff + PRE_P_SECONDS) * SAMPLE_RATE).floor().long()
    if (counts < 0).any() or (counts > samples).any():
        raise ValueError("Requested observation extends outside supplied waveform samples")
    time_mask = torch.arange(samples, device=waveforms.device)[None, :] < counts[:, None]
    observed = time_mask[:, None, :, None] & station_mask[:, :, None, None]
    prefix = torch.where(observed, waveforms, torch.zeros((), device=waveforms.device, dtype=waveforms.dtype))
    if demean:
        mean = prefix.sum(2, keepdim=True) / counts.clamp_min(1).to(waveforms.dtype)[:, None, None, None]
        prefix = torch.where(observed, prefix - mean, torch.zeros_like(prefix))
    valid = station_mask & prefix.ne(0).any(dim=(2, 3))
    if samples < TRACE_SAMPLES:
        prefix = F.pad(prefix, (0, 0, 0, TRACE_SAMPLES - samples))
    return prefix, valid


def _glorot(module):
    if isinstance(module, (nn.Linear, nn.Conv1d, nn.Conv2d)):
        nn.init.xavier_uniform_(module.weight)
        if module.bias is not None:
            nn.init.zeros_(module.bias)


def _relu_mlp(dimensions):
    modules = []
    for left, right in zip(dimensions[:-1], dimensions[1:]):
        modules.extend((nn.Linear(left, right), nn.ReLU()))
    return nn.Sequential(*modules)


class StationEncoder(nn.Module):
    """Source-shaped, scale-retaining 3000 x 3 station encoder."""

    def __init__(self):
        super().__init__()
        self.front = nn.Sequential(
            nn.Conv2d(1, 8, (5, 1), stride=(5, 1)), nn.ReLU(),
            nn.Conv2d(8, 32, (16, 3), stride=(1, 3)), nn.ReLU(),
        )
        self.temporal = nn.Sequential(
            nn.Conv1d(32, 64, 16), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(64, 128, 16), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(128, 32, 8), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(32, 32, 8), nn.ReLU(),
            nn.Conv1d(32, 16, 4), nn.ReLU(),
        )
        self.projection = _relu_mlp((865, 500, 500, 500))
        self.apply(_glorot)

    @staticmethod
    def normalize_and_scale(x):
        peak = x.abs().amax((1, 2), keepdim=True)
        return x / (peak + 1e-8), (peak.flatten(1) + 1e-8).log() / 100.

    def forward(self, x):
        if x.ndim != 3 or x.shape[1:] != (TRACE_SAMPLES, 3):
            raise ValueError("StationEncoder requires N x 3000 x 3")
        normalized, amplitude = self.normalize_and_scale(x)
        features = self.front(normalized.unsqueeze(1)).squeeze(-1)
        features = self.temporal(features)
        if features.shape[1:] != (16, 54):
            raise RuntimeError("Source convolution shape drifted from 54 x 16")
        # Keras Flatten consumed time-major (N,54,16), not channel-major N,16,54.
        flattened = features.transpose(1, 2).contiguous().reshape(len(x), 864)
        return self.projection(torch.cat((flattened, amplitude), dim=1))


class CoordinateEmbedding(nn.Module):
    """Original latitude/longitude/depth frequency and channel interleaving."""

    def __init__(self, wavelengths=CHILE_WAVELENGTHS):
        super().__init__()
        if len(wavelengths) != 3 or any(low <= 0 or high < low for low, high in wavelengths):
            raise ValueError("Require three positive (min,max) coordinate wavelengths")
        for name, dimension, (low, high) in zip(("latitude", "longitude", "depth"), (100, 100, 50), wavelengths):
            frequency = (2 * math.pi / low) * (low / high)**(torch.arange(dimension, dtype=torch.float64) / dimension)
            self.register_buffer(name + "_frequency", frequency.float())

    def forward(self, coordinates, station_mask=None):
        if coordinates.ndim != 3 or coordinates.shape[-1] != 3:
            raise ValueError("Coordinates must be B x S x (lat,lon,depth)")
        latitude = coordinates[..., 0:1] * self.latitude_frequency
        longitude = coordinates[..., 1:2] * self.longitude_frequency
        depth = coordinates[..., 2:3] * self.depth_frequency
        # Groups of ten: two lat/lon frequency pairs and one depth pair.
        values = torch.stack((
            latitude.sin()[..., 0::2], latitude.cos()[..., 0::2],
            longitude.sin()[..., 0::2], longitude.cos()[..., 0::2], depth.sin(),
            latitude.sin()[..., 1::2], latitude.cos()[..., 1::2],
            longitude.sin()[..., 1::2], longitude.cos()[..., 1::2], depth.cos(),
        ), dim=-1).flatten(-2)
        if station_mask is not None:
            values = torch.where(station_mask[..., None], values, torch.zeros_like(values))
        return values


class InterleavedSelfAttention(nn.Module):
    """Preserve the source's (key_dim,heads) projection packing and abs output."""

    def __init__(self, dimension=EMBED_DIM, heads=10):
        super().__init__()
        if dimension % heads:
            raise ValueError("Attention dimension must be divisible by head count")
        self.dimension, self.heads, self.key_dim = dimension, heads, dimension // heads
        self.query = nn.Linear(dimension, dimension, bias=False)
        self.key = nn.Linear(dimension, dimension, bias=False)
        self.value = nn.Linear(dimension, dimension, bias=False)
        self.output = nn.Linear(dimension, dimension, bias=False)
        for parameter in self.parameters():
            nn.init.uniform_(parameter, -.02, .02)

    def forward(self, x, mask):
        batch, count, _ = x.shape
        def heads(projection):
            return projection(x).reshape(batch, count, self.key_dim, self.heads).permute(0, 3, 1, 2)
        q, k, v = heads(self.query), heads(self.key), heads(self.value)
        scores = (q @ k.transpose(-1, -2)) / math.sqrt(self.key_dim)
        # Event token is always valid, so at least one key survives. The source
        # subtracts a finite 1e6 mask penalty; preserve it under normalized inputs.
        scores = scores - (~mask[:, None, None, :]).to(scores.dtype) * 1e6
        attended = scores.softmax(-1) @ v
        merged = attended.permute(0, 2, 1, 3).contiguous().reshape(batch, count, self.dimension)
        projected = self.output(merged)
        return torch.where(mask[..., None], projected.abs(), torch.zeros_like(projected))


class TransformerBlock(nn.Module):
    def __init__(self):
        super().__init__()
        self.attention = InterleavedSelfAttention()
        self.attention_norm = nn.LayerNorm(500, eps=1e-5)
        self.feedforward = nn.Sequential(nn.Linear(500, 1000), nn.GELU(approximate="tanh"), nn.Linear(1000, 500))
        self.feedforward.apply(_glorot)
        self.feedforward_norm = nn.LayerNorm(500, eps=1e-5)

    def forward(self, x, mask):
        x = self.attention_norm(x + self.attention(x, mask))
        x = torch.where(mask[..., None], x, torch.zeros_like(x))
        update = torch.where(mask[..., None], self.feedforward(x), torch.zeros_like(x))
        x = self.feedforward_norm(x + update)
        return torch.where(mask[..., None], x, torch.zeros_like(x))


class GaussianMixtureHead(nn.Module):
    """Source magnitude MLP and five positive-mean Gaussian components."""

    def __init__(self):
        super().__init__()
        self.features = _relu_mlp((500, 150, 100, 50, 30, 10))
        self.weight_logits = nn.Linear(10, 5)
        self.mean_values = nn.Linear(10, 5)
        self.scale_values = nn.Linear(10, 5)
        self.apply(_glorot)
        nn.init.constant_(self.mean_values.bias, 1.8)
        nn.init.constant_(self.scale_values.bias, .2)

    def forward(self, event_embedding):
        features = self.features(event_embedding)
        logits = self.weight_logits(features)
        return {
            "logits": logits, "weights": logits.softmax(-1),
            "means": self.mean_values(features).relu(),
            "scales": self.scale_values(features).relu() + 1e-4,
        }


class TeamLM(nn.Module):
    """Magnitude-only TEAM-LM port, or a matched-input station-pooling control.

    ``model(x, coords, station_mask, cutoff_seconds=1.)`` returns B x 5 arrays
    logits/weights/means/scales. Prefix centering belongs here, not in the cache.
    ``forward_single_station`` is available for the source's encoder pretraining
    phase; its separate density head is discarded for event-model training.
    """

    def __init__(self, aggregation="transformer", transformer_layers=6):
        super().__init__()
        if aggregation not in ("transformer", "pool"):
            raise ValueError("aggregation must be transformer or pool")
        if transformer_layers < 1:
            raise ValueError("At least one transformer layer is required")
        self.aggregation = aggregation
        self.station_encoder = StationEncoder()
        self.station_norm = nn.LayerNorm(500, eps=1e-5)
        self.coordinates = CoordinateEmbedding()
        if aggregation == "transformer":
            self.event_token = nn.Parameter(torch.empty(500))
            nn.init.uniform_(self.event_token, -.02, .02)
            self.transformer = nn.ModuleList(TransformerBlock() for _ in range(transformer_layers))
            self.pool_mlp = None
        else:
            self.register_parameter("event_token", None)
            self.transformer = nn.ModuleList()
            self.pool_mlp = _relu_mlp((500, 500, 500))
            self.pool_mlp.apply(_glorot)
        self.magnitude_head = GaussianMixtureHead()
        self.single_station_head = GaussianMixtureHead()

    def forward(self, waveforms, coordinates, station_mask=None, cutoff_seconds=1.):
        if waveforms.ndim != 4:
            raise ValueError("Expected B x S x T x 3 waveforms")
        if coordinates.shape != (waveforms.shape[0], waveforms.shape[1], 3):
            raise ValueError("Coordinate/event/station axes must match waveforms")
        # The original Keras Input cast HDF float64 metadata to its float32
        # model dtype. Match the waveform/model dtype at this input boundary.
        coordinates = coordinates.to(device=waveforms.device, dtype=waveforms.dtype)
        prepared, mask = prepare_prefix(waveforms, station_mask, cutoff_seconds)
        # Source zero coordinates mark padding. Coordinates are never estimated
        # from future earthquake labels or waveform picks in this architecture.
        mask = mask & coordinates.ne(0).any(-1)
        safe_coords = torch.where(mask[..., None], coordinates, torch.zeros_like(coordinates))
        batch, stations = prepared.shape[:2]
        embedding = self.station_encoder(prepared.reshape(batch * stations, TRACE_SAMPLES, 3)).reshape(batch, stations, 500)
        embedding = self.station_norm(embedding)
        embedding = torch.where(mask[..., None], embedding, torch.zeros_like(embedding))
        embedding = embedding + self.coordinates(safe_coords, mask)
        if self.aggregation == "transformer":
            token = self.event_token.reshape(1, 1, 500).expand(batch, 1, -1)
            embedding = torch.cat((token, embedding), dim=1)
            mask = F.pad(mask, (1, 0), value=True)
            for block in self.transformer:
                embedding = block(embedding, mask)
            event = embedding[:, 0]
        else:
            station_features = self.pool_mlp(embedding)
            event = station_features.masked_fill(~mask[..., None], -torch.inf).amax(1)
            event = torch.where(mask.any(1, keepdim=True), event, torch.zeros_like(event))
        return self.magnitude_head(event)

    def forward_single_station(self, waveforms, cutoff_seconds=1., *, demean=False):
        """Source pretraining masks the suffix but does not demean by default."""
        if waveforms.ndim != 3:
            raise ValueError("Single-station pretraining expects B x T x 3")
        prepared, _ = prepare_prefix(waveforms[:, None], None, cutoff_seconds, demean=demean)
        return self.single_station_head(self.station_encoder(prepared[:, 0]))

    def parameter_counts(self):
        total = sum(p.numel() for p in self.parameters())
        temporary = sum(p.numel() for p in self.single_station_head.parameters())
        return {"total_including_pretraining_head": total,
                "event_model": total - temporary, "temporary_pretraining_head": temporary,
                "station_encoder": sum(p.numel() for p in self.station_encoder.parameters()),
                "transformer": sum(p.numel() for p in self.transformer.parameters()),
                "pool_mlp": 0 if self.pool_mlp is None else sum(p.numel() for p in self.pool_mlp.parameters())}


def mixture_log_prob(mixture, magnitudes):
    """Normalized mixture log density at one observed magnitude per event."""
    means, scales = mixture["means"], mixture["scales"]
    if magnitudes.shape == (len(means), 1):
        magnitudes = magnitudes[:, 0]
    if magnitudes.shape != (len(means),):
        raise ValueError("Require one target magnitude per event")
    standardized = (magnitudes[:, None] - means) / scales
    component = -.5 * standardized.square() - scales.log() - .5 * math.log(2 * math.pi)
    return torch.logsumexp(F.log_softmax(mixture["logits"], dim=-1) + component, dim=-1)


def mixture_nll(mixture, magnitudes, density_epsilon=1e-6, reduction="mean"):
    """Source-floored score by default; epsilon=0 gives the proper log score."""
    if density_epsilon < 0 or not math.isfinite(density_epsilon):
        raise ValueError("density_epsilon must be finite and nonnegative")
    log_density = mixture_log_prob(mixture, magnitudes)
    if density_epsilon:
        log_density = torch.logaddexp(log_density, log_density.new_tensor(math.log(density_epsilon)))
    loss = -log_density
    if reduction == "none":
        return loss
    if reduction == "mean":
        return loss.mean()
    if reduction == "sum":
        return loss.sum()
    raise ValueError("reduction must be none, mean, or sum")


def mixture_cdf(mixture, grid):
    """B x G continuous CDF for a one-dimensional grid (no magnitude clipping)."""
    if grid.ndim != 1:
        raise ValueError("CDF grid must be one dimensional")
    z = (grid[None, :, None] - mixture["means"][:, None]) / mixture["scales"][:, None]
    return (.5 * (1 + torch.erf(z / math.sqrt(2))) * mixture["weights"][:, None]).sum(-1)


def mixture_mean(mixture):
    return (mixture["weights"] * mixture["means"]).sum(-1)
