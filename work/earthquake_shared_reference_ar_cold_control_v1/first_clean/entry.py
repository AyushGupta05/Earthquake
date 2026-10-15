"""ROOT starts this exact positively pinned source; no vendor imports here."""
import hashlib
import importlib.util
import json
import os
import stat
import sys
import time
import types


def read(spec):
    path = spec['path']; parts = path.split('/')[1:]
    assert path.startswith('/') and all(x not in ('', '.', '..') for x in parts)
    d = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in parts[:-1]:
            n = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=d)
            os.close(d); d = n
        f = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=d)
        try:
            before = os.fstat(f)
            assert stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == spec['mode'] and before.st_nlink == 1
            assert before.st_size == spec['pin']['bytes'] <= 2 * 1024 * 1024
            with os.fdopen(f, 'rb', closefd=False) as stream: raw = stream.read(before.st_size + 1)
            after = os.fstat(f)
            assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            assert len(raw) == spec['pin']['bytes'] and hashlib.sha256(raw).hexdigest() == spec['pin']['sha256']
            return raw
        finally: os.close(f)
    finally: os.close(d)


def load(spec, name):
    raw = read(spec); module = types.ModuleType(name)
    module.__file__ = spec['path']; module.__spec__ = importlib.util.spec_from_file_location(name, spec['path'])
    sys.modules[name] = module
    exec(compile(raw, spec['path'], 'exec'), module.__dict__)
    return module


def main(args):
    path, sha, size = args
    req = json.loads(read(dict(path=path, pin=dict(sha256=sha, bytes=int(size)), mode=0o400)))
    assert os.path.abspath(__file__) == req['entry']['path']; read(req['entry'])
    config = json.loads(read(req['config']))
    v6 = config['sources']['v6']; aliases = {}; modules = {}
    try:
        for name in ('secure_io', 'vendor_inventory', 'generated_source', 'metadata_finder', 'source_binding', 'systemd_adapter'):
            aliases[name] = sys.modules.get(name)
            spec = dict(path=v6['directory'] + '/' + name + '.py', pin=v6['files'][name + '.py'], mode=0o400)
            modules[name] = load(spec, 'eew_l_cold_manager_' + name); sys.modules[name] = modules[name]
    finally:
        for name, old in aliases.items():
            if old is None: sys.modules.pop(name, None)
            else: sys.modules[name] = old
    io, sb = modules['secure_io'], modules['source_binding']
    ad = config['sources']['adapter']
    adapter = load(dict(path=ad['directory'] + '/runtime_adapter.py', pin=ad['files']['runtime_adapter.py'], mode=0o400), 'eew_l_cold_preflight_adapter')
    control = load(req['controller'], 'eew_l_cold_controller')
    begin = time.monotonic()
    def check():
        control.need(time.monotonic() - begin < 120, 'readiness_preflight_expired')
        control.authority(req, io, time.time(), 1020)
    raws = {k: adapter._source(s, k, io, sb, check) for k, s in config['sources'].items()}
    adapter._injected(config, io, sb); adapter._copies(raws, io); adapter._roles(config, raws, io)
    sb.runtime(config['runtime'], check); check()
    assert not {'numpy', 'scipy', 'torch'} & set(sys.modules)
    bootstrap = config['sources']['bootstrap']
    assert req['caller'] == dict(path=bootstrap['directory'] + '/caller.py', pin=bootstrap['files']['caller.py'], mode=0o400)
    sdmod = modules['systemd_adapter']
    result = control.run(req, io=io, sd=sdmod.Systemd(req['commands']), process=sdmod.process, seconds=sdmod.seconds)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result['status'] == 'complete' else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
