"""Four pinned cached objects behind a fresh parent authorization; no network code."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import types

PROTOCOL = 'geonet-archive-precontext-sensitivity-v2'
PRECONTEXTS = [0, 1, 3, 5]
BODY_CAP = 64*1024*1024
TOTAL_BODY_CAP = 256*1024*1024
OUTPUT_CAP = 8*1024*1024
SOURCE_NAMES = {'core.py', 'qualification.py', 'child_harness.py', 'supervisor.py', 'PROTOCOL.md', 'SCHEMAS.md', 'RUNTIME_PINS.json'}
LIMITS = {'objects': 4, 'object_bytes': BODY_CAP, 'total_bytes': TOTAL_BODY_CAP,
          'object_advertised_samples': 16_000_000, 'total_advertised_samples': 64_000_000,
          'whole_seconds': 120, 'output_bytes': OUTPUT_CAP}
BASE = Path(__file__).resolve().parent


def check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('elapsed diagnostic deadline')


def digest(body):
    return hashlib.sha256(body).hexdigest()


def valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def bounded_read(path, cap, deadline):
    check_deadline(deadline)
    p = Path(path)
    if not isinstance(path, str) or not p.is_absolute() or str(p) != path or p.resolve() != p:
        raise ValueError('noncanonical input path')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size > cap:
            raise ValueError('not a bounded regular input')
        body = stream.read(cap+1)
    check_deadline(deadline)
    if len(body) > cap:
        raise ValueError('input cap')
    return body


def strict_json(body):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('duplicate JSON field')
            obj[key] = value
        return obj
    def bad(value):
        raise ValueError('nonfinite JSON')
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad)


def load_verified(name, body):
    module = types.ModuleType(name)
    module.__file__ = str(BASE / (name + '.py'))
    exec(compile(body, module.__file__, 'exec'), module.__dict__)
    return module


def validate_slot(slot, index):
    expected_keys = {'slot_index', 'body_path', 'body_sha256', 'body_bytes', 'expected_nslc',
                     't0_ns', 'pick_ns', 'filename_year', 'filename_doy'}
    if not isinstance(slot, dict) or set(slot) != expected_keys or type(slot['slot_index']) is not int or slot['slot_index'] != index:
        raise ValueError('slot schema/order')
    if not valid_hash(slot['body_sha256']) or type(slot['body_bytes']) is not int or not 0 < slot['body_bytes'] <= BODY_CAP:
        raise ValueError('body pin/size')
    if not isinstance(slot['body_path'], str):
        raise ValueError('body path')
    path = Path(slot['body_path'])
    if not path.is_absolute() or str(path) != slot['body_path'] or path.resolve() != path:
        raise ValueError('noncanonical planned body path')
    nslc = slot['expected_nslc']
    if not isinstance(nslc, dict) or set(nslc) != {'network', 'station', 'location', 'channel'}:
        raise ValueError('literal NSLC schema')
    import re
    patterns = {'network': '[A-Z0-9]{2}', 'station': '[A-Z0-9]{1,5}', 'location': '[A-Z0-9]{2}', 'channel': '[A-Z0-9]{2}Z'}
    if any(not isinstance(nslc[k], str) or not re.fullmatch(patterns[k], nslc[k]) for k in patterns):
        raise ValueError('unsupported literal vertical NSLC')
    for field in ('t0_ns', 'pick_ns'):
        if type(slot[field]) is not int or not -(2**63)+10**10 <= slot[field] < 2**63-10**10:
            raise ValueError('unsupported preserved timestamp')
    if type(slot['filename_year']) is not int or not 1900 <= slot['filename_year'] <= 2100:
        raise ValueError('filename year')
    if type(slot['filename_doy']) is not int or not 1 <= slot['filename_doy'] <= 366:
        raise ValueError('filename day')
    import datetime as dt
    if (dt.date(slot['filename_year'], 1, 1)+dt.timedelta(days=slot['filename_doy']-1)).year != slot['filename_year']:
        raise ValueError('invalid filename year/day')


def validate_gate(args):
    deadline = args.deadline
    for key in ('plan_sha256', 'authorization_sha256', 'adapter_sha256', 'supervisor_sha256', 'runtime_sha256'):
        if not valid_hash(getattr(args, key)):
            raise ValueError('trusted invocation pin')
    pbody = bounded_read(args.plan, 64*1024, deadline)
    abody = bounded_read(args.authorization, 64*1024, deadline)
    if digest(pbody) != args.plan_sha256 or digest(abody) != args.authorization_sha256:
        raise ValueError('trusted parent pin mismatch')
    plan, auth = strict_json(pbody), strict_json(abody)
    if (not isinstance(plan, dict) or set(plan) != {'protocol_id', 'slots', 'source_files', 'limits', 'precontexts_seconds'}
            or plan['protocol_id'] != PROTOCOL or plan['limits'] != LIMITS
            or type(plan['precontexts_seconds']) is not list or plan['precontexts_seconds'] != PRECONTEXTS
            or any(type(v) is not int for v in plan['precontexts_seconds'])):
        raise ValueError('plan identity/limits')
    auth_keys = {'protocol_id', 'offline_decode_authorized', 'plan_sha256', 'source_files', 'limits',
                 'pushed_source_commit', 'source_manifest_sha256', 'review_receipt_sha256', 'test_receipt_sha256',
                 'code_only_review_clean', 'focused_tests_passed', 'precontexts_seconds'}
    if (not isinstance(auth, dict) or set(auth) != auth_keys or auth['protocol_id'] != PROTOCOL
            or auth['offline_decode_authorized'] is not True or auth['code_only_review_clean'] is not True
            or auth['focused_tests_passed'] is not True or auth['plan_sha256'] != args.plan_sha256
            or auth['limits'] != LIMITS or auth['source_files'] != plan['source_files']
            or type(auth['precontexts_seconds']) is not list or auth['precontexts_seconds'] != PRECONTEXTS
            or any(type(v) is not int for v in auth['precontexts_seconds'])):
        raise ValueError('fresh parent authorization')
    commit = auth['pushed_source_commit']
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('pushed source binding')
    for key in ('source_manifest_sha256', 'review_receipt_sha256', 'test_receipt_sha256'):
        if not valid_hash(auth[key]):
            raise ValueError('public proof binding')
    sources = plan['source_files']
    if not isinstance(sources, dict) or set(sources) != SOURCE_NAMES or any(not valid_hash(v) for v in sources.values()):
        raise ValueError('processing source allowlist')
    if sources['child_harness.py'] != args.adapter_sha256 or sources['supervisor.py'] != args.supervisor_sha256:
        raise ValueError('running source pins')
    buffers = {}
    for name in sorted(sources):
        buffers[name] = bounded_read(str(BASE/name), 4*1024*1024, deadline)
        if digest(buffers[name]) != sources[name]:
            raise ValueError('processing source changed')
    slots = plan['slots']
    if not isinstance(slots, list) or len(slots) != 4:
        raise ValueError('exact four slots')
    for i, slot in enumerate(slots):
        validate_slot(slot, i)
    if len({slot['body_path'] for slot in slots}) != 4 or sum(slot['body_bytes'] for slot in slots) > TOTAL_BODY_CAP:
        raise ValueError('four distinct bounded bodies')
    return plan, auth, buffers


def verify_runtime(pin_body, args):
    pins = strict_json(pin_body)
    check_deadline(args.deadline)
    if pins['python_executable'] != args.runtime_path or sys.executable != args.runtime_path:
        raise ValueError('runtime executable path')
    resolved = str(Path(args.runtime_path).resolve())
    if resolved != pins['resolved_python_executable'] or pins['python_sha256'] != args.runtime_sha256:
        raise ValueError('runtime executable identity')
    if digest(bounded_read(resolved, 128*1024*1024, args.deadline)) != args.runtime_sha256:
        raise ValueError('runtime executable changed')
    if sys.version != pins['python_version'] or str(Path(sys.prefix).resolve()) != pins['prefix']:
        raise ValueError('runtime prefix/version')
    root = Path(pins['site_packages_root'])
    if root.resolve() != root or not root.is_absolute():
        raise ValueError('runtime package root')
    actual = set()
    for p in root.rglob('*'):
        check_deadline(args.deadline)
        if p.is_symlink():
            raise ValueError('runtime symlink')
        if p.is_file():
            actual.add(p.relative_to(root).as_posix())
    if actual != set(pins['files']):
        raise ValueError('runtime file inventory changed')
    for relative, pin in pins['files'].items():
        p = Path(relative)
        if p.is_absolute() or any(part in ('.', '..') for part in p.parts) or p.as_posix() != relative:
            raise ValueError('runtime member name')
        data = bounded_read(str(root/p), 128*1024*1024, args.deadline)
        if len(data) != pin['bytes'] or digest(data) != pin['sha256']:
            raise ValueError('runtime package source changed')
    # -S prevents executable .pth/sitecustomize hooks before the read/authority gate.
    # Enable only this now-verified directory; do not call site.main/addsitedir.
    sys.path.append(str(root))
    import obspy
    import numpy
    if obspy.__version__ != pins['obspy_version'] or numpy.__version__ != pins['numpy_version']:
        raise ValueError('scientific version changed')
    return obspy.read


def run(args):
    plan, auth, buffers = validate_gate(args)
    read = verify_runtime(buffers['RUNTIME_PINS.json'], args)
    core = load_verified('core', buffers['core.py'])
    qualification = load_verified('qualification', buffers['qualification.py'])
    rows = []
    used_samples = 0
    validated_body_count = 0
    for slot in plan['slots']:
        check_deadline(args.deadline)
        body = bounded_read(slot['body_path'], BODY_CAP, args.deadline)
        if len(body) != slot['body_bytes'] or digest(body) != slot['body_sha256']:
            raise ValueError('cached body changed')
        validated_body_count += 1
        try:
            stream, count, warning_count = qualification.decode(body, read, 64_000_000-used_samples)
            used_samples += count
            row = qualification.analyze(stream, slot, core)
            row.update(advertised_samples=count, decode_warning_count=warning_count)
            del stream
        except Exception as error:
            if isinstance(error, (MemoryError, TimeoutError)):
                raise
            # No exception strings/warnings/identities enter aggregate or failure messages.
            row = qualification.failed(slot['slot_index'], 'decode_or_grid_unsupported')
        rows.append(row)
        del body
        check_deadline(args.deadline)
    result = {'protocol_id': PROTOCOL,
              'private': {'slots': rows, 'provenance': {'plan_sha256': args.plan_sha256,
                'authorization_sha256': args.authorization_sha256, 'source_files': plan['source_files'],
                'pushed_source_commit': auth['pushed_source_commit'], 'validated_body_count': validated_body_count,
                'advertised_samples_decoded': used_samples, 'precontexts_seconds': plan['precontexts_seconds']}},
              'public_aggregate': qualification.aggregate(rows)}
    return result


def bounded_result(result):
    # iterencode prevents materializing a result bigger than the declared stdout cap.
    pieces = []
    size = 0
    for fragment in json.JSONEncoder(sort_keys=True, allow_nan=False).iterencode(result):
        body = fragment.encode('utf-8')
        size += len(body)
        if size + 1 > OUTPUT_CAP:
            raise ValueError('output cap')
        pieces.append(body)
    return b''.join(pieces) + b'\n'


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('invalid child arguments')


def main():
    try:
        parser = PrivateArgumentParser()
        for name in ('plan', 'plan-sha256', 'authorization', 'authorization-sha256', 'adapter-sha256',
                     'supervisor-sha256', 'runtime-sha256', 'runtime-path'):
            parser.add_argument('--'+name, required=True)
        parser.add_argument('--deadline', type=float, required=True)
        args = parser.parse_args()
        if not math.isfinite(args.deadline) or not 0 < args.deadline-time.monotonic() <= 120:
            raise ValueError('child deadline')
        # No plan, source package or cached-body reads until parent retains the worker handle.
        if sys.stdin.buffer.read(1) != b'G':
            raise ValueError('start gate')
        check_deadline(args.deadline)
        body = bounded_result(run(args))
        check_deadline(args.deadline)
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()
        return 0
    except BaseException:
        sys.stderr.write('{"complete":false,"reason":"offline_child_failed"}\n')
        return 1


if __name__ == '__main__':
    sys.exit(main())
