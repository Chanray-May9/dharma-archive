import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path, PurePosixPath
import time
from urllib.request import Request, urlopen
from urllib.parse import quote


def blob_hash(content):
    return hashlib.sha1(f'blob {len(content)}\0'.encode('ascii') + content).hexdigest()


def fetch_one(repository, revision, root, entry):
    relative = PurePosixPath(entry['path'])
    if relative.is_absolute() or '..' in relative.parts or '\\' in entry['path']:
        raise ValueError('Unsafe upstream path')
    target = root.joinpath(*relative.parts)
    if target.is_file() and blob_hash(target.read_bytes()) == entry['sha']:
        return 'existing', entry['size']
    url = f'https://raw.githubusercontent.com/{repository}/{revision}/{quote(relative.as_posix(), safe="/")}'
    failure = None
    for attempt in range(6):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'DharmaArchive/0.1 (public preservation; 8 concurrent downloads)'}), timeout=90) as response:
                content = response.read()
            if len(content) != entry['size'] or blob_hash(content) != entry['sha']:
                raise ValueError(f'Source blob checksum mismatch: {relative}')
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.partial')
            temporary.write_bytes(content)
            temporary.replace(target)
            return 'downloaded', len(content)
        except Exception as error:
            failure = error
            time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f'Failed after retries: {relative}: {failure}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', required=True)
    parser.add_argument('--tree', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--prefix', action='append', required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    tree = json.loads(args.tree.read_text(encoding='utf-8-sig'))
    if tree.get('truncated'):
        raise ValueError('Upstream tree is truncated; refuse to claim a complete snapshot')
    entries = [entry for entry in tree['tree'] if entry['type'] == 'blob' and any(entry['path'].startswith(prefix) for prefix in args.prefix)]
    if not entries:
        raise ValueError('No source files match the selected prefixes')
    args.output.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        pending = {executor.submit(fetch_one, args.repository, tree['sha'], args.output, entry): entry for entry in entries}
        for completed, future in enumerate(as_completed(pending), 1):
            try:
                status, size = future.result()
                total_bytes += size
            except Exception as error:
                failures.append(str(error))
                print(str(error), flush=True)
            if completed % 100 == 0 or completed == len(entries):
                print(f'{completed}/{len(entries)} files; {total_bytes / 1048576:.1f} MiB verified; failures={len(failures)}', flush=True)
    if failures:
        raise RuntimeError(f'{len(failures)} downloads failed; rerun to resume verified downloads')
    (args.output / 'SNAPSHOT.json').write_text(json.dumps({'repository': args.repository, 'revision': tree['sha'], 'prefixes': args.prefix, 'files': len(entries), 'bytes': total_bytes}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
