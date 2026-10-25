import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from credential_store import transform


def api(url, token, method='GET', data=None):
    if urlparse(url).hostname != 'zenodo.org':
        raise ValueError('Refusing to send credentials to another host')
    headers = {'Authorization': 'Bearer ' + token}
    if isinstance(data, dict):
        data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    try:
        with urlopen(Request(url, headers=headers, data=data, method=method), timeout=180) as response:
            return json.load(response)
    except HTTPError as error:
        message = error.read().decode('utf-8', errors='replace')[:2000]
        raise RuntimeError(f'Zenodo HTTP {error.code}: {message}') from None


def main():
    parser = argparse.ArgumentParser(description='Upload and optionally publish a complete preservation distribution on Zenodo')
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--credential', required=True, type=Path)
    parser.add_argument('--deposition', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    credential = json.loads(transform(args.credential.read_bytes(), decrypt=True))
    saved = json.loads(args.deposition.read_text(encoding='utf-8'))
    deposition = api(saved['links']['self'], credential['token'])
    if deposition.get('submitted'):
        print(json.dumps({'state': 'already_published', 'id': deposition['id'], 'links': deposition['links']}))
        return
    metadata = {
        'title': 'Dharma Archive: Buddhist Text Preservation Snapshot 2026-10-23',
        'upload_type': 'dataset',
        'publication_date': '2026-10-23',
        'creators': [{'name': 'Dharma Archive preservation project'}],
        'description': '<p>A preservation snapshot of 27,403 catalogued Buddhist source files in 38 language folders: CBETA XML, SuttaCentral Bilara originals and translations, Esukhia Derge Kangyur and Tengyur, and 225 GRETIL Buddhist TEI texts. Includes exact original bytes, UTF-8 reading copies, SHA-256 manifests, PAR2 error correction and restoration tools. This is not a claim of worldwide completeness.</p><p>Concatenate the ordered part files listed in DISTRIBUTION.json to obtain a standard POSIX TAR archive. The manifest records each part checksum and recovery instructions. TAR members are locally compared with their originals before upload.</p><p>Rights vary by source. Original license notices and source revisions accompany the data. Some sources have non-commercial restrictions; the compilation does not grant additional rights or replace original terms. This record preserves existing text datasets; it does not represent authorship of the scriptures or endorsement by source institutions.</p>',
        'access_right': 'open',
        'license': 'other-nc',
        'keywords': ['Buddhism', 'Buddhist texts', 'digital preservation', 'PAR2', 'CBETA', 'SuttaCentral', 'Esukhia', 'GRETIL'],
        'related_identifiers': [{'identifier': 'https://github.com/Chanray-May9/dharma-archive', 'relation': 'isDocumentedBy', 'resource_type': 'software'}],
    }
    deposition = api(deposition['links']['self'], credential['token'], 'PUT', {'metadata': metadata})
    bucket = deposition['links']['bucket']
    if urlparse(bucket).hostname != 'zenodo.org':
        raise ValueError('Unexpected upload host')
    files = sorted(path for path in args.source.iterdir() if path.is_file())
    known = {record['filename']: record for record in deposition.get('files', [])}
    receipt = {'id': deposition['id'], 'state': 'uploading', 'expected': len(files), 'uploaded': [], 'time_utc': datetime.now(timezone.utc).isoformat()}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding='utf-8')

    def upload(path):
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        if known.get(path.name, {}).get('checksum', '').removeprefix('md5:') == digest:
            return path.name
        headers = {'Authorization': 'Bearer ' + credential['token'], 'Content-Type': 'application/octet-stream', 'Content-Length': str(path.stat().st_size)}
        for attempt in range(5):
            try:
                with path.open('rb') as stream:
                    request = Request(bucket + '/' + quote(path.name), data=stream, headers=headers, method='PUT')
                    with urlopen(request, timeout=600) as response:
                        result = json.load(response)
                if result.get('checksum', '').removeprefix('md5:') != digest:
                    raise ValueError('Uploaded file checksum differs')
                return path.name
            except Exception as error:
                if attempt == 4:
                    raise RuntimeError(f'Upload failed: {path.name} ({type(error).__name__})') from None
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(upload, path) for path in files]
        for future in as_completed(futures):
            receipt['uploaded'].append(future.result())
            args.receipt.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
            print(f'{len(receipt["uploaded"])}/{len(files)} Zenodo files uploaded with matching MD5', flush=True)
    deposition = api(deposition['links']['self'], credential['token'])
    remote = {record['filename']: record for record in deposition['files']}
    for path in files:
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        if remote.get(path.name, {}).get('checksum', '').removeprefix('md5:') != digest:
            raise ValueError(f'File not confirmed in deposition: {path.name}')
    if args.publish:
        deposition = api(deposition['links']['publish'], credential['token'], 'POST', {})
    receipt.update({'state': 'published_pending_independent_readback' if deposition.get('submitted') else 'uploaded_draft', 'doi': deposition.get('doi'), 'links': deposition['links'], 'time_utc': datetime.now(timezone.utc).isoformat()})
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps({'state': receipt['state'], 'id': receipt['id'], 'doi': receipt['doi']}), flush=True)


if __name__ == '__main__':
    main()
