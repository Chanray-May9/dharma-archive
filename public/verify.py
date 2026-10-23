import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError(f'Unsafe archive path: {name}')
    return path


def parse_manifest(content):
    records = []
    for line in content.splitlines():
        if not line.strip():
            continue
        digest, name = line.split('  ', 1)
        safe_path(name)
        if len(digest) != 64 or any(letter not in '0123456789abcdef' for letter in digest):
            raise ValueError('Invalid SHA-256 digest')
        records.append((digest, name))
    if len({name for digest, name in records}) != len(records):
        raise ValueError('Duplicate manifest entries')
    return records


def verify_zip(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError(f'Duplicate ZIP members: {path}')
        for name in names:
            safe_path(name)
        records = parse_manifest(archive.read('manifest-sha256.txt').decode('utf-8'))
        payload = {name for name in names if name.startswith('data/') and not name.endswith('/')}
        if payload != {name for digest, name in records}:
            raise ValueError(f'Incomplete ZIP manifest: {path}')
        for digest, name in records:
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError(f'Corrupt ZIP member: {path}: {name}')
    return len(records)


def verify_directory(root, deep=False, metadata_only=False):
    records = parse_manifest((root / 'manifest-sha256.txt').read_text(encoding='utf-8'))
    actual = {path.relative_to(root).as_posix() for path in (root / 'data').rglob('*') if path.is_file()}
    declared = {name for digest, name in records}
    missing = declared - actual
    permitted_missing = {name for name in missing if name.startswith('data/packages/') or (name.startswith('data/recovery/') and name.endswith('.par2')) or (name.startswith('data/upstream/') and '.part-' in name)}
    if actual - declared or (missing and (not metadata_only or missing != permitted_missing)):
        raise ValueError('Payload set differs from manifest')
    for digest, name in records:
        path = root.joinpath(*safe_path(name).parts)
        if metadata_only and name in permitted_missing:
            continue
        with path.open('rb') as stream:
            actual_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual_digest != digest:
            raise ValueError(f'Checksum mismatch: {name}')
        if deep and path.suffix == '.zip' and name.startswith('data/packages/'):
            verify_zip(path)
    catalog = json.loads((root / 'data/catalog.json').read_text(encoding='utf-8'))
    if isinstance(catalog, dict):
        catalog = [record for name in catalog['chunks'] for record in json.loads((root / name).read_text(encoding='utf-8'))]
    identifiers = [record['id'] for record in catalog]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('Duplicate catalog IDs')
    for record in catalog:
        for field in (('package_path',) if record.get('text_storage') == 'zip-member' else ('text_path', 'package_path')):
            path = root.joinpath(*safe_path(record[field]).parts)
            if metadata_only and record[field] in permitted_missing:
                continue
            if not path.is_file():
                raise ValueError(f'Missing catalog target: {record[field]}')
    status = json.loads((root / 'data/status.json').read_text(encoding='utf-8'))
    if status['documents'] != len(catalog):
        raise ValueError('Status count differs from catalog')
    return len(records) - len(permitted_missing) if metadata_only else len(records)


def main():
    parser = argparse.ArgumentParser(description='Offline, Python-standard-library archive verifier')
    parser.add_argument('path', type=Path)
    parser.add_argument('--deep', action='store_true')
    parser.add_argument('--metadata-only', action='store_true')
    args = parser.parse_args()
    count = verify_zip(args.path) if args.path.is_file() else verify_directory(args.path, args.deep, args.metadata_only)
    print(json.dumps({'ok': True, 'verified_files': count, 'scope': 'local_metadata_only' if args.metadata_only else 'all_payload_files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
