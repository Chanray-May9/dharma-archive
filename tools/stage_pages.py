import argparse
from pathlib import Path
import shutil


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Stage only the frontend and catalog for GitHub Pages; data stays in the Git repository and Cloudflare mirror')
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a fresh Pages staging directory')
    excluded = ('data/packages/', 'data/recovery/', 'data/upstream/', 'data/toolkit/')
    for path in args.source.rglob('*'):
        if path.is_file():
            relative = path.relative_to(args.source).as_posix()
            if any(relative.startswith(prefix) for prefix in excluded):
                continue
            target = args.output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    print(f'Pages frontend staged at {args.output}; full data is in the Git repository and Cloudflare')
