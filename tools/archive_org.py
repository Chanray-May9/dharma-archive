import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from credential_store import transform


def remote_metadata(identifier):
    with urlopen(f'https://archive.org/metadata/{identifier}', timeout=120) as response:
        return json.load(response)


def upload_file(identifier, path, name, credential):
    digest = hashlib.md5(path.read_bytes()).digest()
    headers = {
        'Authorization': f'LOW {credential["username"]}:{credential["token"]}',
        'Content-Length': str(path.stat().st_size),
        'Content-MD5': base64.b64encode(digest).decode('ascii'),
        'Content-Type': 'application/octet-stream',
        'x-archive-auto-make-bucket': '1',
        'x-archive-queue-derive': '0',
        'x-archive-meta-title': 'Dharma Archive Buddhist Text Preservation Snapshot 2026-10-23',
        'x-archive-meta-mediatype': 'data',
        'x-archive-meta-collection': 'opensource_media',
        'x-archive-meta-description': 'Original Buddhist text snapshots, UTF-8 reading copies, SHA-256 manifests and PAR2 error correction. Source-specific terms are preserved inside each package. Not a claim of worldwide completeness. Part files concatenate to a standard TAR archive; see DISTRIBUTION.json.',
        'x-archive-meta-subject': 'Buddhism;Buddhist texts;digital preservation;CBETA;SuttaCentral;Esukhia;GRETIL',
    }
    for attempt in range(5):
        try:
            with path.open('rb') as stream:
                request = Request(f'https://s3.us.archive.org/{identifier}/{quote(name, safe="/")}', data=stream, headers=headers, method='PUT')
                with urlopen(request, timeout=600) as response:
                    if response.status not in (200, 201):
                        raise RuntimeError(f'Upload returned HTTP {response.status}')
                    response.read()
            return name
        except Exception as error:
            if attempt == 4:
                raise RuntimeError(f'Upload failed: {name} ({type(error).__name__})') from None
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser(description='Upload a preservation distribution to an authorized Internet Archive item')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--credential', type=Path, required=True)
    parser.add_argument('--identifier', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    credential = json.loads(transform(args.credential.read_bytes(), decrypt=True))
    files = sorted(path for path in args.source.rglob('*') if path.is_file())
    existing = remote_metadata(args.identifier)
    if existing and not args.receipt.exists():
        raise ValueError('Existing item requires the local ownership receipt; refusing to overwrite')
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt = {'identifier': args.identifier, 'url': f'https://archive.org/details/{args.identifier}', 'state': 'uploading', 'expected': len(files), 'uploaded': [], 'time_utc': datetime.now(timezone.utc).isoformat()}
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    known = {entry['name']: entry for entry in existing.get('files', [])}
    pending = []
    for path in files:
        name = path.relative_to(args.source).as_posix()
        remote = known.get(name, {})
        if remote.get('md5') == hashlib.md5(path.read_bytes()).hexdigest() and str(remote.get('size')) == str(path.stat().st_size):
            receipt['uploaded'].append(name)
        else:
            pending.append((path, name))
    if not existing and pending:
        path, name = pending.pop(0)
        upload_file(args.identifier, path, name, credential)
        receipt['uploaded'].append(name)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(upload_file, args.identifier, path, name, credential) for path, name in pending]
        for future in as_completed(futures):
            receipt['uploaded'].append(future.result())
            args.receipt.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
            print(f'{len(receipt["uploaded"])}/{len(files)} uploaded', flush=True)
    receipt['state'] = 'uploaded_pending_independent_readback'
    receipt['time_utc'] = datetime.now(timezone.utc).isoformat()
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps({'state': receipt['state'], 'files': len(files), 'url': receipt['url']}), flush=True)


if __name__ == '__main__':
    main()
