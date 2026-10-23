import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../backend/worker.mjs';

test('API maps to the complete independent catalog and permits public CORS', async () => {
  let requested;
  const env = { ASSETS: { fetch: async (request) => {
    requested = request.url;
    return Response.json([{ id: 'example' }]);
  } } };
  const response = await worker.fetch(new Request('https://archive.example/api/catalog?unused=1'), env);
  assert.equal(requested, 'https://archive.example/data/catalog.json');
  assert.equal(response.headers.get('Access-Control-Allow-Origin'), '*');
  assert.deepEqual(await response.json(), [{ id: 'example' }]);
});

test('A missing file cannot silently become the frontend HTML', async () => {
  const env = { ASSETS: { fetch: async () => new Response('Missing', { status: 404 }) } };
  const response = await worker.fetch(new Request('https://archive.example/data/missing.zip'), env);
  assert.equal(response.status, 404);
});

test('Unknown API endpoints and mutations are rejected', async () => {
  assert.equal((await worker.fetch(new Request('https://archive.example/api/missing'), {})).status, 404);
  assert.equal((await worker.fetch(new Request('https://archive.example/api/catalog', { method: 'POST' }), {})).status, 405);
  assert.equal((await worker.fetch(new Request('https://archive.example/api/catalog', { method: 'OPTIONS' }), {})).status, 204);
});

test('HEAD stays a HEAD when forwarding to archive assets', async () => {
  const env = { ASSETS: { fetch: async (request) => {
    assert.equal(request.method, 'HEAD');
    return new Response(null);
  } } };
  assert.equal((await worker.fetch(new Request('https://archive.example/api/catalog', { method: 'HEAD' }), env)).status, 200);
});
