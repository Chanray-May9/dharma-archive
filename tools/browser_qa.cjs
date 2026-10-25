const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '../public');
const output = path.resolve(__dirname, '../..');
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.zip': 'application/zip', '.txt': 'text/plain; charset=utf-8' };
const server = http.createServer((request, response) => {
  let pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  if (pathname.startsWith('/dharma-archive/')) pathname = pathname.slice('/dharma-archive'.length);
  const filename = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
  if (!filename.startsWith(root + path.sep) || !fs.existsSync(filename) || !fs.statSync(filename).isFile()) return response.writeHead(404).end();
  const size = fs.statSync(filename).size;
  const headers = { 'Content-Type': types[path.extname(filename)] || 'application/octet-stream', 'Accept-Ranges': 'bytes' };
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
  const fetches = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.route('https://*.workers.dev/**', (route) => route.abort());
    const page = await context.newPage();
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (request) => { if (request.resourceType() === 'fetch') fetches.push(request.url()); });
    const base = `http://127.0.0.1:${server.address().port}/dharma-archive/`;
    await page.goto(base, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelector('#stat-languages').textContent === '38');
    assert.equal(await page.getByText('保存是一件持续的事').count(), 0);
    assert.equal(await page.locator('a[href="#library"]').count(), 0);
    await page.screenshot({ path: path.join(output, 'dharma-archive-desktop.png') });
    await page.locator('.stats a[href="languages.html"]').click();
    await page.waitForURL('**/languages.html');
    await page.waitForSelector('.language-card');
    assert.equal(await page.locator('.language-card').count(), 38);
    await page.reload();
    await page.waitForSelector('.language-card');
    await page.screenshot({ path: path.join(output, 'dharma-languages.png') });
    await page.locator('.language-card a[href*="language=lzh"]').first().click();
    await page.waitForSelector('#catalog-body tr');
    assert.equal(await page.locator('#language').inputValue(), 'lzh');
    assert.equal(await page.locator('#script-mode').inputValue(), 'simplified');
    await page.locator('#search').fill('心经');
    await page.waitForFunction(() => new URL(location.href).searchParams.get('q') === '心经');
    const simplifiedSearchCount = await page.locator('#results-count').innerText();
    await page.locator('#search').fill('心經');
    await page.waitForFunction(() => new URL(location.href).searchParams.get('q') === '心經');
    assert.equal(await page.locator('#results-count').innerText(), simplifiedSearchCount);
    await page.locator('#search').fill('T08n0251');
    await page.waitForFunction(() => new URL(location.href).searchParams.get('q') === 'T08n0251');
    assert.match(await page.locator('.document-title').first().innerText(), /般若波罗蜜多心经/);
    await page.screenshot({ path: path.join(output, 'dharma-library.png') });
    await page.locator('.read-link').first().click();
    await page.waitForURL('**/reader.html?**');
    await page.waitForFunction(() => document.querySelector('#reader-state').textContent.includes('校验通过'));
    assert.match(await page.locator('#reader-text').innerText(), /观自在菩萨/);
    assert.match(await page.locator('#download-original').getAttribute('href'), /^https:\/\/raw\.githubusercontent\.com\/Chanray-May9\/dharma-archive-data-001\/main\/data\/packages\//);
    await page.locator('#script-mode').selectOption('original');
    assert.match(await page.locator('#reader-text').innerText(), /觀自在菩薩/);
    await page.locator('#script-mode').selectOption('simplified');
    const downloading = page.waitForEvent('download');
    await page.locator('#download-text').click();
    const download = await downloading;
    assert.match(download.suggestedFilename(), /简体转换\.txt$/);
    assert.match(fs.readFileSync(await download.path(), 'utf8'), /观自在菩萨/);
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#reader-state').textContent.includes('简体转换显示'));
    await page.screenshot({ path: path.join(output, 'dharma-reader.png') });
    let shardFallbackObserved = false;
    await page.route('**/data/packages/**', async (route) => {
      const requested = new URL(route.request().url());
      if (requested.hostname === 'raw.githubusercontent.com' && requested.pathname.startsWith('/Chanray-May9/dharma-archive-data-')) {
        shardFallbackObserved = true;
        await route.fulfill({ status: 200, body: fs.readFileSync(path.join(root, 'data/packages', path.basename(requested.pathname))), headers: { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/zip' } });
      } else await route.fulfill({ status: 200, body: 'damaged primary bytes', headers: { 'Access-Control-Allow-Origin': '*' } });
    });
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#reader-state').textContent.includes('校验通过'));
    assert.ok(shardFallbackObserved);
    await page.unroute('**/data/packages/**');
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({ path: path.join(output, 'dharma-archive-mobile.png') });
    await page.locator('#back-to-library').click();
    await page.waitForSelector('#catalog-body tr');
    assert.equal(await page.locator('#search').inputValue(), 'T08n0251');
    await page.locator('[data-page-link="languages"]').click();
    await page.waitForSelector('.language-card');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.locator('.language-card a[href*="language=en"]').click();
    await page.waitForSelector('#catalog-body tr');
    assert.equal(await page.locator('#language').inputValue(), 'en');
    await page.locator('[data-page-link="packages"]').click();
    await page.waitForSelector('.package-row');
    assert.match(await page.locator('.package-row a').first().getAttribute('href'), /^https:\/\/raw\.githubusercontent\.com\/Chanray-May9\/dharma-archive-data-/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.locator('[data-page-link="recovery"]').click();
    await page.waitForURL('**/recovery.html');
    assert.equal(await page.getByText('保存是一件持续的事').count(), 0);
    assert.equal(await page.locator('a[href="RESTORE.py"]').count(), 1);
    const upstreamFetches = fetches.filter((url) => !url.startsWith('http://127.0.0.1:') && !url.startsWith('https://dharma-archive-api.gqr20080509.workers.dev/') && !url.startsWith('https://raw.githubusercontent.com/Chanray-May9/'));
    assert.deepEqual(upstreamFetches, []);
    assert.deepEqual(errors, []);
    const receipt = { ok: true, dedicated_pages: ['library', 'languages', 'packages', 'recovery', 'reader'], languages: 38, simplified_traditional_search: 'passed', simplified_reader_and_txt: 'passed', direct_reader_reload: 'passed', original_package_owner: 'Chanray-May9', upstream_fetches: upstreamFetches, corrupt_primary_shard_fallback: shardFallbackObserved, mobile_width: 390, browser_errors: errors };
    fs.writeFileSync(path.join(output, 'browser-qa.json'), JSON.stringify(receipt, null, 2) + '\n');
    console.log(JSON.stringify(receipt));
  } finally {
    await browser.close();
    server.close();
  }
})().catch((error) => { console.error(error.stack); process.exitCode = 1; server.close(); });
