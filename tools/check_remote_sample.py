import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description='Verify a reproducible remote file sample; not a full mirror audit')
    parser.add_argument('--base', required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--count', type=int, default=16)
    args = parser.parse_args()
    files = sorted(path for path in args.source.rglob('*') if path.is_file() and '.git' not in path.relative_to(args.source).parts)
    if args.count < 2 or not files:
        raise ValueError('Need at least two samples and a nonempty source')
    selected = {files[index * (len(files) - 1) // (args.count - 1)] for index in range(args.count)}
    selected.update(path for path in files if path.name == 'manifest-sha256.txt' or path.name.startswith('LICENSE'))
    selected.add(max(files, key=lambda path: path.stat().st_size))

    def check(path):
        name = path.relative_to(args.source).as_posix()
        with path.open('rb') as stream:
            expected = hashlib.file_digest(stream, 'sha256').hexdigest()
        url = args.base.rstrip('/') + '/' + quote(name, safe='/')
        with urlopen(Request(url, headers={'User-Agent': 'DharmaArchiveReadback/1.0'}), timeout=180) as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError(f'Remote checksum differs: {name}')
        return {'path': name, 'bytes': path.stat().st_size, 'sha256': actual}

    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(check, sorted(selected)))
    receipt = {'base': args.base, 'scope': 'sample_only_not_full_readback', 'verified': len(records), 'total_files': len(files), 'files': records, 'ok': True, 'time_utc': datetime.now(timezone.utc).isoformat()}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'ok': True, 'scope': receipt['scope'], 'verified': len(records), 'total_files': len(files)}), flush=True)


if __name__ == '__main__':
    main()
