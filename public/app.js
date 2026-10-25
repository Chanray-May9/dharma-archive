const select = (selector) => document.querySelector(selector);
const config = window.ARCHIVE_CONFIG || {};
const languageNames = { lzh: '汉文', pli: '巴利文', san: '梵文', pra: '普拉克里特诸语', bod: '藏文', zh: '中文译文', en: '英语', de: '德语', fr: '法语', ru: '俄语', ja: '日语', ko: '韩语', vi: '越南语' };
const state = { catalog: [], filtered: [], page: 0, pageSize: 40, packages: [], packageLimit: 40, mirrors: { files: {}, rules: [] } };
const number = new Intl.NumberFormat('zh-CN');
const localURL = (path) => new URL(path, document.baseURI).href;
const backendURL = (path) => config.apiBase ? `${config.apiBase.replace(/\/$/, '')}/${path}` : localURL(path);
const fileURL = (path) => config.apiBase && location.hostname.endsWith('github.io') ? backendURL(path) : localURL(path);

function mirrorURLs(path) {
  return [
    ...(state.mirrors.files?.[path] || []).map((entry) => entry.url),
    ...(state.mirrors.rules || []).filter((rule) => path.startsWith(rule.prefix)).map((rule) => `${rule.base.replace(/\/$/, '')}/${path}`),
  ];
}

async function loadJSON(path, endpoint) {
  const urls = config.apiBase ? (endpoint ? [backendURL(endpoint), localURL(path)] : [localURL(path), backendURL(path)]) : [localURL(path)];
  for (const url of urls) {
    try {
      const response = await fetch(url);
      if (response.ok) return await response.json();
    } catch {}
  }
  throw new Error('目录暂时无法载入。可通过“脱离网站恢复”下载独立文件。');
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function render() {
  const start = state.page * state.pageSize;
  const rows = state.filtered.slice(start, start + state.pageSize);
  const fragment = document.createDocumentFragment();
  for (const record of rows) {
    const row = element('tr');
    const documentCell = element('td');
    const title = element('button', record.title, 'document-title');
    title.addEventListener('click', () => openReader(record));
    documentCell.append(title, element('small', record.id));
    const languageCell = element('td', languageNames[record.language] || record.language);
    const collectionCell = element('td', record.collection, 'collection-cell');
    const actionCell = element('td');
    const read = element('button', '阅读 ↗', 'read-link');
    read.addEventListener('click', () => openReader(record));
    actionCell.append(read);
    row.append(documentCell, languageCell, collectionCell, actionCell);
    fragment.append(row);
  }
  select('#catalog-body').replaceChildren(fragment);
  select('#empty').hidden = Boolean(state.filtered.length);
  select('#results-count').textContent = `共 ${number.format(state.filtered.length)} 份文献文件`;
  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  select('#page-number').textContent = `${state.page + 1} / ${pages}`;
  select('#previous').disabled = state.page === 0;
  select('#next').disabled = state.page + 1 >= pages;
}

function filter() {
  const terms = select('#search').value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const language = select('#language').value;
  const collection = select('#collection').value;
  state.filtered = state.catalog.filter((record) => {
    if (language && record.language !== language) return false;
    if (collection && record.collection !== collection) return false;
    const haystack = `${record.title} ${record.id} ${record.author} ${record.collection}`.toLocaleLowerCase();
    return terms.every((term) => haystack.includes(term));
  });
  state.page = 0;
  render();
}

let readerRequest = 0;
async function openReader(record) {
  const current = ++readerRequest;
  select('#reader-title').textContent = record.title;
  select('#reader-id').textContent = record.id;
  select('#reader-text').textContent = '';
  select('#reader-state').textContent = '正在读取独立文本……';
  select('#download-text').removeAttribute('href');
  select('#download-original').href = fileURL(record.package_path);
  select('#original-source').href = record.source_url;
  if (!select('#reader').open) select('#reader').showModal();
  try {
    const bytes = await readTextBytes(record);
    if (current !== readerRequest) return;
    if (select('#download-text').dataset.objectUrl) URL.revokeObjectURL(select('#download-text').dataset.objectUrl);
    const objectUrl = URL.createObjectURL(new Blob([bytes], { type: 'text/plain;charset=utf-8' }));
    select('#download-text').href = objectUrl;
    select('#download-text').dataset.objectUrl = objectUrl;
    select('#download-text').download = `${record.id.replace(':', '_')}.txt`;
    select('#reader-text').textContent = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    select('#reader-state').textContent = 'SHA-256 校验通过 · 阅读副本，校勘与完整结构见原件';
  } catch (error) {
    if (current === readerRequest) select('#reader-state').textContent = error.message;
  }
}

async function readTextBytes(record) {
  const path = record.text_storage === 'zip-member' ? record.package_path : record.text_path;
  const rawGitHub = `${config.repository.replace('https://github.com/', 'https://raw.githubusercontent.com/')}/main/public/${path}`;
  const urls = [...new Set([fileURL(path), localURL(path), ...(config.apiBase ? [backendURL(path)] : []), ...mirrorURLs(path), rawGitHub])];
  let failure;
  for (const url of urls) {
    try {
      const headers = record.text_storage === 'zip-member' ? { Range: `bytes=${record.text_zip_offset}-${record.text_zip_offset + record.text_zip_size - 1}` } : {};
      const response = await fetch(url, { headers });
      if (!response.ok) throw new Error('文件镜像暂时不可用');
      const received = await response.arrayBuffer();
      let bytes = received;
      if (record.text_storage === 'zip-member') {
        const compressed = response.status === 206 ? received : received.slice(record.text_zip_offset, record.text_zip_offset + record.text_zip_size);
        if (record.text_zip_method === 0) bytes = compressed;
        else if (record.text_zip_method === 8) bytes = await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer();
        else throw new Error('请下载 ZIP 包后使用解压工具读取');
      }
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      const actual = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join('');
      if (actual !== record.text_sha256) throw new Error('文本校验不一致，请改从其他镜像读取。');
      return bytes;
    } catch (error) { failure = error; }
  }
  throw failure || new Error('读取失败，请下载原件恢复包');
}

function showTab() {
  const requested = location.hash.slice(1) || 'library';
  const name = ['library', 'packages', 'preservation'].includes(requested) ? requested : 'library';
  for (const panel of document.querySelectorAll('.panel')) panel.hidden = panel.id !== name;
  for (const link of document.querySelectorAll('[data-tab]')) {
    link.classList.toggle('active', link.dataset.tab === name);
    if (link.dataset.tab === name) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
}

function renderPackages() {
  const query = select('#package-search').value.trim().toLowerCase();
  const packages = state.packages.filter((item) => item.path.toLowerCase().includes(query));
  const fragment = document.createDocumentFragment();
  for (const item of packages.slice(0, state.packageLimit)) {
    const row = element('div', undefined, 'package-row');
    const info = element('div');
    info.append(element('strong', item.path.split('/').pop()), element('small', `${item.documents} 份文献 · ${(item.bytes / 1048576).toFixed(1)} MB · SHA-256 ${item.sha256.slice(0, 16)}…`));
    const link = element('a', '下载 ZIP ↓');
    link.href = fileURL(item.path);
    link.download = '';
    row.append(info, link);
    const alternative = mirrorURLs(item.path)[0];
    if (alternative) {
      const backup = element('a', 'GitHub ↗');
      backup.href = alternative;
      row.append(backup);
    }
    fragment.append(row);
  }
  select('#package-list').replaceChildren(fragment);
  select('#more-packages').hidden = packages.length <= state.packageLimit;
}

select('#search-form').addEventListener('submit', (event) => { event.preventDefault(); filter(); });
let searchTimer;
select('#search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(filter, 120); });
select('#language').addEventListener('change', filter);
select('#collection').addEventListener('change', filter);
select('#previous').addEventListener('click', () => { state.page--; render(); });
select('#next').addEventListener('click', () => { state.page++; render(); });
select('#close-reader').addEventListener('click', () => { readerRequest++; select('#reader').close(); });
select('#reader').addEventListener('close', () => { readerRequest++; });
select('#package-search').addEventListener('input', () => { state.packageLimit = 40; renderPackages(); });
select('#more-packages').addEventListener('click', () => { state.packageLimit += 40; renderPackages(); });
window.addEventListener('hashchange', showTab);
showTab();

async function start() {
  const [catalogIndex, status, packages, mirrors] = await Promise.all([
    loadJSON('data/catalog.json', 'api/catalog'),
    loadJSON('data/status.json', 'api/status'),
    loadJSON('data/packages.json', 'api/packages'),
    loadJSON('data/mirrors.json').catch(() => ({ files: {}, rules: [] })),
  ]);
  const catalog = Array.isArray(catalogIndex) ? catalogIndex : (await Promise.all(catalogIndex.chunks.map((path) => loadJSON(path)))).flat();
  state.catalog = catalog;
  state.packages = packages;
  state.mirrors = mirrors;
  select('#stat-documents').textContent = number.format(status.documents);
  select('#stat-languages').textContent = Object.keys(status.languages).length;
  select('#stat-packages').textContent = number.format(status.packages);
  select('#coverage').textContent = '当前快照包括 CBETA 全部现有藏经集合、SuttaCentral 原典与译文、德格甘珠尔与丹珠尔、GRETIL 梵文佛教文献。计数包括分段、卷册、版本及辅助文件，不等于独立经书部数；世界范围仍在扩充。';
  for (const language of Object.keys(status.languages)) {
    const option = element('option', `${languageNames[language] || language} (${number.format(status.languages[language])})`);
    option.value = language;
    select('#language').append(option);
  }
  for (const collection of Object.keys(status.collections)) {
    const option = element('option', collection);
    option.value = collection;
    select('#collection').append(option);
  }
  select('#repo-link').href = config.repository;
  select('#github-mirror').href = config.repository;
  select('#cloud-mirror').href = backendURL('RECOVERY.txt');
  filter();
  renderPackages();
}

start().catch((error) => {
  select('#coverage').textContent = error.message;
  select('#results-count').textContent = '可通过独立目录恢复';
});
