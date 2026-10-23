import argparse
import hashlib
from pathlib import Path
import zipfile

from verify import safe_path, verify_zip


def restore(source, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    packages = sorted((source / 'data/packages').glob('*.zip'))
    if not packages:
        raise ValueError('No recovery ZIP packages found')
    count = 0
    for package in packages:
        verify_zip(package)
        with zipfile.ZipFile(package) as archive:
            for info in archive.infolist():
                if info.filename.startswith('data/original/'):
                    relative = 'original/' + info.filename.removeprefix('data/original/')
                elif info.filename.startswith('data/reading/'):
                    relative = 'texts/' + info.filename.removeprefix('data/reading/')
                elif info.filename.startswith('data/notices/'):
                    relative = 'notices/' + info.filename.removeprefix('data/notices/')
                else:
                    continue
                target = output.joinpath(*safe_path(relative).parts)
                if not target.resolve().is_relative_to(output):
                    raise ValueError('Output path escapes recovery directory')
                content = archive.read(info)
                if target.exists():
                    if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(content).digest():
                        raise ValueError(f'Conflicting file during restore: {relative}')
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                    count += 1
        print(f'Restored {package.name}: {count} unique files', flush=True)
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Restore originals and UTF-8 texts without a website or database')
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(f'Restored and verified {restore(args.source, args.output)} files')
