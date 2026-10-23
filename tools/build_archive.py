import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from fetch_snapshot import blob_hash


TEI = '{http://www.tei-c.org/ns/1.0}'
XML_ID = '{http://www.w3.org/XML/1998/namespace}id'
CBETA_COLLECTIONS = {'T': '大正新脩大藏經', 'X': '卍新纂續藏經', 'J': '嘉興大藏經', 'N': '漢譯南傳大藏經'}
LANGUAGES = {'pli': '巴利文', 'lzh': '汉文', 'san': '梵文', 'pra': '普拉克里特诸语'}


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8', newline='\n')


def revision(root):
    if (root / 'SNAPSHOT.json').exists():
        return json.loads((root / 'SNAPSHOT.json').read_text(encoding='utf-8'))['revision']
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()


def manifest(directory):
    lines = []
    size = 0
    for path in sorted((directory / 'data').rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            lines.append(f'{digest}  {path.relative_to(directory).as_posix()}\n')
            size += path.stat().st_size
    (directory / 'bagit.txt').write_text('BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n', encoding='utf-8', newline='\n')
    (directory / 'manifest-sha256.txt').write_text(''.join(lines), encoding='utf-8', newline='\n')
    (directory / 'bag-info.txt').write_text(f'Bag-Software-Agent: Dharma Archive 0.1\nPayload-Oxum: {size}.{len(lines)}\n', encoding='utf-8', newline='\n')


def xml_record(content, include_terms=False):
    root = ET.fromstring(content)
    title_node = root.find(f'.//{TEI}title[@level="m"]')
    if title_node is None:
        title_node = root.find(f'.//{TEI}title')
    title = ''.join(title_node.itertext()).strip() if title_node is not None else root.attrib.get(XML_ID, '')
    author = root.find(f'.//{TEI}author')
    attribution = ''.join(author.itertext()).strip() if author is not None else ''
    gaiji = {}
    for char in root.iter(f'{TEI}char'):
        identifier = char.attrib.get(XML_ID, '')
        mappings = list(char.iter(f'{TEI}mapping'))
        for kind in ('unicode', 'normal_unicode', 'normal'):
            mapping = next((item for item in mappings if item.attrib.get('type') == kind and item.text), None)
            if mapping is not None:
                value = mapping.text.strip()
                if re.fullmatch(r'U\+[0-9A-Fa-f]+(?:\s+U\+[0-9A-Fa-f]+)*', value):
                    value = ''.join(chr(int(point[2:], 16)) for point in value.split())
                gaiji[identifier] = value
                break

    def render(node):
        tag = node.tag.rsplit('}', 1)[-1]
        if tag == 'g':
            identifier = node.attrib.get('ref', '').lstrip('#')
            return node.text or gaiji.get(identifier, f'[{identifier}]')
        if tag in ('lb', 'pb'):
            return '\n'
        text = node.text or ''
        for child in node:
            text += render(child) + (child.tail or '')
        if tag == 'note':
            return f'【校注：{text}】'
        if tag == 'rdg':
            return f'【異讀：{text}】'
        if tag in ('p', 'head', 'l', 'div', 'lg', 'juan'):
            return text + '\n'
        return text

    body = root.find(f'.//{TEI}body')
    if body is None:
        raise ValueError('TEI body missing')
    text = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', render(body)).strip()
    if not text:
        raise ValueError('Empty TEI text')
    if include_terms:
        availability = root.find(f'.//{TEI}availability')
        terms = ' '.join(''.join(availability.itertext()).split()) if availability is not None else 'See original source header and preserved source copyright policy'
        return title, attribution, text, terms
    return title, attribution, text


def make_package(path, members, source_metadata):
    members['data/source.json'] = (json.dumps(source_metadata, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    checksums = ''.join(f'{sha256(content)}  {name}\n' for name, content in sorted(members.items()))
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, content in sorted(members.items()):
            archive.writestr(name, content)
        archive.writestr('bagit.txt', 'BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n')
        archive.writestr('manifest-sha256.txt', checksums)
        archive.writestr('README.txt', 'UTF-8 / ZIP (DEFLATE) / BagIt 1.0 / SHA-256\nOriginal files are authoritative. Reading text is derived and may lose markup.\nSee data/source.json and data/notices/ for source versions and terms.\nExtract with any ZIP utility. No website, account, database or API is required.\n')
    if path.stat().st_size > 24 * 1024 * 1024:
        raise ValueError(f'Package exceeds free static-file budget: {path}')


def build(args):
    output = args.output.resolve()
    canon_data = json.loads((args.cbeta / 'canons.json').read_text(encoding='utf-8'))
    CBETA_COLLECTIONS.clear()
    CBETA_COLLECTIONS.update({code: value['title-zh'] for code, value in canon_data.items()})
    if (output / 'data/catalog.json').exists():
        raise ValueError('An archive already exists here; use a new output directory for each snapshot.')
    source_trees = {}
    extras = [json.loads(path.read_text(encoding='utf-8')) for path in args.extra_source]
    for label, root, tree_path, prefixes in [
        ('cbeta', args.cbeta, args.cbeta_tree, [f'{code}/' for code in CBETA_COLLECTIONS]),
        ('suttacentral', args.bilara, args.bilara_tree, [f'root/{language}/' for language in LANGUAGES] + ['translation/']),
    ]:
        tree = json.loads(tree_path.read_text(encoding='utf-8-sig'))
        if tree.get('truncated') or tree['sha'] != revision(root):
            raise ValueError(f'Incomplete or mismatched source tree: {label}')
        entries = [entry for entry in tree['tree'] if entry['type'] == 'blob' and any(entry['path'].startswith(prefix) for prefix in prefixes) and entry['path'].endswith(('.xml', '.json'))]
        for entry in entries:
            path = root / entry['path']
            if not path.is_file() or blob_hash(path.read_bytes()) != entry['sha']:
                raise ValueError(f'Missing or changed upstream file: {label}/{entry["path"]}')
        if not entries:
            raise ValueError(f'Empty source scope: {label}')
        source_trees[label] = {'revision': tree['sha'], 'truncated': False, 'files': entries}
        print(f'{label}: {len(entries)} source files verified against fixed upstream tree', flush=True)
    for source in extras:
        tree = json.loads(Path(source['tree']).read_text(encoding='utf-8-sig'))
        root = Path(source['root'])
        if tree.get('truncated') or revision(root) != tree['sha']:
            raise ValueError(f'Incomplete or mismatched extra source: {source["id"]}')
        entries = [entry for entry in tree['tree'] if entry['type'] == 'blob' and entry['path'].startswith(source['prefix'])]
        for entry in entries:
            if blob_hash((root / entry['path']).read_bytes()) != entry['sha']:
                raise ValueError(f'Extra source hash mismatch: {entry["path"]}')
        source['revision'] = tree['sha']
        source_trees[source['id']] = {'revision': tree['sha'], 'truncated': False, 'files': entries}
        print(f'{source["id"]}: {len(entries)} upstream files verified', flush=True)
    data = output / 'data'
    (data / 'packages').mkdir(parents=True, exist_ok=True)
    (data / 'sources').mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).isoformat()
    sources = [
        {'id': 'cbeta', 'name': 'CBETA 電子佛典基金會', 'repository': 'https://github.com/cbeta-org/xml-p5', 'revision': revision(args.cbeta), 'scope': list(CBETA_COLLECTIONS), 'license': 'Mixed original per-document availability statements; preserved verbatim in catalog and original XML; see CBETA copyright policy', 'license_url': 'https://cbeta.org/copyright', 'retrieved_utc': retrieved, 'coverage': 'All canonical XML collections present in the fixed repository snapshot; not all world Buddhist texts'},
        {'id': 'suttacentral', 'name': 'SuttaCentral / Bilara contributors', 'repository': 'https://github.com/suttacentral/bilara-data', 'revision': revision(args.bilara), 'scope': ['root/pli', 'root/lzh', 'root/san', 'root/pra', 'translation/'], 'license': 'Public domain original texts; Bilara-supported translations CC0; original notices retained', 'license_url': 'https://suttacentral.net/licensing', 'retrieved_utc': retrieved, 'coverage': 'Selected root folders plus all translation JSON files in the fixed repository snapshot; includes ancillary localization files'},
    ]
    sources.extend({key: value for key, value in source.items() if key not in ('root', 'tree')} | {'retrieved_utc': retrieved} for source in extras)
    for label, root in [('cbeta', args.cbeta), ('suttacentral', args.bilara)]:
        target = data / 'sources' / label
        target.mkdir(parents=True, exist_ok=True)
        for name in ['README.md', 'LICENSE.md', '_publication.json', '_project-v2.json', 'canons.json']:
            if (root / name).is_file():
                shutil.copyfile(root / name, target / name)
        write_json(target / 'tree-selected.json', source_trees[label])
    for source in extras:
        target = data / 'sources' / source['id']
        target.mkdir(parents=True, exist_ok=True)
        for path in Path(source['root']).glob('README*'):
            shutil.copyfile(path, target / path.name)
        write_json(target / 'tree-selected.json', source_trees[source['id']])
    if (args.cbeta / 'schema').exists():
        shutil.copytree(args.cbeta / 'schema', data / 'sources/cbeta/schema', dirs_exist_ok=True)
    for source in args.notices.glob('*'):
        if source.is_file():
            shutil.copyfile(source, data / 'sources' / source.name)
    if args.bilara_archive:
        upstream = data / 'upstream'
        upstream.mkdir(parents=True, exist_ok=True)
        chunks = []
        archive_hash = hashlib.sha256()
        with args.bilara_archive.open('rb') as stream:
            while content := stream.read(16 * 1024 * 1024):
                name = f'bilara-full-source.tar.gz.part-{len(chunks) + 1:03d}'
                (upstream / name).write_bytes(content)
                archive_hash.update(content)
                chunks.append({'path': name, 'bytes': len(content), 'sha256': sha256(content)})
        write_json(upstream / 'bilara-full-source-parts.json', {'format': 'raw byte concatenation in listed order; no framing', 'restored_filename': 'bilara-full-source.tar.gz', 'sha256': archive_hash.hexdigest(), 'parts': chunks})
    notices = {f'data/notices/{path.relative_to(data / "sources").as_posix()}': path.read_bytes() for path in (data / 'sources').rglob('*') if path.is_file() and path.name not in ('tree-selected.json', '_publication.json', '_project-v2.json')}
    groups = defaultdict(list)
    for collection in CBETA_COLLECTIONS:
        for path in sorted((args.cbeta / collection).rglob('*.xml')):
            relative = path.relative_to(args.cbeta)
            groups[f'cbeta-{relative.parts[1]}'].append(('cbeta', path, relative.as_posix()))
    for language in LANGUAGES:
        for path in sorted((args.bilara / 'root' / language).rglob('*.json')):
            relative = path.relative_to(args.bilara)
            parts = relative.parts
            group = '-'.join(parts[1:4])
            groups[f'sc-{group}'].append(('suttacentral', path, relative.as_posix()))
    for path in sorted((args.bilara / 'translation').rglob('*.json')):
        relative = path.relative_to(args.bilara)
        group = '-'.join(relative.parts[:3])
        groups[f'sc-{group}'].append(('suttacentral', path, relative.as_posix()))
    for source in extras:
        root = Path(source['root'])
        for entry in source_trees[source['id']]['files']:
            groups[source['id']].append((source['id'], root / entry['path'], entry['path']))
    catalog = []
    packages = []
    for group, files in sorted(groups.items()):
        members = dict(notices)
        records = []
        part = 1
        payload_size = sum(map(len, members.values()))

        def flush():
            nonlocal members, records, part, payload_size
            if not records:
                return
            name = f'{group}-{part:03d}.zip'
            package_path = f'data/packages/{name}'
            make_package(output / package_path, members, sources)
            with zipfile.ZipFile(output / package_path) as archive:
                for record in records:
                    record['package_path'] = package_path
                    info = archive.getinfo(record['text_member'])
                    record['text_zip_offset'] = info.header_offset + 30 + len(info.filename.encode('utf-8')) + len(info.extra)
                    record['text_zip_size'] = info.compress_size
                    record['text_zip_method'] = info.compress_type
            package_bytes = (output / package_path).read_bytes()
            packages.append({'path': package_path, 'documents': len(records), 'bytes': len(package_bytes), 'sha256': sha256(package_bytes), 'group': group})
            catalog.extend(records)
            members = dict(notices)
            records = []
            payload_size = sum(map(len, members.values()))
            part += 1

        for source_id, path, relative in files:
            original = path.read_bytes()
            if source_id == 'cbeta':
                title, author, reading, license_name = xml_record(original, include_terms=True)
                document_id = f'cbeta:{path.stem}'
                collection_code = relative.split('/')[0]
                collection = CBETA_COLLECTIONS[collection_code]
                language = 'lzh'
            elif source_id == 'suttacentral':
                values = json.loads(original)
                if not isinstance(values, dict) or not all(isinstance(value, str) for value in values.values()):
                    raise ValueError(f'Unexpected JSON segment format: {relative}')
                nonempty = [value for value in values.values() if value.strip()]
                title = re.sub(r'<[^>]+>', '', unescape(nonempty[0])).strip() if nonempty else path.stem
                reading = '\n'.join(f'[{key}] {value}' for key, value in values.items())
                document_id = 'sc:' + path.stem
                collection = 'SuttaCentral'
                language = relative.split('/')[1]
                author = relative.split('/')[2]
                license_name = 'CC0-1.0 (Bilara supported translation)' if relative.startswith('translation/') else 'Public domain original text; source notices retained'
            else:
                extra = next(source for source in extras if source['id'] == source_id)
                if extra.get('kind') == 'tei':
                    title, author, reading = xml_record(original)
                else:
                    reading = original.decode('utf-8-sig')
                    title = f'{extra["name"].split(" / ")[0]} · {path.stem}'
                    author = 'Esukhia and upstream contributors; see original README'
                document_id = f'{source_id}:{path.stem}'
                collection = extra['name'].split(' / ')[0]
                language = extra['language']
                license_name = extra['license']
            source = next(item for item in sources if item['id'] == source_id)
            original_url = f'{source["repository"]}/blob/{source["revision"]}/{relative}'
            preamble = f'{title}\nID: {document_id}\nSource: {source["name"]}\nRevision: {source["revision"]}\nOriginal: {original_url}\nTerms: {license_name}; see sources and original header\nReading copy: formatting converted; original is authoritative.\n\n'
            text_bytes = (preamble + reading + '\n').encode('utf-8')
            if len(text_bytes) > 24 * 1024 * 1024:
                raise ValueError(f'Reading text too large: {document_id}')
            if records and payload_size + len(original) + len(text_bytes) > 48 * 1024 * 1024:
                flush()
            filename = document_id.replace(':', '_') + '.txt'
            text_path = f'data/texts/{filename}'
            original_member = f'data/original/{source_id}/{relative}'
            members[original_member] = original
            members[f'data/reading/{filename}'] = text_bytes
            payload_size += len(original) + len(text_bytes)
            records.append({'id': document_id, 'title': title[:300], 'author': author, 'language': language, 'collection': collection, 'source': source_id, 'source_revision': source['revision'], 'source_path': relative, 'source_url': original_url, 'license': license_name, 'original_sha256': sha256(original), 'text_sha256': sha256(text_bytes), 'text_bytes': len(text_bytes), 'text_path': text_path, 'text_storage': 'zip-member', 'text_member': f'data/reading/{filename}', 'original_member': original_member})
        flush()
        print(f'{group}: {len(files)} documents; total {len(catalog)}', flush=True)
    catalog.sort(key=lambda record: (record['source'], record['source_path']))
    if len(catalog) != sum(len(tree['files']) for tree in source_trees.values()):
        raise ValueError('Catalog count does not match verified source file count')
    chunks = []
    for offset in range(0, len(catalog), 1500):
        chunk = catalog[offset:offset + 1500]
        name = f'data/catalog/catalog-{offset // 1500:03d}.json'
        write_json(output / name, chunk)
        chunks.append(name)
        with (output / name).with_suffix('.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
            for record in chunk:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    write_json(data / 'catalog.json', {'documents': len(catalog), 'chunks': chunks, 'format': 'catalog-chunks-v1', 'reading_storage': 'UTF-8 text members in standard ZIP packages'})
    columns = ['id', 'title', 'language', 'collection', 'text_member', 'package_path', 'original_member', 'original_sha256', 'source_url']
    with (data / 'catalog.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(catalog)
    write_json(data / 'sources.json', sources)
    write_json(data / 'packages.json', packages)
    status = {'created_utc': retrieved, 'documents': len(catalog), 'packages': len(packages), 'languages': dict(Counter(record['language'] for record in catalog)), 'collections': dict(Counter(record['collection'] for record in catalog)), 'original_bytes': sum(path.stat().st_size for source_id, path, relative in [entry for group in groups.values() for entry in group]), 'text_bytes': sum(record['text_bytes'] for record in catalog), 'package_bytes': sum(package['bytes'] for package in packages), 'world_coverage': 'incomplete', 'excluded': ['Not-yet-digitized manuscripts', 'Scanned images and audio', 'Other Tibetan editions outside the archived repositories', 'Other Sanskrit corpora pending ingestion', 'Translations outside the archived source repositories'], 'mirrors': [{'platform': 'local', 'state': 'built'}, {'platform': 'GitHub', 'state': 'pending_verification'}, {'platform': 'Cloudflare', 'state': 'pending_verification'}]}
    write_json(data / 'status.json', status)
    manifest(output)
    files = [path for path in output.rglob('*') if path.is_file()]
    if len(files) > 19500:
        raise ValueError('Too many files for the configured free deployment; split into separate shards.')
    oversized = [str(path) for path in files if path.stat().st_size > 24 * 1024 * 1024]
    if oversized:
        raise ValueError(f'Asset size budget exceeded: {oversized}')
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cbeta', required=True, type=Path)
    parser.add_argument('--bilara', required=True, type=Path)
    parser.add_argument('--cbeta-tree', required=True, type=Path)
    parser.add_argument('--bilara-tree', required=True, type=Path)
    parser.add_argument('--bilara-archive', type=Path)
    parser.add_argument('--extra-source', action='append', default=[], type=Path)
    parser.add_argument('--notices', required=True, type=Path)
    parser.add_argument('--output', default='public', type=Path)
    build(parser.parse_args())
