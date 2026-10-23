import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_archive import manifest


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def protect(args):
    root = args.root.resolve()
    recovery = root / 'data/recovery'
    if recovery.exists():
        raise ValueError('Recovery set already exists; do not overwrite a published set')
    recovery.mkdir(parents=True)
    paths = [path for path in (root / 'data').rglob('*') if path.is_file()]
    paths += [root / name for name in ('RECOVERY.txt', 'verify.py', 'RESTORE.py')]
    paths = sorted(paths)
    total = sum(path.stat().st_size for path in paths)
    block_size = 262144
    source_blocks = sum(math.ceil(path.stat().st_size / block_size) for path in paths)
    recovery_blocks = math.ceil(source_blocks * args.percent / 100)
    volume_count = max(2, math.ceil(recovery_blocks * block_size / (18 * 1024 * 1024)))
    if volume_count > 31:
        raise ValueError('Recovery set too large; split into independent recovery stripes')
    filelist = args.work.resolve() / 'recovery-filelist.txt'
    filelist.parent.mkdir(parents=True, exist_ok=True)
    relative = [path.relative_to(root).as_posix() for path in paths]
    filelist.write_text('\n'.join(relative) + '\n', encoding='utf-8', newline='\n')
    index = recovery / 'dharma.par2'
    command = [str(args.par2.resolve()), 'create', '-q', '-q', f'-r{args.percent}', f'-s{block_size}', '-u', f'-n{volume_count}', '-t8', '-m512', f'-B{root}', str(index), '@' + str(filelist)]
    subprocess.run(command, cwd=root, check=True)
    if any(path.stat().st_size > 24 * 1024 * 1024 for path in recovery.glob('*.par2')):
        raise ValueError('A recovery volume exceeds the free asset size limit')
    expected = {name: digest(root / name) for name in relative}
    receipt = {'format': 'PAR2 / Reed-Solomon over GF(2^16)', 'redundancy_percent': args.percent, 'block_bytes': block_size, 'source_files': len(paths), 'source_bytes': total, 'source_blocks_rounded_estimate': source_blocks, 'volumes': [path.name for path in sorted(recovery.glob('*.par2'))], 'tool_sha256': digest(args.par2), 'created_utc': datetime.now(timezone.utc).isoformat(), 'repair_drill': {'state': 'not_run'}}
    if args.drill:
        work = args.work.resolve()
        with tempfile.TemporaryDirectory(prefix='par2-repair-drill-', dir=work) as temporary:
            drill = Path(temporary).resolve()
            if not drill.is_relative_to(work):
                raise ValueError('Unexpected temporary directory location')
            for name in relative:
                target = drill / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / name, target)
            for path in recovery.glob('*.par2'):
                target = drill / path.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            packages = sorted((drill / 'data/packages').glob('*.zip'), key=lambda path: path.stat().st_size, reverse=True)
            missing, corrupted = packages[:2]
            missing_name = missing.relative_to(drill).as_posix()
            corrupted_name = corrupted.relative_to(drill).as_posix()
            missing_bytes = missing.stat().st_size
            missing.unlink()
            with corrupted.open('r+b') as stream:
                stream.seek(min(65536, corrupted.stat().st_size // 3))
                stream.write(b'\xA5' * min(65536, corrupted.stat().st_size // 3))
            result = subprocess.run([str(args.par2.resolve()), 'repair', '-q', '-q', '-t8', '-m512', f'-B{drill}', str(drill / 'data/recovery/dharma.par2')], cwd=drill, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f'Repair drill failed ({result.returncode}): {result.stdout[-2000:]} {result.stderr[-1000:]}')
            for name, expected_digest in expected.items():
                if digest(drill / name) != expected_digest:
                    raise ValueError(f'Repaired bytes differ from originals: {name}')
            receipt['repair_drill'] = {'state': 'passed', 'missing_package': missing_name, 'missing_bytes': missing_bytes, 'corrupted_package': corrupted_name, 'all_protected_files_rehashed': len(expected), 'result': 'All repaired files are byte-for-byte equal by SHA-256'}
    (recovery / 'PROTECTION.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (recovery / 'protected-sha256.txt').write_text(''.join(f'{value}  {name}\n' for name, value in expected.items()), encoding='utf-8', newline='\n')
    manifest(root)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create interoperable PAR2 disaster-recovery data and test actual repair')
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--par2', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--percent', type=int, default=35)
    parser.add_argument('--drill', action='store_true')
    protect(parser.parse_args())
