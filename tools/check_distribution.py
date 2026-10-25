import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description='Read back every byte of a public split TAR distribution')
    parser.add_argument('--base', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    base = args.base.rstrip('/') + '/'
    with urlopen(base + 'DISTRIBUTION.json', timeout=180) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != args.manifest_sha256:
        raise ValueError('Distribution manifest does not match the independently recorded hash')
    distribution = json.loads(content)
    records = distribution['parts']
    names = [record['name'] for record in records]
    if len(names) != len(set(names)) or any(PurePosixPath(name).name != name or '\\' in name or ':' in name for name in names):
        raise ValueError('Invalid part names')

    def check(record):
        with urlopen(Request(base + quote(record['name']), headers={'User-Agent': 'DharmaArchiveReadback/1.0'}), timeout=600) as response:
            digest = hashlib.sha256()
            count = 0
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                count += len(chunk)
        if count != record['bytes'] or digest.hexdigest() != record['sha256']:
            raise ValueError(f'Distribution part differs: {record["name"]}')
        return count

    total = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(check, record) for record in records]
        for index, future in enumerate(as_completed(futures), 1):
            total += future.result()
            if index % 20 == 0 or index == len(records):
                print(f'{index}/{len(records)} parts independently read back', flush=True)
    receipt = {'base': base, 'scope': 'all_distribution_parts', 'ok': True, 'verified': len(records), 'bytes': total, 'manifest_sha256': args.manifest_sha256, 'payload_manifest_sha256': distribution['payload_manifest_sha256'], 'time_utc': datetime.now(timezone.utc).isoformat()}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
