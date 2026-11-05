"""Consistent SQLite snapshot plus artifacts. Stop the bot for a matched snapshot."""
import argparse
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def backup(data: Path, destination: Path):
    database = data / 'nexus_memory.sqlite3'
    if not database.is_file():
        raise ValueError('Memory database does not exist; no backup created')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / database.name
        with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as source, \
                sqlite3.connect(snapshot) as target:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite integrity check failed')
        # Exclusive creation prevents overwriting an earlier backup.
        with destination.open('xb') as output:
            destination.chmod(0o600)
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot, database.name)
                for artifact in (data / 'artifacts').rglob('*'):
                    if artifact.is_file() and not artifact.is_symlink():
                        archive.write(artifact, artifact.relative_to(data))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--data', type=Path, default=Path('data'))
    args = parser.parse_args()
    backup(args.data, args.destination)
