import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from verify import parse_manifest, safe_path


def retrieve(base, path):
    url = base.rstrip('/') + '/' + quote(path, safe='/')
    with urlopen(Request(url, headers={'User-Agent': 'DharmaArchiveMirror/0.1'}), timeout=180) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description='Download or fully read back a public archive mirror')
    parser.add_argument('action', choices=['download', 'check'])
    parser.add_argument('--base', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--packages-only', action='store_true')
    args = parser.parse_args()
    manifest = retrieve(args.base, 'manifest-sha256.txt')
    if hashlib.sha256(manifest).hexdigest() != args.manifest_sha256:
        raise ValueError('Mirror manifest does not match the independently recorded hash')
    records = parse_manifest(manifest.decode('utf-8'))
    try:
        registry = json.loads(retrieve(args.base, 'data/mirrors.json'))
    except Exception:
        registry = {'files': {}, 'rules': []}
    selected = [(digest, name) for digest, name in records if not args.packages_only or name.startswith('data/packages/')]
    args.output.mkdir(parents=True, exist_ok=True)

    def transfer(record):
        digest, name = record
        target = args.output.joinpath(*safe_path(name).parts)
        if args.action == 'download' and target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            return name, 'existing'
        try:
            content = retrieve(args.base, name)
        except Exception as original_error:
            alternatives = [item['url'] for item in registry.get('files', {}).get(name, [])]
            alternatives += [rule['base'].rstrip('/') + '/' + name for rule in registry.get('rules', []) if name.startswith(rule['prefix'])]
            content = None
            for url in alternatives:
                try:
                    with urlopen(Request(url, headers={'User-Agent': 'DharmaArchiveMirror/0.1'}), timeout=180) as response:
                        content = response.read()
                    break
                except Exception:
                    continue
            if content is None:
                raise original_error
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f'Remote checksum mismatch: {name}')
        if args.action == 'download':
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.partial')
            temporary.write_bytes(content)
            temporary.replace(target)
        return name, 'verified'

    failures = []
    verified = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(transfer, record): record for record in selected}
        for completed, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
                verified += 1
            except Exception as error:
                failures.append(str(error))
            if completed % 100 == 0 or completed == len(selected):
                print(f'{completed}/{len(selected)} checked; failures={len(failures)}', flush=True)
    if args.action == 'download':
        (args.output / 'manifest-sha256.txt').write_bytes(manifest)
        for name in ['bagit.txt', 'bag-info.txt', 'RECOVERY.txt', 'verify.py']:
            (args.output / name).write_bytes(retrieve(args.base, name))
    receipt = {'base': args.base, 'action': args.action, 'time_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'packages_only' if args.packages_only else 'all_payload_files', 'manifest_sha256': args.manifest_sha256, 'verified': verified, 'expected': len(selected), 'failures': failures, 'ok': not failures}
    (args.output / 'mirror-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
