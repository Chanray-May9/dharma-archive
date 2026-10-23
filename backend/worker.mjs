const headers = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'X-Content-Type-Options': 'nosniff',
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers });
    if (!['GET', 'HEAD'].includes(request.method)) {
      return Response.json({ error: 'read_only' }, { status: 405, headers });
    }
    if (url.pathname === '/api/health') {
      return Response.json({ ok: true, storage: 'independent-static-files', billing: 'no-paid-resources-created' }, { headers });
    }
    const routes = {
      '/api/catalog': '/data/catalog.json',
      '/api/status': '/data/status.json',
      '/api/packages': '/data/packages.json',
      '/api/sources': '/data/sources.json',
    };
    if (url.pathname.startsWith('/api/')) {
      const target = routes[url.pathname];
      if (!target) return Response.json({ error: 'not_found' }, { status: 404, headers });
      url.pathname = target;
      url.search = '';
      const upstream = await env.ASSETS.fetch(new Request(url, { method: request.method }));
      const responseHeaders = new Headers(upstream.headers);
      for (const [key, value] of Object.entries(headers)) responseHeaders.set(key, value);
      responseHeaders.set('Cache-Control', 'public, max-age=300');
      return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
    }
    return env.ASSETS.fetch(request);
  },
};
