export async function extractZipMember(buffer, memberName) {
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  let directory = -1;
  for (let position = bytes.length - 22; position >= Math.max(0, bytes.length - 65557); position--) {
    if (view.getUint32(position, true) === 0x06054b50 && position + 22 + view.getUint16(position + 20, true) === bytes.length) {
      directory = position;
      break;
    }
  }
  if (directory < 0 || view.getUint16(directory + 4, true) || view.getUint16(directory + 6, true)) throw new Error('不支持的 ZIP 目录');
  let position = view.getUint32(directory + 16, true);
  const count = view.getUint16(directory + 10, true);
  const decoder = new TextDecoder('utf-8', { fatal: true });
  for (let index = 0; index < count; index++) {
    if (position + 46 > directory || view.getUint32(position, true) !== 0x02014b50) throw new Error('ZIP 目录损坏');
    const nameSize = view.getUint16(position + 28, true);
    const extraSize = view.getUint16(position + 30, true);
    const commentSize = view.getUint16(position + 32, true);
    const end = position + 46 + nameSize + extraSize + commentSize;
    if (end > directory) throw new Error('ZIP 文件名越界');
    const name = decoder.decode(bytes.subarray(position + 46, position + 46 + nameSize));
    if (name === memberName) {
      if (view.getUint16(position + 8, true) & 1) throw new Error('不支持加密 ZIP');
      const method = view.getUint16(position + 10, true);
      const size = view.getUint32(position + 20, true);
      const expectedSize = view.getUint32(position + 24, true);
      const local = view.getUint32(position + 42, true);
      if (local + 30 > buffer.byteLength || view.getUint32(local, true) !== 0x04034b50) throw new Error('ZIP 本地头损坏');
      const start = local + 30 + view.getUint16(local + 26, true) + view.getUint16(local + 28, true);
      if (start + size > position) throw new Error('ZIP 内容越界');
      const compressed = buffer.slice(start, start + size);
      let result;
      if (method === 0) result = compressed;
      else if (method === 8) result = await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer();
      else throw new Error('不支持的 ZIP 压缩格式');
      if (result.byteLength !== expectedSize) throw new Error('ZIP 解压长度不一致');
      return result;
    }
    position = end;
  }
  throw new Error('恢复包内未找到原件');
}

export function formatXmlReading(xml, { showSectionNumbers = false } = {}) {
  const document = new DOMParser().parseFromString(xml, 'application/xml');
  if (document.getElementsByTagName('parsererror').length) throw new Error('原件 XML 无法解析');
  const body = document.getElementsByTagNameNS('*', 'body')[0];
  if (!body) throw new Error('原件缺少正文');
  const gaiji = new Map();
  for (const char of document.getElementsByTagNameNS('*', 'char')) {
    const mappings = [...char.getElementsByTagNameNS('*', 'mapping')];
    for (const kind of ['unicode', 'normal_unicode', 'normal']) {
      const mapping = mappings.find((entry) => entry.getAttribute('type') === kind && entry.textContent.trim());
      if (!mapping) continue;
      let value = mapping.textContent.trim();
      if (/^U\+[0-9a-f]+(?:\s+U\+[0-9a-f]+)*$/i.test(value)) value = value.split(/\s+/).map((point) => String.fromCodePoint(Number.parseInt(point.slice(2), 16))).join('');
      gaiji.set(char.getAttribute('xml:id'), value);
      break;
    }
  }
  function render(node) {
    if (node.nodeType === 3 || node.nodeType === 4) return node.textContent.replace(/\r?\n[ \t]*/g, '');
    if (node.nodeType !== 1) return '';
    const tag = node.localName;
    if (['lb', 'pb', 'mulu', 'milestone', 'anchor'].includes(tag)) return '';
    if (tag === 'g') {
      const identifier = (node.getAttribute('ref') || '').replace(/^#/, '');
      return node.textContent || gaiji.get(identifier) || `[${identifier}]`;
    }
    const text = [...node.childNodes].map(render).join('');
    if (tag === 'docNumber') return showSectionNumbers ? `\n\n${text}\n\n` : '';
    if (tag === 'head') {
      const numeric = /^[第卷章節节段〇零一二三四五六七八九十百千萬万億亿兩两\d\s、．.（）()—-]+$/u.test(text.trim());
      if (numeric && !showSectionNumbers) return '';
      return `\n\n${text}\n\n`;
    }
    if (tag === 'note') return `【校注：${text}】`;
    if (tag === 'rdg') return `【異讀：${text}】`;
    if (tag === 'l') return `${text}\n`;
    if (['p', 'div', 'lg', 'juan', 'item', 'trailer', 'byline', 'docAuthor', 'signed', 'dateline', 'opener', 'closer'].includes(tag)) return `\n\n${text}\n\n`;
    return text;
  }
  return render(body).replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}
