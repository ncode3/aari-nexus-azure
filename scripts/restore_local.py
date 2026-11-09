"""Restore a trusted backup into a NEW directory, validating every byte first."""
import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.backup_local import database_counts


def restore(source, destination):
    source, destination = Path(source), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('Recovery requires a new directory; live data is never overwritten')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary) / 'verified'
        staging.mkdir()
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or 'manifest.json' not in names:
                raise ValueError('Duplicate members or missing recovery manifest')
            for item in archive.infolist():
                path = PurePosixPath(item.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in item.filename or ':' in item.filename or
                        item.filename not in {'nexus_memory.sqlite3', 'manifest.json'} and not item.filename.startswith('artifacts/') or
                        stat.S_ISLNK(item.external_attr >> 16) or item.file_size > 256 * 1024 * 1024):
                    raise ValueError('Unsafe backup member')
            if sum(item.file_size for item in archive.infolist()) > 1024 * 1024 * 1024:
                raise ValueError('Recovery archive exceeds the operator-state limit')
            manifest = json.loads(archive.read('manifest.json'))
            if manifest.get('version') != 1 or set(names) != set(manifest['files']) | {'manifest.json'}:
                raise ValueError('Recovery manifest does not match archive')
            for name, expected in manifest['files'].items():
                content = archive.read(name)
                if len(content) != expected['bytes'] or hashlib.sha256(content).hexdigest() != expected['sha256']:
                    raise ValueError('Recovery checksum mismatch')
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        if database_counts(staging / 'nexus_memory.sqlite3') != manifest['counts']:
            raise ValueError('Recovered record counts differ from manifest')
        os.rename(staging, destination)
        return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    result = restore(args.source, args.destination)
    print(json.dumps({'counts': result['counts'], 'files': len(result['files']), 'verified': True}))
