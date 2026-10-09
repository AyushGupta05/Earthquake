"""INSTANCE station-only feature lookup; no waveform or catalogue quantities.

The StationXML archive is read in memory, never extracted. Exact network,
station, location, component and epoch matches are required. Ambiguous epochs
remain unusable rather than being resolved by file order or a nearest date.
"""
import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile
import xml.etree.ElementTree as ET

NS = {'s': 'http://www.fdsn.org/xml/station/1'}
COMPONENTS = 'ENZ'
FAMILIES = ('HH', 'EH', 'HN', 'HL', 'EN')
STATIC_COLUMNS = ('station_latitude_deg', 'station_longitude_deg',
                  'station_elevation_m', 'station_vs_30_mps')


def numeric(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def utc_seconds(value):
    if not value:
        return None
    normalized = value.strip().replace('Z', '+00:00')
    # Python 3.10 accepts fractional seconds with 3 or 6 digits, while INSTANCE
    # often has 2. Normalize precision without changing the represented time.
    normalized = re.sub(r'\.(\d+)(?=[+-]|$)',
                        lambda m: '.' + m.group(1).ljust(6, '0')[:6], normalized)
    parsed = datetime.fromisoformat(normalized)
    # StationXML dates in this inventory omit the UTC suffix; FDSN times are UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def field(node, path):
    text = node.findtext(path, None, NS)
    return text.strip() if text is not None else None


def normalize_units(value):
    raw = (value or '').upper().replace(' ', '')
    if raw == 'M/S':
        return 'm/s'
    if raw in ('M/S**2', 'M/S^2', 'M/S/S'):
        return 'm/s^2'
    return 'unknown'


def location_code(row):
    """Repair only evidenced CSV numeric coercion, never guess a location.

    The local split CSVs encoded nonblank locations as 1.0/2.0. The original
    trace identifier retains the exact SCNL suffix; require its corroboration.
    Event-ID text is never interpreted or passed to model_features.
    """
    raw = row.get('station_location_code', '').strip()
    if not re.fullmatch(r'\d{1,2}\.0+', raw):
        return raw, False
    canonical = f'{int(float(raw)):02d}'
    pieces = row.get('trace_name', '').rsplit('.', 4)
    expected = [row.get('station_network_code', '').strip(),
                row.get('station_code', '').strip(), canonical,
                row.get('station_channels', '').strip()]
    if len(pieces) == 5 and pieces[1:] == expected:
        return canonical, True
    return raw, False


@dataclass(frozen=True)
class Epoch:
    network: str
    station: str
    location: str
    channel: str
    start: float
    end: float
    sensitivity: float
    sensitivity_frequency_hz: float
    input_units: str
    output_units: str
    sample_rate_hz: float
    azimuth_deg: float
    dip_deg: float
    latitude_deg: float
    longitude_deg: float
    elevation_m: float
    sensor: str
    source_member: str

    @property
    def key(self):
        return self.network, self.station, self.location, self.channel

    @property
    def usable(self):
        return (self.sensitivity is not None and self.sensitivity > 0
                and self.sensitivity_frequency_hz is not None
                and self.sensitivity_frequency_hz >= 0
                and normalize_units(self.input_units) != 'unknown'
                and (self.output_units or '').upper() == 'COUNTS')


def parse_xml(root, member):
    result = []
    for network in root.findall('s:Network', NS):
        for station in network.findall('s:Station', NS):
            for channel in station.findall('s:Channel', NS):
                ancestors = (network, station, channel)
                starts = [utc_seconds(n.get('startDate')) for n in ancestors]
                ends = [utc_seconds(n.get('endDate')) for n in ancestors]
                start = max([v for v in starts if v is not None], default=-math.inf)
                end = min([v for v in ends if v is not None], default=math.inf)
                # Some official records have disjoint station/channel epochs.
                # Preserve them for audit; an empty interval can never match.
                prefix = 's:Response/s:InstrumentSensitivity/'
                result.append(Epoch(
                    network.get('code', ''), station.get('code', ''),
                    channel.get('locationCode', '').strip(), channel.get('code', ''),
                    start, end, numeric(field(channel, prefix + 's:Value')),
                    numeric(field(channel, prefix + 's:Frequency')),
                    field(channel, prefix + 's:InputUnits/s:Name'),
                    field(channel, prefix + 's:OutputUnits/s:Name'),
                    numeric(field(channel, 's:SampleRate')),
                    numeric(field(channel, 's:Azimuth')), numeric(field(channel, 's:Dip')),
                    numeric(field(channel, 's:Latitude')), numeric(field(channel, 's:Longitude')),
                    numeric(field(channel, 's:Elevation')), field(channel, 's:Sensor/s:Description'),
                    member,
                ))
    return result


class Inventory:
    def __init__(self, epochs):
        self.epochs = epochs
        self.index = defaultdict(list)
        for epoch in epochs:
            self.index[epoch.key].append(epoch)

    @classmethod
    def from_archive(cls, path):
        epochs = []
        with tarfile.open(path, 'r:gz') as archive:
            for member in archive:
                if member.isfile() and member.name.endswith('.xml'):
                    with archive.extractfile(member) as stream:
                        epochs.extend(parse_xml(ET.parse(stream).getroot(), member.name))
        if not epochs:
            raise ValueError('No StationXML channel epochs found')
        return cls(epochs)

    def lookup(self, key, timestamp):
        candidates = self.index.get(key, [])
        if not candidates:
            return 'no_channel_key', None, 0
        # Inclusive endpoints are conservative: an exact touching boundary is
        # ambiguous, rather than silently assigned to one instrument response.
        matches = [e for e in candidates if e.start <= timestamp <= e.end]
        if not matches:
            return 'outside_epoch', None, 0
        if len(matches) != 1:
            return 'multiple_epochs', None, len(matches)
        epoch = matches[0]
        return ('matched' if epoch.usable else 'invalid_response'), epoch, 1

    def join(self, row):
        result = {'split': row.get('split'), 'row_index': row.get('row_index'),
                  'trace_name': row.get('trace_name'), 'channels': {}}
        result.update({key: numeric(row.get(key)) for key in STATIC_COLUMNS})
        if result['station_vs_30_mps'] is not None and result['station_vs_30_mps'] <= 0:
            result['station_vs_30_mps'] = None
        result['vs30_provenance'] = row.get('station_vs_30_detail', '')
        try:
            timestamp = utc_seconds(row.get('trace_start_time'))
        except (ValueError, OverflowError):
            timestamp = None
        family = row.get('station_channels', '').strip()
        result['channel_family'] = family
        location, repaired = location_code(row)
        result['location_numeric_encoding_repaired'] = repaired
        for component in COMPONENTS:
            key = (row.get('station_network_code', '').strip(),
                   row.get('station_code', '').strip(),
                   location, family + component)
            if timestamp is None:
                status, epoch, count = 'invalid_timestamp', None, 0
            elif family not in FAMILIES:
                status, epoch, count = 'unsupported_family', None, 0
            else:
                status, epoch, count = self.lookup(key, timestamp)
            item = {'status': status, 'n_matching_epochs': count, 'key': '.'.join(key)}
            if epoch is not None:
                item.update({
                    'sensitivity': epoch.sensitivity,
                    'log10_sensitivity': math.log10(epoch.sensitivity) if epoch.usable else None,
                    'sensitivity_frequency_hz': epoch.sensitivity_frequency_hz,
                    'input_units': normalize_units(epoch.input_units),
                    'native_sample_rate_hz': epoch.sample_rate_hz,
                    'azimuth_deg': epoch.azimuth_deg, 'dip_deg': epoch.dip_deg,
                    'inventory_elevation_m': epoch.elevation_m,
                    'sensor': epoch.sensor, 'source_member': epoch.source_member,
                    'epoch_ends_within_120s': math.isfinite(epoch.end) and epoch.end < timestamp + 120,
                })
            result['channels'][component] = item
        statuses = [c['status'] for c in result['channels'].values()]
        result['usable_all_components'] = all(s == 'matched' for s in statuses)
        return result


def sensitivity_convert_prefix(prefix, channel, available_samples):
    """Approximate native-unit conversion of a supplied count prefix only.

    No filtering, integration, detrending, calibration fitting or response
    deconvolution is performed. Call separately for E/N/Z in known array order.
    """
    if channel.get('status') != 'matched':
        raise ValueError('An unambiguous usable epoch is required')
    if not isinstance(available_samples, int) or available_samples < 0:
        raise ValueError('available_samples must be a nonnegative integer')
    if available_samples > len(prefix):
        raise ValueError('Requested samples are not available')
    gain = channel['sensitivity']
    if numeric(gain) is None or gain <= 0:
        raise ValueError('Invalid instrument sensitivity')
    return [float(x) / gain for x in prefix[:available_samples]]


def model_features(joined):
    """Explicit numeric allowlist; excludes identifiers, time and audit flags.

    Fit any centering/scaling on training rows only. These are static station
    descriptors, not a claim that INSTANCE's waveform preprocessing is causal.
    """
    result = {f'family_{f}': float(joined['channel_family'] == f) for f in FAMILIES}
    result['family_unknown'] = float(joined['channel_family'] not in FAMILIES)
    for key in ('station_elevation_m', 'station_vs_30_mps'):
        value = joined.get(key)
        result[key] = 0.0 if value is None else value
        result[key + '_missing'] = float(value is None)
    for name, channel in joined['channels'].items():
        matched = channel['status'] == 'matched'
        result[f'{name}_response_missing'] = float(not matched)
        result[f'{name}_log10_sensitivity'] = channel['log10_sensitivity'] if matched else 0.0
        for unit, label in [('m/s', 'velocity'), ('m/s^2', 'acceleration')]:
            result[f'{name}_{label}'] = float(matched and channel.get('input_units') == unit)
        for field_name in ('sensitivity_frequency_hz', 'native_sample_rate_hz'):
            value = channel.get(field_name) if matched else None
            valid = value is not None and value >= 0
            result[f'{name}_log1p_{field_name}'] = math.log1p(value) if valid else 0.0
            result[f'{name}_{field_name}_missing'] = float(not valid)
    return result


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit(inventory, path):
    stats = defaultdict(lambda: {'records': 0, 'all_components_matched': 0,
        'any_unknown_or_outside_epoch': 0, 'any_multiple_epochs': 0,
        'any_invalid_response': 0, 'any_invalid_timestamp': 0, 'any_unsupported_family': 0,
        'channel_status': Counter(), 'family': Counter(),
        'units': Counter(), 'static_missing': Counter(), 'vs30_provenance': Counter(),
        'boundary_records': 0, 'elevation_mismatch_gt1m': 0,
        'location_numeric_encoding_repaired': 0})
    examples, fixture_rows = {}, []
    with gzip.open(path, 'rt', newline='') as stream:
        for row in csv.DictReader(stream):
            if row['split'] not in ('train', 'val'):
                raise ValueError('Only training and validation are authorized')
            joined = inventory.join(row)
            s = stats[row['split']]
            s['records'] += 1
            s['location_numeric_encoding_repaired'] += int(joined['location_numeric_encoding_repaired'])
            s['family'][joined['channel_family']] += 1
            channels = list(joined['channels'].values())
            statuses = [c['status'] for c in channels]
            s['all_components_matched'] += int(joined['usable_all_components'])
            s['any_unknown_or_outside_epoch'] += int(any(c in ('no_channel_key', 'outside_epoch') for c in statuses))
            s['any_multiple_epochs'] += int('multiple_epochs' in statuses)
            s['any_invalid_response'] += int('invalid_response' in statuses)
            s['any_invalid_timestamp'] += int('invalid_timestamp' in statuses)
            s['any_unsupported_family'] += int('unsupported_family' in statuses)
            s['channel_status'].update(statuses)
            s['units'].update(c.get('input_units', 'unmatched') for c in channels)
            s['static_missing'].update(k for k in STATIC_COLUMNS if joined[k] is None)
            s['vs30_provenance'][joined['vs30_provenance']] += 1
            s['boundary_records'] += int(any(c.get('epoch_ends_within_120s') for c in channels))
            elevation = joined['station_elevation_m']
            s['elevation_mismatch_gt1m'] += int(elevation is not None and any(
                c.get('inventory_elevation_m') is not None and
                abs(c['inventory_elevation_m'] - elevation) > 1 for c in channels))
            tag = f"{row['split']}:{joined['channel_family']}:{','.join(sorted(set(statuses)))}"
            if tag not in examples:
                examples[tag] = joined
                fixture_rows.append(row)
    for s in stats.values():
        for key in ('all_components_matched', 'any_unknown_or_outside_epoch',
                    'any_multiple_epochs', 'any_invalid_response'):
            s[key + '_fraction'] = s[key] / s['records']
    return dict(stats), examples, fixture_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inventory = Inventory.from_archive(args.archive)
    stats, examples, rows = audit(inventory, args.metadata)
    result = {'archive_sha256': sha256(args.archive), 'metadata_export_sha256': sha256(args.metadata),
              'epoch_count': len(inventory.epochs), 'key_count': len(inventory.index),
              'empty_inherited_epoch_count': sum(e.end < e.start for e in inventory.epochs),
              'components': COMPONENTS, 'epoch_boundary_policy': 'closed; ambiguity rejected',
              'splits': stats, 'examples': examples}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    args.output.with_name('actual_records.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'examples'}, indent=2))


if __name__ == '__main__':
    main()
