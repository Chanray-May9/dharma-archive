from pathlib import Path


def build(root):
    template = (root / 'frontend/layout.html').read_text(encoding='utf-8')
    pages = {'home': ('index.html', '首页'), 'library': ('library.html', '经藏目录'), 'languages': ('languages.html', '收录语种'), 'packages': ('packages.html', '下载与镜像'), 'recovery': ('recovery.html', '恢复工具'), 'reader': ('reader.html', '经文阅读')}
    for page, (filename, title) in pages.items():
        content = (root / f'frontend/{page}.html').read_text(encoding='utf-8')
        output = template.replace('{{title}}', title).replace('{{page}}', page).replace('{{content}}', content)
        (root / 'public' / filename).write_text(output, encoding='utf-8', newline='\n')
    print(f'Built {len(pages)} standalone HTML pages')


if __name__ == '__main__':
    build(Path(__file__).resolve().parents[1])
