import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import time


def run(repository, arguments, capture=False):
    environment = os.environ.copy()
    environment['GIT_TERMINAL_PROMPT'] = '0'
    return subprocess.run(['git', '-C', str(repository), *arguments], check=True, text=True, capture_output=capture, env=environment)


def files_under(root):
    result = []
    for directory, folders, filenames in os.walk(root):
        folders[:] = [folder for folder in folders if folder not in ('.git', '__pycache__')]
        for filename in sorted(filenames):
            result.append(Path(directory) / filename)
    return sorted(result)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Resume bounded Git pushes across unreliable HTTP connections')
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--remote', required=True)
    parser.add_argument('--credential-helper', default='!gh auth git-credential')
    parser.add_argument('--max-mib', type=int, default=24)
    parser.add_argument('--max-files', type=int, default=500)
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if not (destination / '.git').exists():
        run(destination, ['init', '-b', 'main'])
        run(destination, ['remote', 'add', 'origin', args.remote])
        run(destination, ['config', 'core.autocrlf', 'false'])
        run(destination, ['config', 'gc.auto', '0'])
        run(destination, ['config', 'maintenance.auto', 'false'])
    files = files_under(source)
    batches = []
    current = []
    current_bytes = 0
    for path in files:
        if current and (current_bytes + path.stat().st_size > args.max_mib * 1048576 or len(current) >= args.max_files):
            batches.append(current)
            current = []
            current_bytes = 0
        current.append(path)
        current_bytes += path.stat().st_size
    if current:
        batches.append(current)
    transferred = 0
    for position, batch in enumerate(batches, 1):
        changed = False
        for path in batch:
            target = destination / path.relative_to(source)
            if not target.is_file() or digest(path) != digest(target):
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                changed = True
            transferred += path.stat().st_size
        if changed:
            run(destination, ['add', '--all'])
            run(destination, ['commit', '-q', '-m', f'Preserve verified archive batch {position} of {len(batches)}'])
        head = run(destination, ['rev-parse', 'HEAD'], capture=True).stdout.strip()
        push_args = ['-c', 'credential.helper=', '-c', f'credential.helper={args.credential_helper}', '-c', 'http.version=HTTP/1.1', '-c', 'http.postBuffer=52428800', 'push', '-q', '-u', 'origin', 'main']
        for attempt in range(4):
            try:
                run(destination, push_args)
                break
            except subprocess.CalledProcessError:
                if attempt == 3:
                    raise
                print(f'Batch {position} interrupted; retry {attempt + 1}/3', flush=True)
                time.sleep(2 ** attempt)
        print(f'{position}/{len(batches)} batches pushed; {transferred / 1048576:.1f} MiB; {head}', flush=True)
    for path in files:
        if digest(path) != digest(destination / path.relative_to(source)):
            raise ValueError(f'Copy changed during transfer: {path}')
    print(f'Complete: {len(files)} files; {transferred} bytes; all local copies rehashed', flush=True)
