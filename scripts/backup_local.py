"""Offline, checksummed SQLite + attachments snapshot. Never overwrites a backup."""
import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.local_lock import FileLease


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def database_counts(database):
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
        return {table: conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                for table in ('memories', 'action_packages')}


def backup(data: Path, destination: Path):
    data, destination = Path(data).resolve(), Path(destination).resolve()
    database = data / 'nexus_memory.sqlite3'
    if not database.is_file() or database.is_symlink():
        raise ValueError('Memory database does not exist or is a link')
    if destination.is_relative_to(data):
        raise ValueError('Backups must be outside the live data directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with FileLease(data / 'runtime.lock'), tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / database.name
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
        files = {database.name: snapshot}
        artifacts = data / 'artifacts'
        if artifacts.is_symlink():
            raise ValueError('Linked artifact directory cannot be backed up')
        for artifact in artifacts.rglob('*'):
            if artifact.is_symlink() or not artifact.resolve().is_relative_to(data):
                raise ValueError('Linked artifacts cannot be backed up')
            if artifact.is_file():
                files[artifact.relative_to(data).as_posix()] = artifact
        manifest = {'version': 1, 'created_at': datetime.now(UTC).isoformat(),
                    'counts': database_counts(snapshot),
                    'files': {name: {'sha256': sha256(path), 'bytes': path.stat().st_size}
                              for name, path in files.items()}}
        with destination.open('xb') as output:
            destination.chmod(0o600)
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name, path in files.items():
                    archive.write(path, name)
                archive.writestr('manifest.json', json.dumps(manifest, indent=2))
        return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--data', type=Path, default=Path('data'))
    args = parser.parse_args()
    result = backup(args.data, args.destination)
    print(json.dumps({'counts': result['counts'], 'files': len(result['files'])}))
