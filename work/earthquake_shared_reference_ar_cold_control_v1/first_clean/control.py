"""Once-only, source-only readiness control. No cloud action on import."""
import datetime
import hashlib
import json
import math
import os
import re
import stat
import time
import traceback

MODES = ('fixtures', 'independent', 'producer')
SOURCE = (120, 300, 300)
MANAGER = (180, 360, 360)
LIMITS = dict(memory=2147483648, swap=0, tasks=64, cpu_weight=10,
              threads=1, cuda_hidden=True, kill_mode='control-group', stop_seconds=5)
THREADS = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def serial(value):
    if isinstance(value, bytes):
        return dict(hex=value.hex(), pin=pin(value))
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


class Journal:
    """Exclusive private directory; bounded atomic files, no replacements."""
    def __init__(self, path, io):
        self.path, self.io = path, io
        parent, name = os.path.split(path)
        need(re.fullmatch('[a-zA-Z0-9_-]+', name), 'namespace')
        fd = io.directory(parent)
        try:
            os.mkdir(name, 0o700, dir_fd=fd)
            os.fsync(fd)
        finally:
            os.close(fd)
        self.fd = io.directory(path)
        st = os.fstat(self.fd)
        need(st.st_uid == os.geteuid() and stat.S_IMODE(st.st_mode) == 0o700, 'journal_owner')

    def write(self, name, value, raw=False):
        need(re.fullmatch('[a-zA-Z0-9_.-]+', name), 'basename')
        body = value if raw else canonical(serial(value))
        need(type(body) is bytes and len(body) <= 2 * 1024 * 1024, 'member_cap')
        total = 0
        for child in os.listdir(self.fd):
            st = os.stat(child, dir_fd=self.fd, follow_symlinks=False)
            need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and stat.S_IMODE(st.st_mode) == 0o400, 'journal_member')
            total += st.st_size
        need(total + len(body) <= 64 * 1024 * 1024, 'journal_cap')
        temp = '.' + name + '.partial'
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=self.fd)
        try:
            view = memoryview(body)
            while view:
                n = os.write(fd, view); need(n > 0, 'short_write'); view = view[n:]
            os.fchmod(fd, 0o400)
            if hasattr(os, 'fdatasync'):
                os.fdatasync(fd)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.link(temp, name, src_dir_fd=self.fd, dst_dir_fd=self.fd, follow_symlinks=False)
        os.unlink(temp, dir_fd=self.fd)
        os.fsync(self.fd)
        spec = dict(path=self.path + '/' + name, pin=pin(body), mode=0o400)
        need(self.io.read_file(spec, 2 * 1024 * 1024) == body, 'readback')
        return spec

    def close(self):
        os.close(self.fd)


def authority(request, io, wall, required_seconds=0):
    raw = io.read_file(request['gate'], 65536); gate = json.loads(raw)
    need(gate['schema'] == 'root-L-readiness-fresh-funding-resource-gate-v1'
         and gate['no_actual_L_fit_authority'] is True, 'gate_scope')
    expiry = datetime.datetime.fromisoformat(gate['bound_until_utc']).timestamp()
    checked = datetime.datetime.fromisoformat(gate['checked_utc']).timestamp()
    need(math.isfinite(wall) and checked <= wall and wall + required_seconds < expiry, 'gate_expired')
    return request['gate']['pin']


def props(answer, allow_absence=False):
    need(not answer['timeout'] and answer['streams_complete'], 'command_return')
    result = {}
    for line in answer['stdout'].decode().splitlines():
        need('=' in line, 'property_line')
        k, v = line.split('=', 1); need(k not in result, 'property_duplicate'); result[k] = v
    absent = (allow_absence and answer['code'] in (1, 4) and result in (
        dict(LoadState='not-found', ActiveState='inactive'),
        dict(LoadState='not-found', ActiveState='inactive', ControlGroup='')))
    need(answer['code'] == 0 or absent, 'command_return')
    return result


def timer_start(timer, service, service_name, stop_path, before, after, seconds):
    t, s = props(timer), props(service)
    need(t['ActiveState'] == 'active' and t['Unit'] == service_name and s['ActiveState'] == 'inactive', 'timer_state')
    matches = re.findall(r'OnActive(?:USec|Sec)=([^;]+)', t['TimersMonotonic'])
    need(len(matches) == 1 and seconds(matches[0].strip()) == 1000 and seconds(t['AccuracyUSec']) <= 1, 'timer_interval')
    argv = re.findall(r'argv\[\]=([^;]*)(?:;|$)', s['ExecStart'])
    need(len(argv) == 1 and argv[0].split() == ['/usr/bin/bash', stop_path], 'timer_command')
    start = int(t['ActiveEnterTimestampMonotonic']) / 1e6
    need(before <= start <= after, 'timer_activation')
    return start


def argv(request, config, control, mode, unit, manager):
    result = ['systemd-run', '--user', '--unit=' + unit[:-8], '--pipe', '--wait', '--setenv=CUDA_VISIBLE_DEVICES=']
    result += ['--setenv=' + name + '=1' for name in THREADS]
    for key, value in (('MemoryMax', 2147483648), ('MemorySwapMax', 0), ('TasksMax', 64),
                       ('CPUWeight', 10), ('CPUQuota', '100%'), ('RuntimeMaxSec', manager),
                       ('TimeoutStopSec', 5), ('KillMode', 'control-group')):
        result += ['-p', str(key) + '=' + str(value)]
    c = request['config']; p = control['pin']
    result += [config['runtime']['python'], '-I', '-B', request['caller']['path'], c['path'],
               c['pin']['sha256'], str(c['pin']['bytes']), control['path'], p['sha256'], str(p['bytes']), mode]
    return result


def report_ok(report, mode, source):
    need(report['schema'] == 'L-cold-source-readiness-v1' and report['mode'] == mode
         and report['scienceactual'] == 0 and report['status'] == 'complete', 'child_incomplete')
    need(type(report['seconds']) in (int, float) and math.isfinite(report['seconds'])
         and 0 <= report['seconds'] <= source, 'child_time')
    if mode == 'fixtures':
        need(report['tests'] == dict(run=19, errors=0, failures=0, skipped=0), 'fixtures')
    else:
        s = report['synthetic']
        need(s['status'] == 'complete' and s['scienceactual'] == 0 and s['mode'] == mode, 'synthetic')
        if mode == 'producer':
            need(s['synthetic_steps'] == 3, 'synthetic_steps')


def run(request, *, io, sd, process, seconds, clock=time.monotonic, wall=time.time):
    """Caller has positively bound this module, helpers and full source/runtime preflight."""
    need(request['schema'] == 'root-L-cold-control-request-v1', 'request_schema')
    ident = request['id']; need(re.fullmatch('[a-z0-9-]{1,40}', ident), 'id')
    units = {m: 'eew-marked-' + ident + '-%02d.service' % i for i, m in enumerate(MODES)}
    stop_service = 'eew-marked-' + ident + '-stop.service'; timer = stop_service[:-8] + '.timer'
    authority(request, io, wall(), 1020)
    need(request['bash']['path'] == '/usr/bin/bash'
         and request['commands']['systemctl']['path'] == '/usr/bin/systemctl', 'stop_executable_paths')
    config = json.loads(io.read_file(request['config']))
    io.read_file(request['caller']); io.read_file(request['bash'], 16 * 1024 * 1024)
    preflight = json.loads(io.read_file(request['preflight']))
    need(preflight['status'] == 'complete' and preflight['config_pin'] == request['config']['pin'], 'preflight')
    need(preflight['publication_ancestor'] == json.loads(io.read_file(request['gate']))['publication_commit'], 'publication')
    for unit in units.values():
        sd.own(unit); sd.available(unit)
    journal = Journal(request['namespace'], io)
    report = dict(schema='root-L-cold-readiness-return-v1', status='incomplete', scienceactual=0,
                  excluded=('bridge', 'comparator', 'L9_actual_input_binding'), stages=[], cleanup=[])
    whole = None; timer_attempted = False

    def command(key, args, timeout=5):
        spec = request['commands'][key]; io.read_file(spec, 16 * 1024 * 1024)
        return process([spec['path']] + args, timeout)

    def show(unit, fields):
        return command('systemctl', ['--user', 'show', unit, '--property=' + ','.join(fields)])

    def closed(unit):
        answer = show(unit, ('LoadState', 'ActiveState', 'ControlGroup'))
        journal.write(unit.replace('.', '_') + '_closure_' + str(len(report['cleanup'])) + '.json', answer)
        value = props(answer, allow_absence=True)
        need(value['ActiveState'] in ('inactive', 'failed') and value['ControlGroup'] == '', 'unit_not_empty')
        report['cleanup'].append(dict(unit=unit, properties=value))

    try:
        for unit in (stop_service, timer):
            fields = ('LoadState', 'ActiveState') if unit.endswith('.timer') else ('LoadState', 'ActiveState', 'ControlGroup')
            answer = show(unit, fields); journal.write('absence_' + unit.rsplit('.', 1)[1] + '.json', answer)
            expected = dict(LoadState='not-found', ActiveState='inactive')
            if unit.endswith('.service'): expected['ControlGroup'] = ''
            need(props(answer, allow_absence=True) == expected, 'stop_namespace_in_use')
        stop_body = ('#!/usr/bin/bash\nPATH=/usr/bin:/bin\nexport PATH\nstatus=0\n' + ''.join(
            '/usr/bin/systemctl --user stop ' + u + '\nif [ "$?" -ne 0 ]; then status=1; fi\n'
            for u in units.values()) + 'exit "$status"\n').encode()
        stop = journal.write('stop.sh', stop_body, raw=True)
        journal.write('request.private.json', request)
        before = clock(); authority(request, io, wall(), 1020); timer_attempted = True
        install = command('systemd_run', ['--user', '--unit=' + stop_service[:-8], '--on-active=1000s',
                         '--timer-property=AccuracySec=1s', '--property=Type=oneshot',
                         '--property=TimeoutStartSec=60', '/usr/bin/bash', stop['path']], 10)
        journal.write('timer_install.json', install); need(install['code'] == 0 and install['streams_complete'] and not install['timeout'], 'timer_install')
        timer_raw = show(timer, ('ActiveState', 'Unit', 'AccuracyUSec', 'TimersMonotonic', 'ActiveEnterTimestampMonotonic'))
        service_raw = show(stop_service, ('ActiveState', 'ExecStart'))
        journal.write('timer_readback.json', dict(timer=timer_raw, service=service_raw))
        whole = timer_start(timer_raw, service_raw, stop_service, stop['path'], before, clock(), seconds)
        report['whole_begin'] = whole
        control = journal.write('control.private.json', dict(units=units, commands=request['commands'], whole_begin=whole, limits=LIMITS))
        for index, mode in enumerate(MODES):
            authority(request, io, wall(), MANAGER[index] + 10)
            need(clock() + MANAGER[index] + 15 <= whole + 1000, 'whole_remaining')
            sd.available(units[mode]); io.read_file(request['caller'])
            claim = journal.write(mode + '_claim.json', dict(mode=mode, ordinal=index, source=SOURCE[index], manager=MANAGER[index], config=request['config']['pin']))
            started = clock(); result = sd.run(argv(request, config, control, mode, units[mode], MANAGER[index]), MANAGER[index], units[mode])
            elapsed = clock() - started
            journal.write(mode + '_manager.json', result)
            entry = dict(mode=mode, claim=claim, manager_seconds=elapsed); report['stages'].append(entry)
            closed(units[mode])
            need(result['code'] == 0 and result['streams_complete'] and not result['timeout'], 'manager_return')
            output = json.loads(result['stdout'])
            expected_path = request['namespace'] + '/' + mode + '_report.private.json'
            need(output['report_path'] == expected_path, 'report_path')
            spec = dict(path=expected_path, pin=output['report_pin'], mode=0o400)
            child = json.loads(io.read_file(spec, 1024 * 1024)); os.fsync(journal.fd)
            entry['report'] = spec; report_ok(child, mode, SOURCE[index])
            need(elapsed <= SOURCE[index] and clock() <= whole + 1000, 'late_source_return')
            authority(request, io, wall())
        report['status'] = 'complete'
    except BaseException as exc:
        report['failure'] = dict(reason=type(exc).__name__ + ':' + str(exc), traceback=traceback.format_exc())
    finally:
        # Preserve the scientific/transport outcome BEFORE cleanup and late checks.
        try:
            journal.write('outcome_before_cleanup.json', report)
        except BaseException as exc:
            report['status'] = 'incomplete'; report['retention_failure'] = type(exc).__name__ + ':' + str(exc)
        for unit in units.values():
            try:
                answer = command('systemctl', ['--user', '--no-block', 'stop', unit], 5)
                journal.write(unit.replace('.', '_') + '_stop.json', answer)
                closed(unit)
            except BaseException as exc:
                report['status'] = 'incomplete'; report.setdefault('cleanup_errors', []).append(type(exc).__name__ + ':' + str(exc))
        # The independent whole-run stop remains armed if ANY service's
        # inactive/empty closure could not be positively established.
        if timer_attempted and not report.get('cleanup_errors'):
            try:
                answer = command('systemctl', ['--user', 'stop', timer, stop_service], 10)
                journal.write('timer_stop.json', answer)
                need(answer['code'] == 0 and answer['streams_complete'] and not answer['timeout'], 'timer_stop')
                for unit in (timer, stop_service):
                    fields = ('LoadState', 'ActiveState') if unit.endswith('.timer') else ('LoadState', 'ActiveState', 'ControlGroup')
                    answer = show(unit, fields); journal.write('final_' + unit.rsplit('.', 1)[1] + '.json', answer)
                    value = props(answer, allow_absence=True)
                    need(value['ActiveState'] == 'inactive' and (unit.endswith('.timer') or value['ControlGroup'] == ''), 'timer_not_closed')
            except BaseException as exc:
                report['status'] = 'incomplete'; report.setdefault('cleanup_errors', []).append(type(exc).__name__ + ':' + str(exc))
        elif timer_attempted:
            report['timer_retained_for_unverified_cleanup'] = True
        report['whole_seconds'] = None if whole is None else clock() - whole
        try:
            authority(request, io, wall())
        except BaseException as exc:
            report['status'] = 'incomplete'; report['final_authority_failure'] = str(exc)
        if whole is None or clock() > whole + 1000:
            report['status'] = 'incomplete'; report['late'] = True
        final = journal.write('final_report.json', report)
        # A finalization crossing expiry cannot silently leave a passing receipt.
        if whole is not None and clock() > whole + 1000:
            report['status'] = 'incomplete'; journal.write('late_after_finalization.json', dict(status='incomplete', final=final, whole_seconds=clock()-whole))
        journal.close()
    return dict(status=report['status'], final_report=final, scienceactual=0)
