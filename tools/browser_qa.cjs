const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '../public');
const output = path.resolve(__dirname, '../..');
const contentTypes = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.zip': 'application/zip', '.txt': 'text/plain; charset=utf-8' };
const server = http.createServer((request, response) => {
  let pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  if (pathname.startsWith('/dharma-archive/')) pathname = pathname.slice('/dharma-archive'.length);
  const filename = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
  if (!filename.startsWith(root + path.sep) || !fs.existsSync(filename) || !fs.statSync(filename).isFile()) {
    response.writeHead(404).end();
    return;
  }
  const size = fs.statSync(filename).size;
  const headers = { 'Content-Type': contentTypes[path.extname(filename)] || 'application/octet-stream', 'Accept-Ranges': 'bytes' };
  const range = request.headers.range?.match(/^bytes=(\d+)-(\d+)$/);
  if (range) {
    const start = Number(range[1]);
    const end = Math.min(Number(range[2]), size - 1);
    if (start > end || start >= size) return response.writeHead(416).end();
    response.writeHead(206, { ...headers, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1 });
    fs.createReadStream(filename, { start, end }).pipe(response);
  } else {
    response.writeHead(200, { ...headers, 'Content-Length': size });
    fs.createReadStream(filename).pipe(response);
  }
});

(async () => {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true });
  const errors = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', (error) => errors.push(error.message));
    const base = `http://127.0.0.1:${server.address().port}/dharma-archive/`;
    await page.goto(base, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#catalog-body tr');
    const documents = await page.locator('#stat-documents').innerText();
    await page.locator('#search').fill('T08n0251');
    await page.waitForTimeout(250);
    await page.locator('.read-link').first().click();
    await page.waitForFunction(() => document.querySelector('#reader-state').textContent.includes('校验通过'));
    const heartTitle = await page.locator('#reader-title').innerText();
    await page.locator('#close-reader').click();
    let shardFallbackObserved = false;
    await page.route('**/data/packages/**', async (route) => {
      const requested = new URL(route.request().url());
      if (requested.hostname === 'raw.githubusercontent.com' && requested.pathname.includes('dharma-archive-data-')) {
        const filename = path.join(root, 'data/packages', path.basename(requested.pathname));
        shardFallbackObserved = true;
        await route.fulfill({ status: 200, body: fs.readFileSync(filename), headers: { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/zip' } });
      } else {
        await route.fulfill({ status: 200, body: 'deliberately damaged primary bytes', headers: { 'Access-Control-Allow-Origin': '*' } });
      }
    });
    await page.locator('.read-link').first().click();
    await page.waitForFunction(() => document.querySelector('#reader-state').textContent.includes('校验通过'));
    if (!shardFallbackObserved) throw new Error('Corrupt primary did not fall back to a registered GitHub shard');
    await page.locator('#close-reader').click();
    await page.unroute('**/data/packages/**');
    await page.locator('#search').fill('');
    await page.waitForTimeout(250);
    await page.screenshot({ path: path.join(output, 'dharma-archive-desktop.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    if (mobileOverflow) throw new Error('Horizontal overflow on mobile');
    await page.screenshot({ path: path.join(output, 'dharma-archive-mobile.png') });
    await page.locator('[data-tab=packages]').click();
    await page.waitForSelector('.package-row');
    const packagesVisible = await page.locator('.package-row').count();
    if (errors.length) throw new Error(errors.join('; '));
    const receipt = { ok: true, tested_base_path: '/dharma-archive/', documents, heartTitle, zip_range_read_sha256: 'passed', corrupt_primary_shard_fallback: shardFallbackObserved, mobile_width: 390, mobileOverflow, packagesVisible, browser_errors: errors };
    fs.writeFileSync(path.join(output, 'browser-qa.json'), JSON.stringify(receipt, null, 2) + '\n');
    console.log(JSON.stringify(receipt));
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => { console.error(error.message); process.exitCode = 1; server.close(); });
