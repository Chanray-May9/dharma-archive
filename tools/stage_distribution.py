import argparse
import hashlib
import json
from pathlib import Path
import tarfile


class SplitWriter:
    def __init__(self, output, limit):
        self.output = output
        self.limit = limit
        self.stream = None
        self.written = 0
        self.parts = []

    def write(self, content):
        total = len(content)
        while content:
            if self.stream is None or self.written == self.limit:
                self.close()
                name = f'dharma-archive.tar.part-{len(self.parts) + 1:03}'
                self.parts.append(name)
                self.stream = (self.output / name).open('wb')
                self.written = 0
            count = min(len(content), self.limit - self.written)
            self.stream.write(content[:count])
            self.written += count
            content = content[count:]
        return total

    def close(self):
        if self.stream:
            self.stream.close()
            self.stream = None


class PartReader:
    def __init__(self, paths):
        self.paths = iter(paths)
        self.stream = None

    def read(self, size):
        chunks = []
        remaining = size
        while remaining:
            if self.stream is None:
                path = next(self.paths, None)
                if path is None:
                    break
                self.stream = path.open('rb')
            chunk = self.stream.read(remaining)
            if not chunk:
                self.close()
                continue
            chunks.append(chunk)
            remaining -= len(chunk)
        return b''.join(chunks)

    def close(self):
        if self.stream:
            self.stream.close()
            self.stream = None


def validate_distribution(source, output):
    distribution = json.loads((output / 'DISTRIBUTION.json').read_text(encoding='utf-8'))
    paths = []
    for record in distribution['parts']:
        if Path(record['name']).name != record['name']:
            raise ValueError('Unsafe distribution part name')
        path = output / record['name']
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != record['sha256'] or path.stat().st_size != record['bytes']:
            raise ValueError(f'Damaged part: {path.name}')
        paths.append(path)
    expected = {path.relative_to(source).as_posix(): path for path in source.rglob('*') if path.is_file()}
    seen = set()
    reader = PartReader(paths)
    try:
        with tarfile.open(fileobj=reader, mode='r|') as archive:
            for member in archive:
                name = member.name.removeprefix('dharma-archive/')
                if not member.isfile() or name not in expected or name in seen:
                    raise ValueError(f'Unexpected TAR member: {member.name}')
                with expected[name].open('rb') as stream:
                    expected_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                with archive.extractfile(member) as stream:
                    actual_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if actual_digest != expected_digest:
                    raise ValueError(f'TAR member differs: {name}')
                seen.add(name)
    finally:
        reader.close()
    if seen != set(expected):
        raise ValueError('Incomplete TAR distribution')
    print(f'Validated {len(paths)} parts and all {len(seen)} original TAR members', flush=True)


def main():
    parser = argparse.ArgumentParser(description='Split a standard TAR distribution without proprietary framing')
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--part-mib', type=int, default=16)
    args = parser.parse_args()
    if args.verify_only:
        validate_distribution(args.source, args.output)
        return
    args.output.mkdir(parents=True, exist_ok=True)
    if list(args.output.iterdir()):
        raise ValueError('Use an empty staging directory')
    if not 1 <= args.part_mib <= 512:
        raise ValueError('Part size must be between 1 and 512 MiB')
    writer = SplitWriter(args.output, args.part_mib * 1024 * 1024)
    with tarfile.open(fileobj=writer, mode='w|', format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(args.source.rglob('*')):
            if path.is_file():
                archive.add(path, arcname='dharma-archive/' + path.relative_to(args.source).as_posix(), recursive=False)
    writer.close()
    records = []
    for name in writer.parts:
        path = args.output / name
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        records.append({'name': name, 'bytes': path.stat().st_size, 'sha256': digest})
    manifest_hash = hashlib.sha256((args.source / 'manifest-sha256.txt').read_bytes()).hexdigest()
    record = {'format': f'POSIX TAR / PAX, byte-split at {args.part_mib} MiB; no encryption', 'parts': records, 'payload_manifest_sha256': manifest_hash, 'restore': 'Concatenate parts in the listed order into dharma-archive.tar, then extract using any standard TAR tool. Run python dharma-archive/verify.py dharma-archive --deep. For damaged payloads use the included PAR2 volumes before verification.'}
    (args.output / 'DISTRIBUTION.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    (args.output / 'README.txt').write_text(record['restore'] + '\n\nPayload manifest SHA-256: ' + manifest_hash + '\n', encoding='utf-8')
    print(f'{len(records)} TAR parts; {sum(item["bytes"] for item in records)} bytes', flush=True)
    validate_distribution(args.source, args.output)


if __name__ == '__main__':
    main()
