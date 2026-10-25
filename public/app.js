import { extractZipMember, formatXmlReading } from './reader-layout.js';

const select = (selector) => document.querySelector(selector);
const config = window.ARCHIVE_CONFIG || {};
const currentPage = document.body.dataset.page;
const params = new URLSearchParams(location.search);
const languageNames = { lzh: '汉文原典', pli: '巴利文', san: '梵文', pra: '普拉克里特诸语', bod: '藏文', zh: '汉语译文', en: '英语', de: '德语', fr: '法语', ru: '俄语', ja: '日语', jpn: '日语', ko: '韩语', vi: '越南语', cs: '捷克语', es: '西班牙语', et: '爱沙尼亚语', fi: '芬兰语', gsw: '瑞士德语', gu: '古吉拉特语', hi: '印地语', id: '印度尼西亚语', it: '意大利语', ka: '格鲁吉亚语', kan: '卡纳达语', lo: '老挝语', lt: '立陶宛语', mr: '马拉地语', my: '缅甸语', nl: '荷兰语', no: '挪威语', pl: '波兰语', pt: '葡萄牙语', si: '僧伽罗语', sl: '斯洛文尼亚语', sr: '塞尔维亚语', ta: '泰米尔语', th: '泰语', tr: '土耳其语' };
const number = new Intl.NumberFormat('zh-CN');
const localURL = (path) => new URL(path, document.baseURI).href;
const backendURL = (path) => config.apiBase ? `${config.apiBase.replace(/\/$/, '')}/${path}` : localURL(path);
const fileURL = (path) => config.apiBase && location.hostname.endsWith('github.io') ? backendURL(path) : localURL(path);
const state = { catalog: [], filtered: [], page: 0, pageSize: 40, packages: [], packageLimit: 40, mirrors: { files: {}, rules: [] }, originalText: '', originalXml: '', readerRecord: null, searchCache: new Map() };
let scriptMode = params.get('script');
if (!['simplified', 'original'].includes(scriptMode)) {
  try { scriptMode = localStorage.getItem('dharma-script'); } catch {}
}
if (!['simplified', 'original'].includes(scriptMode)) scriptMode = 'simplified';
let converter;

function simplify(text) {
  if (!/[\u3400-\u9fff]/u.test(text)) return text;
  if (!converter) {
    if (!window.OpenCC) throw new Error('简体转换组件未能加载，请刷新重试，或选择原文显示。');
    converter = window.OpenCC.Converter({ from: 't', to: 'cn' });
  }
  return converter(text);
}

const displayText = (text) => scriptMode === 'simplified' ? simplify(text) : text;

function pageURL(page, values = {}) {
  const url = new URL(page === 'home' ? 'index.html' : `${page}.html`, document.baseURI);
  for (const [key, value] of Object.entries(values)) if (value !== '' && value !== undefined) url.searchParams.set(key, value);
  return url.href;
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function mirrorURLs(path) {
  return [...(state.mirrors.files?.[path] || []).map((entry) => entry.url), ...(state.mirrors.rules || []).filter((rule) => path.startsWith(rule.prefix)).map((rule) => `${rule.base.replace(/\/$/, '')}/${path}`)];
}

async function loadJSON(path, endpoint) {
  const urls = config.apiBase ? (endpoint ? [backendURL(endpoint), localURL(path)] : [localURL(path), backendURL(path)]) : [localURL(path)];
  for (const url of urls) {
    try {
      const response = await fetch(url);
      if (response.ok) return await response.json();
    } catch {}
  }
  throw new Error('暂时无法载入文件，请重试或下载离线目录。');
}

function libraryValues() {
  return { q: select('#search').value.trim(), language: select('#language').value, collection: select('#collection').value, page: state.page + 1, script: scriptMode };
}

function renderCatalog() {
  const fragment = document.createDocumentFragment();
  for (const record of state.filtered.slice(state.page * state.pageSize, (state.page + 1) * state.pageSize)) {
    const row = element('tr');
    const documentCell = element('td');
    const url = pageURL('reader', { ...libraryValues(), id: record.id });
    const title = element('a', displayText(record.title), 'document-title');
    title.href = url;
    documentCell.append(title, element('small', record.id));
    const actions = element('td');
    const read = element('a', '阅读 ↗', 'read-link');
    read.href = url;
    actions.append(read);
    row.append(documentCell, element('td', languageNames[record.language] || record.language), element('td', displayText(record.collection), 'collection-cell'), actions);
    fragment.append(row);
  }
  select('#catalog-body').replaceChildren(fragment);
  select('#empty').hidden = Boolean(state.filtered.length);
  select('#results-count').textContent = `共 ${number.format(state.filtered.length)} 份文献文件`;
  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  select('#page-number').textContent = `${state.page + 1} / ${pages}`;
  select('#previous').disabled = state.page === 0;
  select('#next').disabled = state.page + 1 >= pages;
  history.replaceState(null, '', pageURL('library', libraryValues()));
}

function filterCatalog(resetPage = true) {
  const terms = simplify(select('#search').value.trim()).toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const language = select('#language').value;
  const collection = select('#collection').value;
  state.filtered = state.catalog.filter((record) => {
    if (language && record.language !== language) return false;
    if (collection && record.collection !== collection) return false;
    if (!terms.length) return true;
    if (!state.searchCache.has(record.id)) state.searchCache.set(record.id, simplify(`${record.title} ${record.id} ${record.author} ${record.collection}`).toLocaleLowerCase());
    return terms.every((term) => state.searchCache.get(record.id).includes(term));
  });
  if (resetPage) state.page = 0;
  state.page = Math.min(state.page, Math.max(0, Math.ceil(state.filtered.length / state.pageSize) - 1));
  renderCatalog();
}

function setupLibrary(status) {
  for (const [language, count] of Object.entries(status.languages)) {
    const option = element('option', `${languageNames[language] || language} (${number.format(count)})`);
    option.value = language;
    select('#language').append(option);
  }
  for (const collection of Object.keys(status.collections)) {
    const option = element('option', displayText(collection));
    option.value = collection;
    select('#collection').append(option);
  }
  select('#search').value = params.get('q') || '';
  select('#language').value = params.get('language') || '';
  select('#collection').value = params.get('collection') || '';
  state.page = Math.max(0, (Number.parseInt(params.get('page'), 10) || 1) - 1);
  select('#search-form').addEventListener('submit', (event) => { event.preventDefault(); filterCatalog(); });
  let searchTimer;
  select('#search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(filterCatalog, 150); });
  select('#language').addEventListener('change', () => filterCatalog());
  select('#collection').addEventListener('change', () => filterCatalog());
  select('#previous').addEventListener('click', () => { state.page--; renderCatalog(); });
  select('#next').addEventListener('click', () => { state.page++; renderCatalog(); });
  filterCatalog(false);
}

function renderLanguages(status) {
  select('#language-count').textContent = `${Object.keys(status.languages).length} 个收录语种`;
  for (const [language, count] of Object.entries(status.languages)) {
    const card = element('article', undefined, 'language-card');
    const link = element('a');
    link.href = pageURL('library', { language, script: 'simplified' });
    link.append(element('h2', languageNames[language] || language), element('small', language.toUpperCase()), element('p', `${number.format(count)} 份文献文件 · 浏览 →`));
    card.append(link);
    if (['lzh', 'zh'].includes(language)) {
      link.append(element('p', '简体阅读'));
      const original = element('a', '原文显示 →', 'language-original');
      original.href = pageURL('library', { language, script: 'original' });
      card.append(original);
    }
    select('#language-list').append(card);
  }
}

async function readTextBytes(record) {
  const path = record.text_storage === 'zip-member' ? record.package_path : record.text_path;
  const urls = [...new Set([fileURL(path), localURL(path), ...(config.apiBase ? [backendURL(path)] : []), ...mirrorURLs(path)])];
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
        else throw new Error('请下载 ZIP 包后解压读取');
      }
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      const actual = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join('');
      if (actual !== record.text_sha256) throw new Error('文本校验不一致，正在尝试其他副本。');
      return bytes;
    } catch (error) { failure = error; }
  }
  throw failure || new Error('读取失败，请下载原件恢复包。');
}

async function loadOriginalXml(record) {
  const urls = [...new Set([fileURL(record.package_path), localURL(record.package_path), ...(config.apiBase ? [backendURL(record.package_path)] : []), ...mirrorURLs(record.package_path)])];
  for (const url of urls) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(30000) });
      if (!response.ok) continue;
      const bytes = await extractZipMember(await response.arrayBuffer(), record.original_member);
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      const actual = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join('');
      if (actual !== record.original_sha256) continue;
      const xml = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
      formatXmlReading(xml);
      return xml;
    } catch {}
  }
  return '';
}

function renderReader() {
  const record = state.readerRecord;
  if (!record) return;
  const converted = scriptMode === 'simplified' && ['lzh', 'zh'].includes(record.language);
  const title = converted ? simplify(record.title) : record.title;
  const text = converted ? simplify(state.originalText) : state.originalText;
  const flowing = select('#layout-mode').value === 'flow' && Boolean(state.originalXml);
  const layout = flowing ? formatXmlReading(state.originalXml, { showSectionNumbers: select('#show-section-numbers').checked }) : state.originalText;
  const displayed = converted ? simplify(layout) : layout;
  select('#reader-title').textContent = title;
  document.title = `${title} · 经藏`;
  select('#reader-text').textContent = displayed;
  select('#reader-text').dataset.layout = flowing ? 'flow' : 'original';
  select('#reader-state').textContent = `原阅读文本 SHA-256 校验通过 · ${converted ? '简体转换显示' : '原文显示'}`;
  const download = select('#download-text');
  if (download.dataset.objectUrl) URL.revokeObjectURL(download.dataset.objectUrl);
  const objectUrl = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  download.href = objectUrl;
  download.dataset.objectUrl = objectUrl;
  download.download = `${record.id.replace(':', '_')}${converted ? '_简体转换' : '_原文'}.txt`;
  download.textContent = converted ? '下载简体 TXT ↓' : '下载原文 TXT ↓';
  const values = Object.fromEntries(params);
  values.script = scriptMode;
  delete values.id;
  select('#back-to-library').href = pageURL('library', values);
  history.replaceState(null, '', pageURL('reader', { ...values, id: record.id }));
}

async function setupReader() {
  const record = state.catalog.find((entry) => entry.id === params.get('id'));
  if (!record) throw new Error('未找到这份经文，请返回目录重新选择。');
  select('#reader-id').textContent = record.id;
  select('#reader-state').textContent = '正在读取已备份文本……';
  select('#download-original').href = mirrorURLs(record.package_path)[0] || fileURL(record.package_path);
  select('#original-source').href = record.source_url;
  state.originalText = new TextDecoder('utf-8', { fatal: true }).decode(await readTextBytes(record));
  if (record.source === 'cbeta' && record.original_member.endsWith('.xml')) state.originalXml = await loadOriginalXml(record);
  if (!state.originalXml) {
    select('#layout-mode').value = 'original';
    select('#layout-mode').disabled = true;
    select('#show-section-numbers').disabled = true;
  }
  select('#layout-mode').addEventListener('change', renderReader);
  select('#show-section-numbers').addEventListener('change', renderReader);
  state.readerRecord = record;
  renderReader();
}

function renderPackages() {
  const query = select('#package-search').value.trim().toLowerCase();
  const packages = state.packages.filter((item) => item.path.toLowerCase().includes(query));
  const fragment = document.createDocumentFragment();
  for (const item of packages.slice(0, state.packageLimit)) {
    const row = element('div', undefined, 'package-row');
    const info = element('div');
    info.append(element('strong', item.path.split('/').pop()), element('small', `${item.documents} 份文献 · ${(item.bytes / 1048576).toFixed(1)} MB · SHA-256 ${item.sha256.slice(0, 16)}…`));
    const cloud = element('a', 'Cloudflare 下载 ↓');
    cloud.href = fileURL(item.path);
    const github = element('a', '我的 GitHub 文件 ↓');
    github.href = mirrorURLs(item.path)[0] || fileURL(item.path);
    row.append(info, github, cloud);
    fragment.append(row);
  }
  select('#package-list').replaceChildren(fragment);
  select('#more-packages').hidden = packages.length <= state.packageLimit;
}

async function start() {
  if (currentPage === 'home' && ['#library', '#packages', '#preservation'].includes(location.hash)) {
    location.replace(pageURL({ '#library': 'library', '#packages': 'packages', '#preservation': 'recovery' }[location.hash]));
    return;
  }
  for (const link of document.querySelectorAll('[data-page-link]')) {
    if (link.dataset.pageLink === currentPage || (currentPage === 'reader' && link.dataset.pageLink === 'library')) {
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
    }
  }
  const mode = select('#script-mode');
  if (mode) {
    mode.value = scriptMode;
    mode.addEventListener('change', () => {
      scriptMode = mode.value;
      try { localStorage.setItem('dharma-script', scriptMode); } catch {}
      if (currentPage === 'library') renderCatalog();
      if (currentPage === 'reader') renderReader();
    });
  }
  if (currentPage === 'recovery') return;
  if (currentPage === 'packages') {
    [state.packages, state.mirrors] = await Promise.all([loadJSON('data/packages.json', 'api/packages'), loadJSON('data/mirrors.json')]);
    select('#package-search').addEventListener('input', () => { state.packageLimit = 40; renderPackages(); });
    select('#more-packages').addEventListener('click', () => { state.packageLimit += 40; renderPackages(); });
    renderPackages();
    return;
  }
  const status = await loadJSON('data/status.json', 'api/status');
  if (currentPage === 'home') {
    select('#stat-documents').textContent = number.format(status.documents);
    select('#stat-languages').textContent = Object.keys(status.languages).length;
    select('#stat-packages').textContent = number.format(status.packages);
    return;
  }
  if (currentPage === 'languages') { renderLanguages(status); return; }
  const index = await loadJSON('data/catalog.json', 'api/catalog');
  state.catalog = Array.isArray(index) ? index : (await Promise.all(index.chunks.map((path) => loadJSON(path)))).flat();
  if (currentPage === 'library') setupLibrary(status);
  if (currentPage === 'reader') {
    state.mirrors = await loadJSON('data/mirrors.json');
    await setupReader();
  }
}

start().catch((error) => {
  select('#page-error').hidden = false;
  select('#page-error').textContent = error.message;
});
