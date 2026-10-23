import argparse
import json
from pathlib import Path

from fetch_snapshot import blob_hash


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verify every extracted source file against a fixed Git tree')
    parser.add_argument('--tree', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    tree = json.loads(args.tree.read_text(encoding='utf-8-sig'))
    if tree.get('truncated'):
        raise ValueError('Truncated source tree')
    entries = [entry for entry in tree['tree'] if entry['type'] == 'blob']
    for entry in entries:
        path = args.root / entry['path']
        if not path.is_file() or blob_hash(path.read_bytes()) != entry['sha']:
            raise ValueError(f'Missing or changed source file: {entry["path"]}')
    (args.root / 'SNAPSHOT.json').write_text(json.dumps({'revision': tree['sha'], 'verified_files': len(entries)}, indent=2) + '\n', encoding='utf-8')
    print(f'{len(entries)} source files verified against {tree["sha"]}')
