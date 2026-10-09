"""Immutable run directories with complete configuration and source identity."""
import hashlib
import json
from pathlib import Path
import uuid


def create_run(parent, label, config, sources=()):
    """Never reuse a directory, even for an identical configuration/seed.

    The digest identifies configuration and code, while the random suffix
    separates repeated executions. Repeated seeds are not independent seeds.
    """
    sources = [Path(p) for p in sources]
    manifest = {'config': config, 'source_sha256': {
        str(p.name): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    canonical = json.dumps(manifest, sort_keys=True, allow_nan=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:12]
    destination = Path(parent) / f'{label}_{digest}_{uuid.uuid4().hex[:12]}'
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'identity.json').write_text(canonical + '\n')
    return destination
