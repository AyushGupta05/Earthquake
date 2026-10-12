"""Twelve pinned cached objects behind a fresh parent authorization; no network code."""
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

PROTOCOL = 'geonet-archive-enz-retained-failure-qualification-v4'
PRECONTEXT = 3
COMPONENTS = ('E', 'N', 'Z')
CORE_SHA256 = '70c2a53c7beef5f1ddfae7d46e52bcdae97ee711cd10636da6250bd20ab9144e'
RUNTIME_PINS_SHA256 = 'a5a273ffad973848521d08bb5b730fe226c7a45440c298ac25e20624a158c9f6'
QUALIFICATION_PROPOSAL_SHA256 = 'cf29847b2c7529b6f12de8365a06c734d11fceff5b5bf51a1500134e6cd93b60'
PROPOSAL_SHA256 = '9db9d9a06d0ae5c01740b5e5c7befd96a1c34e8b7eef9527639f70b4d4538bb4'
BODY_CAP = 64*1024*1024
TOTAL_BODY_CAP = 768*1024*1024
OUTPUT_CAP = 8*1024*1024
SOURCE_NAMES = {'core.py', 'qualification.py', 'child_harness.py', 'supervisor.py', 'PROTOCOL.md', 'SCHEMAS.md', 'RUNTIME_PINS.json', 'PUBLIC_TRANSPORT_PROPOSAL.md', 'PUBLIC_QUALIFICATION_PROPOSAL.md'}
LIMITS = {'objects': 12, 'object_bytes': BODY_CAP, 'total_bytes': TOTAL_BODY_CAP,
          'object_advertised_samples': 16_000_000, 'total_advertised_samples': 192_000_000,
          'whole_seconds': 120, 'output_bytes': OUTPUT_CAP}
BASE = Path(__file__).resolve().parent


def valid_limits(value):
    return (isinstance(value, dict) and set(value) == set(LIMITS)
            and all(type(value[k]) is int and value[k] == v for k, v in LIMITS.items()))


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


def validate_object(slot, index, suffix):
    expected_keys = {'slot_index', 'body_path', 'body_sha256', 'body_bytes', 'expected_nslc',
                     't0_ns', 'pick_ns', 'filename_year', 'filename_doy', 'transport_status'}
    if not isinstance(slot, dict) or set(slot) != expected_keys or type(slot['slot_index']) is not int or slot['slot_index'] != index:
        raise ValueError('slot schema/order')
    if not valid_hash(slot['body_sha256']) or type(slot['body_bytes']) is not int or not 0 < slot['body_bytes'] <= BODY_CAP:
        raise ValueError('body pin/size')
    if not isinstance(slot['body_path'], str):
        raise ValueError('body path')
    path = Path(slot['body_path'])
    if not path.is_absolute() or str(path) != slot['body_path'] or path.resolve() != path:
        raise ValueError('noncanonical planned body path')
    allowed=('prior_vertical_qualified',) if suffix=='Z' else ('qualified_http200','unqualified_http404')
    if slot['transport_status'] not in allowed:raise ValueError('component transport status')
    nslc = slot['expected_nslc']
    if not isinstance(nslc, dict) or set(nslc) != {'network', 'station', 'location', 'channel'}:
        raise ValueError('literal NSLC schema')
    import re
    patterns = {'network': '[A-Z0-9]{2}', 'station': '[A-Z0-9]{1,5}', 'location': '[A-Z0-9]{2}', 'channel': '[A-Z0-9]{2}'+suffix}
    if any(not isinstance(nslc[k], str) or not re.fullmatch(patterns[k], nslc[k]) for k in patterns):
        raise ValueError('unsupported literal component NSLC')
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


PREREQUISITE_IDS = {'transport_protocol_id':'geonet-anonymous-archive-transport-v5',
                    'transport_study_id':'geonet-configured-eight-horizontal-precontext3-transport-v5',
                    'transport_proposal_sha256':PROPOSAL_SHA256,
                    'qualification_proposal_sha256':QUALIFICATION_PROPOSAL_SHA256}
PREREQUISITE_PINS = {'v5_collection_manifest_sha256','v5_returned_summary_sha256','independent_v4_audit_sha256',
                     'vertical_v2_result_sha256','parent_metadata_custody_sha256'}


TERMINAL_ACCOUNTING={'horizontal_attempts':8,'qualified_http200':6,'unqualified_http404':2,'prior_vertical_qualified':4}


def status_digest(slots):
    masks=[{k:slot['components'][k]['transport_status'] for k in COMPONENTS} for slot in slots]
    return digest(json.dumps(masks,sort_keys=True,separators=(',',':')).encode('utf-8'))


def validate_prerequisites(value):
    if (not isinstance(value,dict) or set(value)!=set(PREREQUISITE_IDS)|PREREQUISITE_PINS|{'terminal_accounting'}
            or any(value[k]!=v for k,v in PREREQUISITE_IDS.items())
            or any(not valid_hash(value[k]) for k in PREREQUISITE_PINS)):
        raise ValueError('parent prerequisite bindings')
    counts=value['terminal_accounting']
    if (not isinstance(counts,dict) or set(counts)!=set(TERMINAL_ACCOUNTING)
            or any(type(counts[k]) is not int or counts[k]!=v for k,v in TERMINAL_ACCOUNTING.items())):
        raise ValueError('strict six/two/four terminal accounting')


def validate_slot(slot, index):
    if (not isinstance(slot,dict) or set(slot)!={'slot_index','t0_ns','pick_ns','filename_year','filename_doy','components'}
            or not isinstance(slot['components'],dict) or set(slot['components'])!=set(COMPONENTS)):
        raise ValueError('fixed ENZ slot schema')
    identities=[]
    for suffix in COMPONENTS:
        obj=slot['components'][suffix]
        if not isinstance(obj,dict) or set(obj)!={'body_path','body_sha256','body_bytes','expected_nslc','transport_status'}:
            raise ValueError('component input schema')
        flat={k:slot[k] for k in ('slot_index','t0_ns','pick_ns','filename_year','filename_doy')}
        flat.update(obj)
        validate_object(flat,index,suffix)
        n=obj['expected_nslc'];identities.append((n['network'],n['station'],n['location'],n['channel'][:2]))
    if len(set(identities))!=1:
        raise ValueError('literal ENZ triplet correspondence')


def validate_gate(args):
    deadline = args.deadline
    for key in ('plan_sha256', 'authorization_sha256', 'adapter_sha256', 'supervisor_sha256', 'runtime_sha256','transport_statuses_sha256'):
        if not valid_hash(getattr(args, key)):
            raise ValueError('trusted invocation pin')
    pbody = bounded_read(args.plan, 64*1024, deadline)
    abody = bounded_read(args.authorization, 64*1024, deadline)
    if digest(pbody) != args.plan_sha256 or digest(abody) != args.authorization_sha256:
        raise ValueError('trusted parent pin mismatch')
    plan, auth = strict_json(pbody), strict_json(abody)
    if (not isinstance(plan, dict) or set(plan) != {'protocol_id', 'slots', 'source_files', 'limits', 'precontext_s', 'prerequisites','transport_statuses_sha256'}
            or plan['protocol_id'] != PROTOCOL or not valid_limits(plan['limits'])
            or type(plan['precontext_s']) is not int or plan['precontext_s'] != PRECONTEXT):
        raise ValueError('plan identity/limits')
    auth_keys = {'protocol_id', 'offline_decode_authorized', 'plan_sha256', 'source_files', 'limits',
                 'pushed_source_commit', 'source_manifest_sha256', 'review_receipt_sha256', 'test_receipt_sha256',
                 'code_only_review_clean', 'focused_tests_passed', 'precontext_s','prerequisites',
                 'v5_terminal_accounting_complete','independent_v4_terminal_accounting_verified','parent_fixed_bindings_verified','transport_statuses_sha256'}
    if (not isinstance(auth, dict) or set(auth) != auth_keys or auth['protocol_id'] != PROTOCOL
            or auth['offline_decode_authorized'] is not True or auth['code_only_review_clean'] is not True
            or auth['focused_tests_passed'] is not True or auth['plan_sha256'] != args.plan_sha256
            or not valid_limits(auth['limits']) or auth['source_files'] != plan['source_files']
            or type(auth['precontext_s']) is not int or auth['precontext_s'] != PRECONTEXT
            or auth['prerequisites'] != plan['prerequisites']
            or any(auth[k] is not True for k in ('v5_terminal_accounting_complete','independent_v4_terminal_accounting_verified','parent_fixed_bindings_verified'))):
        raise ValueError('fresh parent authorization')
    validate_prerequisites(plan['prerequisites'])
    if plan['transport_statuses_sha256']!=args.transport_statuses_sha256 or auth['transport_statuses_sha256']!=args.transport_statuses_sha256:
        raise ValueError('trusted transport status pin mismatch')
    commit = auth['pushed_source_commit']
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('pushed source binding')
    for key in ('source_manifest_sha256', 'review_receipt_sha256', 'test_receipt_sha256'):
        if not valid_hash(auth[key]):
            raise ValueError('public proof binding')
    sources = plan['source_files']
    if not isinstance(sources, dict) or set(sources) != SOURCE_NAMES or any(not valid_hash(v) for v in sources.values()):
        raise ValueError('processing source allowlist')
    if (sources['core.py']!=CORE_SHA256 or sources['RUNTIME_PINS.json']!=RUNTIME_PINS_SHA256
            or sources['PUBLIC_TRANSPORT_PROPOSAL.md']!=PROPOSAL_SHA256
            or sources['PUBLIC_QUALIFICATION_PROPOSAL.md']!=QUALIFICATION_PROPOSAL_SHA256):
        raise ValueError('fixed scientific/proposal source pins')
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
    objects=[slot['components'][k] for slot in slots for k in COMPONENTS]
    statuses=[obj['transport_status'] for obj in objects]
    if any(statuses.count(k)!=v for k,v in TERMINAL_ACCOUNTING.items() if k!='horizontal_attempts') or status_digest(slots)!=args.transport_statuses_sha256:
        raise ValueError('six/two/four fixed transport mask')
    if len({obj['body_path'] for obj in objects}) != 12 or sum(obj['body_bytes'] for obj in objects) > TOTAL_BODY_CAP:
        raise ValueError('twelve distinct bounded bodies')
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
    # Verify every retained object, including error bodies, before any decode.
    # The decode pass rechecks each eligible body so a changed file cannot reuse
    # this first-pass proof; only one bounded object buffer is retained at a time.
    for slot in plan['slots']:
        for suffix in COMPONENTS:
            obj = slot['components'][suffix]
            body = bounded_read(obj['body_path'], BODY_CAP, args.deadline)
            if len(body) != obj['body_bytes'] or digest(body) != obj['body_sha256']:
                raise ValueError('cached body changed')
            validated_body_count += 1
            del body
    for slot in plan['slots']:
        components={}
        for suffix in COMPONENTS:
            check_deadline(args.deadline)
            obj=slot['components'][suffix]
            if obj['transport_status']=='unqualified_http404':
                components[suffix]=qualification.failed(slot['slot_index'],'transport_unqualified',obj['transport_status'])
                check_deadline(args.deadline)
                continue
            body = bounded_read(obj['body_path'], BODY_CAP, args.deadline)
            if len(body) != obj['body_bytes'] or digest(body) != obj['body_sha256']:
                raise ValueError('cached body changed')
            stream = None
            try:
                stream, count, warning_count = qualification.decode(body, read, 192_000_000-used_samples)
                used_samples += count
                flat={k:slot[k] for k in ('slot_index','t0_ns','pick_ns','filename_year','filename_doy')}
                flat.update(obj)
                row = qualification.analyze(stream, flat, core)
                row.update(advertised_samples=count, decode_warning_count=warning_count)
            except Exception as error:
                if isinstance(error, (MemoryError, TimeoutError)):
                    raise
                row = qualification.failed(slot['slot_index'], 'decode_or_grid_unsupported',obj['transport_status'])
            finally:
                del stream
            components[suffix]=row
            del body
            check_deadline(args.deadline)
        rows.append(qualification.make_slot(slot,components,core))
    result = {'protocol_id': PROTOCOL,
              'private': {'slots': rows, 'provenance': {'plan_sha256': args.plan_sha256,
                'authorization_sha256': args.authorization_sha256, 'source_files': plan['source_files'],
                'pushed_source_commit': auth['pushed_source_commit'], 'validated_body_count': validated_body_count,
                'advertised_samples_decoded': used_samples, 'precontext_s': plan['precontext_s'],
                'prerequisites':plan['prerequisites'],'transport_statuses_sha256':args.transport_statuses_sha256}},
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
                     'supervisor-sha256', 'runtime-sha256', 'runtime-path','transport-statuses-sha256'):
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
