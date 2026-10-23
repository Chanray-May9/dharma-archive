import hashlib
from pathlib import Path
import shutil


if __name__ == '__main__':
    destination = Path('work/codeberg-public-domain')
    selections = [
        (Path('work/derge-kangyur'), ['text']),
        (Path('work/derge-tengyur'), ['text']),
        (Path('work/bilara-full'), ['root/pli', 'root/lzh', 'root/san', 'root/pra', 'translation']),
    ]
    for source, folders in selections:
        target_root = destination / source.name
        for folder in folders:
            shutil.copytree(source / folder, target_root / folder, dirs_exist_ok=True)
        for path in list(source.glob('README*')) + list(source.glob('LICENSE*')) + [source / 'SNAPSHOT.json']:
            if path.is_file():
                shutil.copyfile(path, target_root / path.name)
    lines = []
    total = 0
    for path in sorted(destination.rglob('*')):
        if path.is_file() and path.name != 'manifest-sha256.txt':
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            lines.append(f'{digest}  {path.relative_to(destination).as_posix()}\n')
            total += path.stat().st_size
    (destination / 'manifest-sha256.txt').write_text(''.join(lines), encoding='utf-8', newline='\n')
    print(f'{len(lines)} original files; {total} bytes; public domain / CC0 subset only')
