import argparse
import hashlib
import json
from pathlib import Path
import shutil


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prepare bounded GitHub data repositories without LFS pointers')
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--owner', default='Chanray-May9')
    args = parser.parse_args()
    root = args.root.resolve()
    paths = sorted((root / 'data/packages').glob('*.zip')) + sorted((root / 'data/upstream').glob('*.part-*'))
    repositories = []
    files = {}
    current = None
    for path in paths:
        if current is None or current['bytes'] + path.stat().st_size > 750 * 1024 * 1024:
            current = {'name': f'dharma-archive-data-{len(repositories) + 1:03d}', 'bytes': 0, 'files': 0}
            repositories.append(current)
        relative = path.relative_to(root).as_posix()
        target = args.output / current['name'] / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        url = f'https://raw.githubusercontent.com/{args.owner}/{current["name"]}/main/{relative}'
        files[relative] = [{'url': url, 'sha256': digest, 'state': 'prepared_not_yet_uploaded'}]
        current['bytes'] += path.stat().st_size
        current['files'] += 1
    for repository in repositories:
        directory = args.output / repository['name']
        (directory / 'README.md').write_text(f'# 经藏原件数据分片 / {repository["name"]}\n\n真实 ZIP 原件恢复包，不使用 Git LFS。完整目录、来源、纠错与恢复说明见 https://github.com/{args.owner}/dharma-archive 。\n\n文件数：{repository["files"]}；字节数：{repository["bytes"]}。恢复包内含原始 XML/JSON/TXT、UTF-8 阅读副本、来源与校验说明。\n\n此仓库仅是完整快照的一部分，应连同其他分片及恢复数据共同保存。\n', encoding='utf-8')
        manifest = ''.join(f'{info[0]["sha256"]}  {name}\n' for name, info in files.items() if f'/{repository["name"]}/' in info[0]['url'])
        (directory / 'manifest-sha256.txt').write_text(manifest, encoding='utf-8', newline='\n')
    registry = {'cloudflare': 'https://dharma-archive-api.gqr20080509.workers.dev', 'repositories': repositories, 'files': files, 'rules': [{'prefix': 'data/recovery/', 'base': f'https://raw.githubusercontent.com/{args.owner}/dharma-archive-recovery/main/'}], 'state': 'prepared; verify external receipts before treating as uploaded'}
    (root / 'data/mirrors.json').write_text(json.dumps(registry, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps({'repositories': repositories, 'files': len(files)}, ensure_ascii=False, indent=2))
