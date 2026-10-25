import assert from 'node:assert/strict';
import test from 'node:test';
import { extractZipMember } from '../public/reader-layout.js';

const fixtures = [
  'UEsDBBQAAAAAAAuJWV2mGyQaGgAAABoAAAARAAAAZGF0YS9vcmlnaW5hbC54bWw8Ym9keT48cD7mraPmloc8L3A+PC9ib2R5PlBLAQIUABQAAAAAAAuJWV2mGyQaGgAAABoAAAARAAAAAAAAAAAAAACAAQAAAABkYXRhL29yaWdpbmFsLnhtbFBLBQYAAAAAAQABAD8AAABJAAAAAAA=',
  'UEsDBBQAAAAIAAuJWV2mGyQaGQAAABoAAAARAAAAZGF0YS9vcmlnaW5hbC54bWyzScpPqbSzKbB7tnbxs2ntNvoFdjb6YDEAUEsBAhQAFAAAAAgAC4lZXaYbJBoZAAAAGgAAABEAAAAAAAAAAAAAAIABAAAAAGRhdGEvb3JpZ2luYWwueG1sUEsFBgAAAAABAAEAPwAAAEgAAAAAAA=='
];

test('extract exact UTF-8 original bytes from stored and DEFLATE ZIP members', async () => {
  for (const fixture of fixtures) {
    const buffer = Uint8Array.from(Buffer.from(fixture, 'base64')).buffer;
    const bytes = await extractZipMember(buffer, 'data/original.xml');
    assert.equal(new TextDecoder().decode(bytes), '<body><p>正文</p></body>');
  }
});

test('reject truncated ZIP archives and missing original members', async () => {
  await assert.rejects(extractZipMember(new ArrayBuffer(4), 'missing'), /ZIP/);
  const buffer = Uint8Array.from(Buffer.from(fixtures[0], 'base64')).buffer;
  await assert.rejects(extractZipMember(buffer, 'missing'), /未找到/);
  await assert.rejects(extractZipMember(buffer.slice(0, -1), 'data/original.xml'), /ZIP/);
});
