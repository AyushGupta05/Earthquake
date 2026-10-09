"""Inventory public Alaska MiniSEED headers, without sample decoding or inference.

Every selected ZIP member is fully decompressed and CRC checked by zipfile.
ObsPy is explicitly restricted to MiniSEED headonly=True. This is an archive
availability audit, not a reproduction of the publication's 530-event cohort.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import signal
import time
import warnings
import zipfile

import numpy as np
import obspy

EXPECTED_BYTES = 8372439484
EXPECTED_MD5 = '38449cb548b3e5c7119b267f6a12a400'
ROOT = 'testsuite_data_williamson/'
MAX_MEMBER_BYTES = 50000000


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def parse_metadata(text):
    records = defaultdict(list)
    for line in text.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) != 10:
            raise ValueError('Expected ten station metadata fields')
        net, sta, loc, cha = parts[:4]
        key = '.'.join((net, sta, '' if loc == '--' else loc, cha))
        lat, lon, elev, rate, gain = map(float, parts[4:9])
        if not all(math.isfinite(x) for x in (lat, lon, elev, rate, gain)) or rate <= 0 or gain <= 0:
            raise ValueError('Invalid finite metadata/rate/gain')
        records[key].append({'sampling_rate': rate, 'gain': gain, 'units': parts[9]})
    return dict(records)


def select_members(names, expected_events=781):
    """Join release <id>.dat to <id>_replay.seed, rejecting silent collisions.

    This operates on directory names only. It never opens a waveform member.
    The publication cohort is deliberately not reconstructed here.
    """
    if len(names) != len(set(names)):
        raise ValueError('Duplicate ZIP names')
    metadata, seeds = {}, {}
    for name in names:
        if name.endswith('/'):
            continue
        if name.startswith(ROOT + 'channel_files/') and name.endswith('.dat'):
            event = name[len(ROOT + 'channel_files/'):-len('.dat')]
            destination = metadata
        elif name.startswith(ROOT + 'miniseed/') and name.endswith('_replay.seed'):
            event = name[len(ROOT + 'miniseed/'):-len('_replay.seed')]
            destination = seeds
        else:
            raise ValueError(f'Unexpected release member: {name}')
        if not event or '/' in event or event in destination:
            raise ValueError('Empty, nested or duplicate event member identity')
        destination[event] = name
    if set(metadata) != set(seeds) or len(seeds) != expected_events:
        raise ValueError(f'Release does not have expected {expected_events} matched event containers')
    return metadata, seeds


def inspect_headers(payload, metadata):
    # libmseed can skip corrupt/truncated records and return a partial Stream.
    # Byte-integrity checks alone cannot establish complete header coverage.
    # Conservatively require a warning-free reader; even benign warnings need
    # explicit review before relaxing this gate for an availability audit.
    with warnings.catch_warnings(record=True) as reader_warnings:
        warnings.simplefilter('always')
        stream = obspy.read(io.BytesIO(payload), format='MSEED', headonly=True)
    if reader_warnings:
        details = '; '.join(f'{w.category.__name__}: {w.message}' for w in reader_warnings)
        raise ValueError('MiniSEED reader warning; header audit incomplete: ' + details)
    by_id = defaultdict(list)
    for trace in stream:
        if len(trace.data) != 0:
            raise ValueError('Head-only reader unexpectedly decoded samples')
        s = trace.stats
        rate, n = float(s.sampling_rate), int(s.npts)
        if not math.isfinite(rate) or rate <= 0 or n <= 0:
            raise ValueError('Invalid header sample count/rate')
        by_id[trace.id].append({'start': float(s.starttime), 'end': float(s.endtime),
                               'sampling_rate': rate, 'npts': n})
    if not by_id:
        raise ValueError('Empty MiniSEED headers')
    missing_metadata = sorted(set(by_id) - set(metadata))
    absent_waveforms = sorted(set(metadata) - set(by_id))
    mismatches, gaps, overlaps = [], [], []
    rates, units = Counter(), Counter()
    total_samples = 0
    for key, segments in sorted(by_id.items()):
        segments.sort(key=lambda x: (x['start'], x['end']))
        expected = {x['sampling_rate'] for x in metadata.get(key, [])}
        for segment in segments:
            rates[str(segment['sampling_rate'])] += 1
            total_samples += segment['npts']
            if expected and segment['sampling_rate'] not in expected:
                mismatches.append({'id': key, 'header_rate': segment['sampling_rate'], 'metadata_rates': sorted(expected)})
        for unit in {x['units'] for x in metadata.get(key, [])}:
            units[unit] += 1
        # Union coverage endpoint handles nested/duplicate segments. Tolerance
        # is half the smaller sample interval, not an inferred missing count.
        endpoint, previous_rate = None, None
        for segment in segments:
            end_exclusive = segment['end'] + 1 / segment['sampling_rate']
            if endpoint is not None:
                delta = segment['start'] - endpoint
                tolerance = .5 / max(previous_rate, segment['sampling_rate'])
                if delta > tolerance:
                    gaps.append({'id': key, 'seconds': delta})
                elif delta < -tolerance:
                    # Nested segments only overlap for their own duration, not
                    # all the way to the accumulated coverage endpoint.
                    overlaps.append({'id': key, 'seconds': min(endpoint, end_exclusive) - segment['start']})
            if endpoint is None or end_exclusive > endpoint:
                endpoint, previous_rate = end_exclusive, segment['sampling_rate']
    return {'channels': len(by_id), 'header_segments': len(stream), 'header_declared_samples': total_samples,
            'header_rate_segments': dict(rates), 'matched_channel_units': dict(units),
            'missing_metadata': missing_metadata, 'metadata_without_waveforms': absent_waveforms,
            'rate_mismatches': mismatches, 'gaps': gaps, 'overlaps': overlaps,
            'duplicate_metadata_ids': sorted(k for k,v in metadata.items() if len(v) != 1),
            'first_start_utc': str(obspy.UTCDateTime(min(x['start'] for v in by_id.values() for x in v))),
            'last_end_utc': str(obspy.UTCDateTime(max(x['end'] for v in by_id.values() for x in v))),
            'segments_by_channel': dict(by_id)}


def inspect_member(archive, seed_member, metadata_member):
    """Read complete members (including CRC verification) before parsing."""
    seed_info, metadata_info = archive.getinfo(seed_member), archive.getinfo(metadata_member)
    if seed_info.file_size > MAX_MEMBER_BYTES or metadata_info.file_size > MAX_MEMBER_BYTES:
        raise ValueError('Member exceeds prespecified 50 MB memory limit')
    rows = parse_metadata(archive.read(metadata_member).decode('utf-8'))
    result = inspect_headers(archive.read(seed_member), rows)
    result.update(seed_member=seed_member, seed_crc32=seed_info.CRC, seed_bytes=seed_info.file_size,
                  metadata_member=metadata_member, metadata_crc32=metadata_info.CRC,
                  metadata_bytes=metadata_info.file_size)
    return result


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def deadline(*_):
        raise TimeoutError('Header audit exceeded fixed 1800-second wall limit')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1800)
    started = time.monotonic()
    if args.output.exists():
        raise FileExistsError('Audit output must be fresh')
    if args.archive.stat().st_size != EXPECTED_BYTES or digest(args.archive, 'md5') != EXPECTED_MD5:
        raise ValueError('Full release ZIP differs from published identity')
    args.output.mkdir(parents=True)
    results = {}
    with zipfile.ZipFile(args.archive) as archive:
        metadata, seeds = select_members(archive.namelist())
        for index, event in enumerate(sorted(seeds)):
            # Reading a member to EOF checks ZIP CRC. No extraction paths are used.
            results[event] = inspect_member(archive, seeds[event], metadata[event])
            if (index + 1) % 50 == 0:
                print(json.dumps({'completed': index+1, 'elapsed_seconds': time.monotonic()-started}), flush=True)
    atomic_json(args.output/'events.json', results)
    counts = {key: sum(len(r[key]) for r in results.values()) for key in
              ('missing_metadata', 'metadata_without_waveforms', 'rate_mismatches', 'gaps', 'overlaps', 'duplicate_metadata_ids')}
    summary = {'schema': 'alaska-header-availability-v1', 'complete': True,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'archive_bytes': EXPECTED_BYTES,
        'archive_md5': EXPECTED_MD5, 'source_sha256': digest(__file__),
        'events_json_sha256': digest(args.output/'events.json'), 'event_containers': len(results),
        'obspy_version': obspy.__version__, 'numpy_version': np.__version__,
        'sample_arrays_decoded': False, 'zip_selected_members_fully_decompressed_crc_verified': True,
        'picks_or_predictions_computed': False, 'magnitude_labels_used': False,
        'cohort': '781 release containers; not a reconstruction of the published 530-event cohort',
        'header_channels': sum(r['channels'] for r in results.values()),
        'header_segments': sum(r['header_segments'] for r in results.values()),
        'counts': counts, 'elapsed_seconds': time.monotonic()-started}
    atomic_json(args.output/'COMPLETE.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
