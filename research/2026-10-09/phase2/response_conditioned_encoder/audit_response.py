"""Metadata-only acquisition response audit. Never opens waveforms or labels.

Descriptors use pinned ObsPy/evalresp, default physical input/output units,
all response stages, and fixed frequencies. Grid/stage comparisons exercise
independent API paths through the SAME backend, not independent physics.
"""
from collections import Counter, defaultdict
from contextlib import contextmanager
import argparse
import csv
from dataclasses import asdict
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
import tempfile
from pathlib import Path
import sys
import tarfile
import time
import warnings
import xml.etree.ElementTree as ET

import numpy as np

FREQUENCIES = np.array([.5, 1., 2., 4., 8., 16.], dtype=np.float64)
ARCHIVE_SHA = '71eccc6304afad15e9c45534ca374b4b4f974c9f93ccfc0f2683616ee6421ef2'
INVENTORY_SHA = '9a942c4773e5c18264aa2db432ba4669f965004aeb9a1f67f25a67d6c812c227'
NS = {'s': 'http://www.fdsn.org/xml/station/1'}
REFERENCE_ATOL = 1e-10
REFERENCE_RTOL = 1e-7


def sha(path):
    result = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            result.update(block)
    return result.hexdigest()


def load_module(name, path, expected=None):
    if expected and sha(path) != expected:
        raise ValueError('Pinned source mismatch: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def relative_error(value, reference):
    return float(np.max(np.abs(value-reference)/np.maximum(np.abs(reference), 1e-30)))


def canonical_unit(unit):
    unit = (unit or '').upper().replace(' ', '')
    return {'M/S**2': 'M/S^2', 'M/S/S': 'M/S^2', 'COUNT': 'COUNTS',
            'VOLT': 'V', 'VOLTS': 'V'}.get(unit, unit)


@contextmanager
def capture_native_stderr():
    """Capture evalresp C warnings in this single-threaded audit process."""
    result = []
    sys.stderr.flush()
    saved = os.dup(2)
    with tempfile.TemporaryFile(mode='w+b') as stream:
        try:
            os.dup2(stream.fileno(), 2)
            yield result
        finally:
            sys.stderr.flush()
            os.dup2(saved, 2)
            os.close(saved)
            stream.seek(0)
            result.extend(line.strip() for line in stream.read().decode('utf-8', errors='replace').splitlines() if line.strip())


def evaluate_response(response):
    """Evaluate a unique native response; channel rate mask is added separately.

    Quality mismatch fails closed for descriptor use, but every failure is
    retained for audit. InstrumentSensitivity is NOT multiplied into evalresp's
    already scaled full-stage transfer function a second time.
    """
    result = {'valid_response': False, 'reasons': [], 'warnings': [], 'native_warnings': []}
    sensitivity = response.instrument_sensitivity
    stages = response.response_stages
    if sensitivity is None or not stages:
        result['reasons'].append('missing_sensitivity_or_stages')
        return result
    try:
        g, fc = float(sensitivity.value), float(sensitivity.frequency)
    except (TypeError, ValueError, OverflowError):
        result['reasons'].append('invalid_scalar_sensitivity')
        return result
    result.update(sensitivity=float(g), calibration_frequency_hz=float(fc),
                  input_units=canonical_unit(sensitivity.input_units),
                  output_units=canonical_unit(sensitivity.output_units),
                  stage_types=[type(s).__name__ for s in stages],
                  stage_numbers=[s.stage_sequence_number for s in stages])
    if not math.isfinite(g) or g <= 0 or not math.isfinite(fc) or fc < 0:
        result['reasons'].append('invalid_scalar_sensitivity')
        return result
    if result['input_units'] not in ('M/S', 'M/S^2') or result['output_units'] != 'COUNTS':
        result['reasons'].append('unsupported_units')
    seq = result['stage_numbers']
    if seq != list(range(1, len(stages)+1)):
        result['reasons'].append('noncontiguous_stage_numbers')
    chain = [canonical_unit(stages[0].input_units)]
    for stage in stages:
        if canonical_unit(stage.input_units) != chain[-1]:
            result['reasons'].append('stage_unit_discontinuity')
        chain.append(canonical_unit(stage.output_units))
    if chain[0] != result['input_units'] or chain[-1] != result['output_units']:
        result['reasons'].append('endpoint_unit_mismatch')
    result['unit_chain'] = chain
    if result['reasons']:
        result['reasons'] = sorted(set(result['reasons']))
        return result
    try:
        with capture_native_stderr() as native, warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            rates = response.get_sampling_rates()
            result['stage_sampling_rates_obspy_inferred'] = rates
            for stage in stages:
                digital = (type(stage).__name__ == 'FIRResponseStage' or
                           getattr(stage, 'pz_transfer_function_type', '').upper().startswith('DIGITAL') or
                           getattr(stage, 'cf_transfer_function_type', '').upper().startswith('DIGITAL'))
                clock = rates.get(stage.stage_sequence_number, {}).get('input_sampling_rate')
                if digital and (clock is None or not math.isfinite(float(clock)) or clock <= 0):
                    # Evalresp otherwise invents a1Hz clock for digital PZ stages.
                    result['reasons'].append('digital_sampling_clock_unresolved')
                    raise ValueError('Digital response requires a positive determined input clock')
            result['final_stage_output_rate'] = rates[max(rates)]['output_sampling_rate'] if rates else None
            kwargs = dict(output='DEF', hide_sensitivity_mismatch_warning=True)
            full = response.get_evalresp_response_for_frequencies(FREQUENCIES, **kwargs)
            # .5 Hz grid, up to64Hz; t_samp defines queried frequency spacing,
            # not the acquisition chain rate, which is stored in its stages.
            grid, gf = response.get_evalresp_response(t_samp=1/128, nfft=256, **kwargs)
            indices = np.rint(FREQUENCIES/.5).astype(int)
            if not np.array_equal(gf[indices], FREQUENCIES):
                raise ValueError('FFT grid does not contain exact six frequencies')
            product = np.ones(len(FREQUENCIES), dtype=complex)
            for stage in stages:
                product *= response.get_evalresp_response_for_frequencies(
                    FREQUENCIES, start_stage=stage.stage_sequence_number,
                    end_stage=stage.stage_sequence_number, **kwargs)
            at_calibration = response.get_evalresp_response_for_frequencies([fc], **kwargs)[0]
        result['warnings'] = sorted(set(str(w.message) for w in caught))
        result['native_warnings'] = sorted(set(native))
        if any('inconsistent' in w for w in result['warnings']):
            result['reasons'].append('stage_sampling_inconsistent')
        arrays = (full, grid[indices], product)
        if any(not np.isfinite(a).all() for a in arrays) or not np.isfinite(at_calibration):
            raise ValueError('Nonfinite frequency response')
        result['grid_relative_error'] = relative_error(grid[indices], full)
        result['stage_product_relative_error'] = relative_error(product, full)
        # Relative comparison is meaningful in native units after gain division.
        if not np.allclose(grid[indices]/g, full/g, atol=REFERENCE_ATOL, rtol=REFERENCE_RTOL):
            result['reasons'].append('grid_disagreement')
        if not np.allclose(product/g, full/g, atol=REFERENCE_ATOL, rtol=REFERENCE_RTOL):
            result['reasons'].append('stage_product_disagreement')
        result['calibration_gain_ratio'] = float(abs(at_calibration)/g)
        if abs(result['calibration_gain_ratio']-1) > .05:
            result['reasons'].append('reported_fullstage_sensitivity_mismatch_gt5pct')
        ratio = full/g
        # Missing/zero entries are masked, never treated as measured flatness.
        finite = np.isfinite(ratio) & (np.abs(ratio) > 0)
        logamp = np.zeros(len(ratio))
        logamp[finite] = np.log(np.abs(ratio[finite]))
        phase = np.angle(ratio)
        result['transfer_real'] = full.real.tolist()
        result['transfer_imag'] = full.imag.tolist()
        result['descriptor_unmasked'] = np.stack([logamp, np.cos(phase), np.sin(phase)], axis=-1).tolist()
        result['frequency_finite_nonzero'] = finite.tolist()
        result['valid_response'] = not result['reasons']
    except Exception as exc:
        result['reasons'].append('evalresp_error')
        result['exception'] = type(exc).__name__ + ': ' + str(exc)
        result['native_warnings'] = sorted(set(native)) if 'native' in locals() else []
    result['reasons'] = sorted(set(result['reasons']))
    return result


def descriptor_for_channel(evaluated, sample_rate):
    """Six x(log amplitude, cosine, sine, valid mask), with exact zero fallback."""
    output = np.zeros((len(FREQUENCIES), 4), dtype=np.float64)
    if not evaluated.get('valid_response') or sample_rate is None or not math.isfinite(sample_rate) or sample_rate <= 0:
        return output
    final_rate = evaluated.get('final_stage_output_rate')
    if final_rate is not None and not math.isclose(final_rate, sample_rate, rel_tol=1e-8, abs_tol=1e-6):
        return output
    mask = (FREQUENCIES < .4*sample_rate) & np.asarray(evaluated['frequency_finite_nonzero'], dtype=bool)
    output[mask, :3] = np.asarray(evaluated['descriptor_unmasked'])[mask]
    output[:, 3] = mask
    return output


def covering_epoch(epochs, begin, end):
    """Conservative inclusive overlap: even a boundary-touch competitor rejects."""
    if begin is None or end is None or not math.isfinite(begin) or not math.isfinite(end) or end < begin:
        return 'invalid_window', None
    overlapping = [e for e in epochs if e.end >= e.start and e.start <= end and e.end >= begin]
    if not epochs:
        return 'no_channel_key', None
    if not overlapping:
        return 'outside_epoch', None
    if len(overlapping) != 1:
        return 'multiple_overlapping_epochs', None
    epoch = overlapping[0]
    if epoch.start > begin or epoch.end < end:
        return 'partial_epoch_cover', None
    if not epoch.usable:
        return 'invalid_scalar_response', epoch
    return 'matched', epoch


def load_archive(archive_path, inventory_module):
    import obspy
    if sha(archive_path) != ARCHIVE_SHA:
        raise ValueError('Pinned response archive mismatch')
    epochs, responses, member_hashes = [], {}, {}
    stage_count = Counter()
    with tarfile.open(archive_path) as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith('.xml'):
                continue
            raw = archive.extractfile(member).read()
            member_hashes[member.name] = hashlib.sha256(raw).hexdigest()
            root = ET.fromstring(raw)
            parsed = inventory_module.parse_xml(root, member.name)
            xml_channels = root.findall('s:Network/s:Station/s:Channel', NS)
            obs = obspy.read_inventory(io.BytesIO(raw), format='STATIONXML')
            obspy_channels = [(net.code, sta.code, ch.location_code, ch.code, ch) for net in obs for sta in net for ch in sta]
            if not (len(parsed) == len(xml_channels) == len(obspy_channels)):
                raise ValueError('XML/parser channel count disagreement')
            for epoch, xml, observed in zip(parsed, xml_channels, obspy_channels):
                channel = observed[-1]
                if tuple(observed[:4]) != epoch.key:
                    raise ValueError('ObsPy channel identity order disagreement')
                node = xml.find('s:Response', NS)
                # A string sentinel survives sorted JSON and later keyed joins.
                rid = hashlib.sha256(ET.tostring(node)).hexdigest() if node is not None else 'missing_response'
                if rid not in responses:
                    responses[rid] = evaluate_response(channel.response) if channel.response is not None else {'valid_response': False, 'reasons':['no_response']}
                    stage_count.update(responses[rid].get('stage_types', []))
                record = asdict(epoch)
                record['response_id'] = rid
                record['epoch_id'] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
                record['descriptor'] = descriptor_for_channel(responses[rid], epoch.sample_rate_hz).tolist()
                rate = responses[rid].get('final_stage_output_rate')
                record['channel_reasons'] = (['native_rate_mismatch'] if rate is not None and epoch.sample_rate_hz is not None and not math.isclose(rate, epoch.sample_rate_hz, rel_tol=1e-8, abs_tol=1e-6) else [])
                epochs.append((epoch, record))
            print('response XML members=' + str(len(member_hashes)) + ' unique=' + str(len(responses)), flush=True) if len(member_hashes)%100 == 0 else None
    return epochs, responses, member_hashes, stage_count


def json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.partial')
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True, default=json_default, allow_nan=False)+'\n')
    temporary.replace(path)


def finite_json(value):
    if isinstance(value, dict):
        return {k: finite_json(v) for k,v in value.items()}
    if isinstance(value, list):
        return [finite_json(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def archive_main(args):
    import obspy, scipy
    from obspy.signal import evrespwrapper
    if obspy.__version__ != '1.5.1' or np.__version__ != '2.2.6' or scipy.__version__ != '1.15.3':
        raise RuntimeError('Audit runtime version changed')
    start = time.monotonic()
    module = load_module('response_audit_inventory', args.inventory_module, INVENTORY_SHA)
    epochs, responses, members, stages = load_archive(args.archive, module)
    failures = Counter(reason for r in responses.values() for reason in r['reasons'])
    output = Path(args.output);output.mkdir(parents=True, exist_ok=True)
    atomic_json(output/'response_evaluations.json', finite_json(responses))
    atomic_json(output/'channel_epochs.json', finite_json([r for _,r in epochs]))
    summary = {'scope':'Public acquisition metadata only; no waveform or target reads',
               'frequencies_hz': FREQUENCIES.tolist(), 'output':'DEF',
               'sample_rate_mask':'frequency < 0.4 * native_sample_rate',
               'comparison':{'rtol':REFERENCE_RTOL,'atol_after_sensitivity_division':REFERENCE_ATOL,
                             'independence_boundary':'API/grid and stage decomposition share the same pinned C evalresp backend'},
               'archive_sha256':sha(args.archive), 'source_sha256':sha(__file__),
               'inventory_module_sha256':sha(args.inventory_module), 'xml_member_sha256':members,
               'obspy':obspy.__version__,'numpy':np.__version__,'scipy':scipy.__version__,
               'evalresp_library':str(evrespwrapper.clibevresp._name),
               'evalresp_library_sha256':sha(evrespwrapper.clibevresp._name),
               'counts':{'xml_members':len(members),'channel_epochs':len(epochs),'unique_response_descriptions':len(responses),
                         'valid_unique_responses':sum(r['valid_response'] for r in responses.values()),
                         'channel_epochs_all6_frequencies':sum(np.asarray(r['descriptor'])[:,3].sum()==6 for _,r in epochs)},
               'stage_types_unique_response_count':dict(stages),'failures_nonexclusive':dict(failures),
               'max_grid_relative_error':max((r.get('grid_relative_error',0) for r in responses.values()),default=0),
               'max_stage_product_relative_error':max((r.get('stage_product_relative_error',0) for r in responses.values()),default=0),
               'seconds':time.monotonic()-start}
    atomic_json(output/'archive_audit.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='xml_member_sha256'}, indent=2, default=json_default))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--inventory-module', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    archive_main(parser.parse_args())
