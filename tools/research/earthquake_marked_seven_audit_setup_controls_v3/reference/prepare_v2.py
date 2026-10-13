"""ROOT-only metadata/control assembly. Never call without fresh ROOT authority.

No scientific imports, fit dispatch, artifact decode, SSH, Git or dependency
installation. This file is authored without executing prepare(). ROOT supplies
positively pinned source/runtime/publication/cost evidence, then explicitly calls
prepare(request). Existing directories and units are terminal: no retry/replace.
"""
import hashlib
import json
import math
import os
from pathlib import PurePosixPath
import re
import stat
import subprocess
import time
from datetime import datetime, timezone
from decimal import Decimal

AUDIT_ID = 'shared-noise-audit-v2-20261013'
STUDY = 'earthquake-TRAIN115-marked-noise-fitting-v2'
BASE = '/home/ec2-user/eew-marked-seven-audit-v2-20261013'
ROLES = {'v6', 'native', 'auditor', 'wrapper', 'input_adapter', 'harness'}
LIMITS = dict(memory=2147483648, swap=0, tasks=64, cpu_weight=10,
              threads=1, cuda_hidden=True, kill_mode='control-group', stop_seconds=5)
ENVELOPE = 7 * 64 * 1024 * 1024
VALID_UNTIL = '2026-10-14T04:00:00Z'
EXPIRY = '2026-10-31T00:00:00Z'
SERVICES = ['Amazon Elastic Compute Cloud', 'AWS Data Transfer', 'Amazon Virtual Private Cloud']
REQUEST_KEYS = {'schema', 'static_receipt', 'source_profile', 'hooks_source',
                'protocol', 'source_proof', 'runtime_proof', 'linux_proofs',
                'published_proof', 'source_commit', 'credit_proof',
                'resource_observation', 'cost_bound_proof',
                'task_spend_upper_bound_usd', 'task_bound_until_utc',
                'uncertainty_reserve_usd', 'other_reservations_usd', 'commands', 'bash'}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def utc(value):
    need(type(value) is str, 'UTC type')
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(d.tzinfo is not None, 'UTC timezone')
    return d.timestamp()


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def amount(value):
    need(type(value) in (str, int, float), 'money type')
    result = Decimal(str(value))
    need(result.is_finite() and result >= 0 and result.as_tuple().exponent >= -2, 'money cents')
    return result


def directory(path):
    """Open every existing ancestor without following a symlink."""
    need(type(path) is str and path.startswith('/') and str(PurePosixPath(path)) == path
         and '..' not in PurePosixPath(path).parts, 'canonical path')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in PurePosixPath(path).parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read(spec, cap=16 * 1024 * 1024):
    need(type(spec) is dict and set(spec) == {'path', 'pin', 'mode'}, 'file spec')
    need(type(spec['pin']) is dict and set(spec['pin']) == {'bytes', 'sha256'}
         and type(spec['pin']['bytes']) is int and 0 <= spec['pin']['bytes'] <= cap
         and re.fullmatch('[0-9a-f]{64}', spec['pin']['sha256']), 'file pin')
    p = PurePosixPath(spec['path']); parent = directory(str(p.parent))
    try:
        fd = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == spec['mode']
                 and before.st_nlink == 1 and before.st_size <= cap, 'regular mode size')
            chunks = []; total = 0
            while total <= cap:
                chunk = os.read(fd, min(65536, cap + 1 - total))
                if not chunk:
                    break
                total += len(chunk); chunks.append(chunk)
            after = os.fstat(fd); raw = b''.join(chunks)
            need((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                 (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                 and pin(raw) == spec['pin'], 'stable pinned bytes')
            return raw
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def obj(spec, cap=16 * 1024 * 1024):
    return json.loads(read(spec, cap))


def make_new(path):
    p = PurePosixPath(path); fd = directory(str(p.parent))
    try:
        os.mkdir(p.name, 0o700, dir_fd=fd)  # exclusive; never repair old state
        os.fsync(fd)
    finally:
        os.close(fd)
    result = directory(path)
    st = os.fstat(result)
    need(st.st_uid == os.geteuid() and stat.S_IMODE(st.st_mode) == 0o700, 'new owner/mode')
    return result


def put(fd, base, name, value, raw=False):
    need(re.fullmatch('[a-zA-Z0-9_.-]+', name), 'new basename')
    b = value if raw else canonical(value)
    need(type(b) is bytes and len(b) <= 2 * 1024 * 1024, 'control cap')
    f = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=fd)
    try:
        view = memoryview(b)
        while view:
            written = os.write(f, view); need(written > 0, 'short write'); view = view[written:]
        os.fchmod(f, 0o400)
        if hasattr(os, 'fdatasync'):
            os.fdatasync(f)
        os.fsync(f)
    finally:
        os.close(f)
    os.fsync(fd)
    s = dict(path=base + '/' + name, pin=pin(b), mode=0o400)
    need(read(s, 2 * 1024 * 1024) == b, 'control readback')
    return s


def properties(raw):
    need(type(raw) is str and len(raw) <= 65536, 'systemctl properties cap')
    out = {}
    for line in raw.splitlines():
        need('=' in line, 'property syntax')
        k, v = line.split('=', 1); need(k not in out, 'duplicate property'); out[k] = v
    return out


def duration(raw):
    p = re.findall(r'([0-9]+(?:\.[0-9]+)?)(h|min|s|ms|us)', raw)
    need(p and ''.join(n + u for n, u in p) == raw.replace(' ', ''), 'duration syntax')
    return sum(Decimal(n) * {'h': Decimal(3600), 'min': Decimal(60), 's': Decimal(1),
                            'ms': Decimal('.001'), 'us': Decimal('.000001')}[u] for n, u in p)


def stop_body(units):
    need(units == ['eew-marked-' + AUDIT_ID + '-%02d.service' % i for i in range(7)], 'stop units')
    # Do not use set -e: all seven stops must be attempted even if one is absent.
    return ('#!/usr/bin/bash\nPATH=/usr/bin:/bin\nexport PATH\nstatus=0\n' + ''.join(
        'systemctl --user stop ' + unit + '\nif [ "$?" -ne 0 ]; then status=1; fi\n'
        for unit in units) + 'exit "$status"\n').encode()


def check_timer(timer_raw, service_raw, service, stop_path, before, after):
    t, s = properties(timer_raw), properties(service_raw)
    need(t['ActiveState'] == 'active' and t['Unit'] == service
         and duration(t['AccuracyUSec']) <= 1 and s['ActiveState'] == 'inactive', 'installed stop state')
    intervals = re.findall(r'OnActive(?:USec|Sec)=([^;]+)', t['TimersMonotonic'])
    need(len(intervals) == 1 and duration(intervals[0].strip()) == 7400, '7400 timer')
    argv = re.findall(r'argv\[\]=([^;]*)(?:;|$)', s['ExecStart'])
    need(len(argv) == 1 and argv[0].split() == ['/usr/bin/bash', stop_path], 'stop argv')
    need(re.fullmatch('[0-9]+', t['ActiveEnterTimestampMonotonic']), 'timer monotonic timestamp')
    started = int(t['ActiveEnterTimestampMonotonic']) / 1e6
    need(before <= started <= after, 'timer activation in observed interval')
    return started


def funding(request, raw_credit, wall):
    need(raw_credit['schema'] == 'eligible-AWS-main-credit-live-UI-proof-v1'
         and raw_credit['main_credit_status'] == 'Active'
         and raw_credit['main_credit_expiry'] == '2026-10-31'
         and raw_credit['eligible_services'] == SERVICES, 'eligible credit')
    for k in ('account_shared', 'estimated_amounts_delayed_24_hours',
              'settled_incremental_task_spend_unknown', 'same_account_default_cli_credentials_refreshed'):
        need(raw_credit[k] is True, 'raw credit semantics')
    need(raw_credit['credit_reserved_by_provider'] is False
         and raw_credit['authorized_credit_only_ceiling_usd'] == 2000
         and raw_credit['conservative_task_reservation_usd'] == 335, 'fixed authority')
    spend = amount(request['task_spend_upper_bound_usd'])
    balance = amount(raw_credit['main_credit_estimated_remaining_usd'])
    uncertainty = amount(request['uncertainty_reserve_usd'])
    other = amount(request['other_reservations_usd']); lower = balance - uncertainty - other
    need(spend < 335 and uncertainty >= 1500 and lower >= 2000 - spend
         and amount(raw_credit['total_estimated_remaining_usd']) >= balance, 'remaining credit coverage')
    need(utc(raw_credit['checked_utc']) <= wall < utc(VALID_UNTIL) <= utc(EXPIRY)
         and utc(request['task_bound_until_utc']) >= utc(VALID_UNTIL), 'financial/cost validity')
    # All amounts derive from pinned ROOT evidence and explicit ROOT cost authority.
    return dict(schema='root-marked-funding-proof-v1', credits_only=True, main_active=True,
                services=['EC2', 'VPC', 'DataTransfer'], ceiling_usd='2000', reservation_usd='335',
                task_spend_upper_bound_usd=str(spend), estimated_balance_usd=str(balance),
                uncertainty_reserve_usd=str(uncertainty), other_reservations_usd=str(other),
                unreserved_lower_bound_usd=str(lower), checked_utc=raw_credit['checked_utc'],
                valid_until_utc=VALID_UNTIL, credit_expiry_utc=EXPIRY, raw_proof=request['credit_proof'])


def closed_sources(sources):
    need(set(sources) == ROLES, 'six roles')
    for role, s in sources.items():
        need(set(s) == {'directory', 'files', 'manifest', 'upload_manifest'}, 'role shape')
        expected = set(s['files']); expected_dirs = set()
        for name, p in s['files'].items():
            n = PurePosixPath(name)
            need(not n.is_absolute() and str(n) == name and '..' not in n.parts, 'source relative path')
            expected_dirs.update(str(x) for x in n.parents if str(x) != '.')
            read(dict(path=s['directory'] + '/' + name, pin=p, mode=0o400))
        if s['upload_manifest'] is not None:
            u = s['upload_manifest']; need(u['path'] == s['directory'] + '/parent_upload_manifest.private.json'
                                           and obj(u) == s['files'], 'upload manifest')
            expected.add('parent_upload_manifest.private.json')
        found_files, found_dirs = set(), set()
        def walk(path, relative=''):
            fd = directory(path)
            try:
                for name in os.listdir(fd):
                    rel = relative + name; st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISDIR(st.st_mode):
                        found_dirs.add(rel); walk(path + '/' + name, rel + '/')
                    else:
                        need(stat.S_ISREG(st.st_mode), 'source symlink/special'); found_files.add(rel)
            finally:
                os.close(fd)
        walk(s['directory'])
        need(found_files == expected and found_dirs == expected_dirs, 'closed source inventory')
        rel = s['manifest']['path'][len(s['directory']) + 1:]
        need(s['manifest']['path'] == s['directory'] + '/' + rel
             and rel in s['files'] and s['files'][rel] == s['manifest']['pin'], 'role manifest')
        read(s['manifest'])


def prepare(request):
    """ROOT executes once on the original worker, after all source staging.

    Request is externally positive-pinned by ROOT. All named proof inputs are
    already readonly files on that host. Runtime/source proof creation is NOT
    this function's responsibility. It never opens numerical artifact bodies.
    """
    need(set(request) == REQUEST_KEYS and request['schema'] == 'root-marked-seven-audit-setup-input-v2', 'request schema')
    need(re.fullmatch('[0-9a-f]{40}', request['source_commit']), 'published commit')
    static = obj(request['static_receipt'], 2 * 1024 * 1024)
    need(static['schema'] == 'root-marked-audit-static-input-preparation-v1'
         and static['new_audit_clock_started'] is False, 'static preparation')
    original = obj(static['original_config']); need(pin(canonical(original)) == static['original_config_pin'], 'original config pin')
    need(original['authority_config'] == static['original_authority'], 'original authority binding')
    for key in ('bundle_template_spec', 'original_execution_spec', 'original_authority'):
        read(static[key])
    sources = obj(request['source_profile']); closed_sources(sources)
    subjects = {role: s['manifest']['pin'] for role, s in sources.items()}
    runtime = original['runtime']; runtime_pin = pin(canonical(runtime))
    for key in ('hooks_source', 'protocol', 'published_proof', 'resource_observation', 'cost_bound_proof'):
        need(bool(read(request[key])), 'empty ROOT evidence')
    source = obj(request['source_proof']); runtime_proof = obj(request['runtime_proof'])
    for proof in (source, runtime_proof):
        need(proof['schema'] == 'root-seven-audit-source-runtime-proof-v1'
             and proof['status'] == 'pass' and proof['source_manifest_pins'] == subjects, 'ROOT source/runtime evidence')
    need(source['hooks_source_pin'] == request['hooks_source']['pin']
         and source['protocol_pin'] == request['protocol']['pin']
         and runtime_proof['runtime_subject_pin'] == runtime_pin, 'ROOT proof subjects')
    need(type(request['linux_proofs']) is list and request['linux_proofs'], 'target receipts')
    for spec in request['linux_proofs']:
        p = obj(spec)
        need(p['status'] == 'pass' and all(type(p[x]) is int and p[x] == 0 for x in ('skip', 'fail', 'error'))
             and p['source_manifest_pins'] == subjects and p['runtime_subject_pin'] == runtime_pin
             and p['hooks_source_pin'] == request['hooks_source']['pin'], 'exact target receipt')
    commands = request['commands']; need(set(commands) == {'systemctl', 'systemd_run'}, 'commands')
    for name, path in (('systemctl', '/usr/bin/systemctl'), ('systemd_run', '/usr/bin/systemd-run')):
        need(commands[name]['path'] == path, 'command path'); read(commands[name])
    need(request['bash']['path'] == '/usr/bin/bash', 'bash path'); read(request['bash'])
    fund = funding(request, obj(request['credit_proof']), time.time())
    units = ['eew-marked-' + AUDIT_ID + '-%02d.service' % i for i in range(7)]
    stop_service = 'eew-marked-' + AUDIT_ID + '-whole-stop.service'
    stop_timer = stop_service[:-8] + '.timer'
    paths = dict(control=BASE + '-control', store=BASE + '-store', evidence=BASE + '-root-evidence')
    # Namespace absence is checked before any new directory or timer is created.
    for path in paths.values():
        need(not os.path.lexists(path), 'existing terminal audit namespace')
    def call(args, timeout=15, codes=(0,)):
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
        need(len(result.stdout) <= 65536 and len(result.stderr) <= 65536, 'bounded systemd output')
        need(result.returncode in codes, 'systemd command return')
        return dict(argv=args, returncode=result.returncode, stdout=result.stdout.decode(), stderr=result.stderr.decode())
    absence = []
    for unit in units + [stop_service, stop_timer]:
        observation = call([commands['systemctl']['path'], '--user', 'show', unit,
                            '--property=LoadState,ActiveState,ControlGroup'], codes=(0, 1, 4))
        p = properties(observation['stdout'])
        need(p.get('LoadState') == 'not-found' and p.get('ActiveState') == 'inactive'
             and p.get('ControlGroup', '') == '', 'existing audit unit')
        absence.append(observation)
    fds = {}; armed = False
    try:
        for key, path in paths.items():
            fds[key] = make_new(path)
        fd = fds['control']
        put(fd, paths['control'], 'setup_request.private.json', request)
        put(fd, paths['control'], 'preexisting_units.private.json', absence)
        space = os.fstatvfs(fds['store']); need(space.f_bavail * space.f_frsize >= ENVELOPE + 64 * 1024 * 1024, 'disk envelope')
        publication = dict(schema='root-seven-audit-publication-proof-v1', source_commit=request['source_commit'],
                           source_manifest_pins=subjects, runtime_subject_pin=runtime_pin,
                           hooks_source_pin=request['hooks_source']['pin'], protocol_pin=request['protocol']['pin'],
                           linux_proofs=request['linux_proofs'], published_proof=request['published_proof'])
        ps = put(fd, paths['control'], 'publication.private.json', publication)
        fs = put(fd, paths['control'], 'funding.private.json', fund)
        body = stop_body(units)
        stop_spec = put(fd, paths['control'], 'whole-stop.sh', body, raw=True)
        before = time.monotonic()
        installed = call([commands['systemd_run']['path'], '--user', '--unit=' + stop_service[:-8],
                          '--on-active=7400s', '--timer-property=AccuracySec=1s',
                          '--property=Type=oneshot', '--property=TimeoutStartSec=60',
                          '/usr/bin/bash', stop_spec['path']])
        armed = True
        put(fd, paths['control'], 'timer_install.private.json', installed)
        timer = call([commands['systemctl']['path'], '--user', 'show', stop_timer,
                      '--property=ActiveState,Unit,AccuracyUSec,TimersMonotonic,ActiveEnterTimestampMonotonic'])
        service = call([commands['systemctl']['path'], '--user', 'show', stop_service, '--property=ActiveState,ExecStart'])
        observed = time.monotonic()
        installed_begin = check_timer(timer['stdout'], service['stdout'], stop_service, stop_spec['path'], before, observed)
        # Begin after staging and observed timer installation. UTC upper mapping
        # uses wall-after-monotonic plus rounding/slack; it never lengthens mono lease.
        whole_begin = time.monotonic(); wall = time.time(); lease_end = whole_begin + 7190
        need(whole_begin - installed_begin < 120 and lease_end <= installed_begin + 7400, 'fresh whole/stop coverage')
        lease_utc = stamp(math.ceil(wall + 7192))
        automatic_stop_utc = stamp(math.ceil(wall + installed_begin + 7400 - whole_begin + 2))
        need(utc(lease_utc) < utc(automatic_stop_utc) <= utc(VALID_UNTIL)
             and utc(automatic_stop_utc) <= utc(request['task_bound_until_utc']), 'UTC stop/cost coverage')
        boot_path = '/proc/sys/kernel/random/boot_id'
        bfd = os.open(boot_path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            bst = os.fstat(bfd); boot = os.read(bfd, 129)
            need(stat.S_IMODE(bst.st_mode) == 0o444 and len(boot) <= 128, 'kernel boot')
        finally:
            os.close(bfd)
        boot_spec = dict(path=boot_path, pin=pin(boot), mode=0o444)
        raw_control = dict(schema='root-seven-audit-installed-stop-raw-v1', approved_units=units,
                           commands=commands, boot_id_sha256=pin(boot)['sha256'],
                           installed_begin_monotonic=installed_begin, automatic_stop_utc=automatic_stop_utc,
                           observedraw_systemctl_timer=timer['stdout'], observedraw_service=service['stdout'],
                           service_unit=stop_service, exec_argv=['/usr/bin/bash', stop_spec['path']],
                           stop_script=stop_spec, expected_stop_script=body.decode())
        raw_spec = put(fd, paths['control'], 'installed_stop.private.json', raw_control)
        resource = dict(schema='root-seven-audit-resource-proof-v1', source_manifest_pins=subjects,
                        runtime_subject_pin=runtime_pin, funding_pin=fs['pin'], publication_pin=ps['pin'],
                        protocol_pin=request['protocol']['pin'], hooks_source_pin=request['hooks_source']['pin'],
                        binding_sha256=static['binding_sha256'], whole_begin=whole_begin, lease_deadline=lease_end,
                        commands=commands, approved_units=units, limits=LIMITS, whole_seconds=7200,
                        closure_seconds=200, disk_directory=paths['store'], disk_reservation_bytes=ENVELOPE,
                        cost_deadline_monotonic=whole_begin + utc(request['task_bound_until_utc']) - wall,
                        automatic_stop_utc=automatic_stop_utc, boot_id_sha256=pin(boot)['sha256'], raw_control_proof=raw_spec,
                        root_resource_observation=request['resource_observation'], root_cost_bound=request['cost_bound_proof'])
        rs = put(fd, paths['control'], 'resource.private.json', resource)
        hooks = dict(schema='root-marked-seven-audit-hooks-config-v1', funding=fs, resource=rs, publication=ps,
                     boot_id=boot_spec, lease=dict(issued=whole_begin, expires=lease_end,
                                                  expires_utc=lease_utc, boot_id_sha256=pin(boot)['sha256']),
                     original_config=static['original_config'], original_authority=static['original_authority'],
                     original_execution=static['original_execution_spec'], last_return_evidence_directory=paths['evidence'],
                     source_proof=request['source_proof'], runtime_proof=request['runtime_proof'])
        hs = put(fd, paths['control'], 'hooks_config.private.json', hooks)
        config = dict(schema='marked-seven-audit-deployment-v1', audit_id=AUDIT_ID, study=STUDY,
                      feature_schema='earthquake-TRAIN115-marked-noise-observations-v1',
                      feature_study='earthquake-TRAIN115-marked-noise-study-v1', whole_begin=whole_begin,
                      lease_deadline=lease_end, binding_sha256=static['binding_sha256'],
                      wrapper_binding_sha256=static['wrapper_binding_sha256'], sources=sources, runtime=runtime,
                      bundle_template=static['bundle_template_spec'], publication=ps, protocol=request['protocol'],
                      hooks_source=request['hooks_source'], hooks_config=hs, commands=commands,
                      store_directory=paths['store'], storage_limit_bytes=ENVELOPE)
        cs = put(fd, paths['control'], 'deployment_config.private.json', config)
        receipt = dict(schema='root-marked-seven-audit-control-preparation-v2', status='prepared', audit_id=AUDIT_ID,
                       config_spec=cs, config_canonical_pin=pin(canonical(config)), control_directory=paths['control'],
                       store_directory=paths['store'], last_return_evidence_directory=paths['evidence'],
                       source_manifest_pins=subjects, runtime_subject_pin=runtime_pin, hooks_source_spec=request['hooks_source'],
                       bundle_template_spec=static['bundle_template_spec'], whole_begin=whole_begin, lease_deadline=lease_end,
                       whole_stop_timer=stop_timer, whole_stop_service=stop_service, raw_control_spec=raw_spec,
                       publication_spec=ps, source_commit=request['source_commit'], automatic_stop_utc=automatic_stop_utc,
                       no_audit_invoked=True)
        put(fd, paths['control'], 'preparation_receipt.private.json', receipt)
        need(time.monotonic() + 960 <= lease_end and time.time() < utc(lease_utc), 'late preparation')
        return receipt
    except BaseException as exc:
        # Preserve partial setup; do not stop an installed safety timer or retry.
        if 'control' in fds:
            try:
                put(fds['control'], paths['control'], 'setup_failure.private.json',
                    dict(status='incomplete', type=type(exc).__name__, reason=str(exc)[:512],
                         audit_id=AUDIT_ID, timer_install_returned_success=armed, no_audit_invoked=True, no_retry=True))
            except Exception:
                pass
        raise
    finally:
        for fd in fds.values():
            os.close(fd)


# Deliberately no __main__ path. ROOT must positively load these exact source
# bytes and explicitly call prepare with an independently pinned request.
