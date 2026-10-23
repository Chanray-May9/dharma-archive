const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const cliPath = path.join(process.env.APPDATA, 'npm', 'node_modules', 'wrangler', 'wrangler-dist', 'cli.js');
let source = fs.readFileSync(cliPath, 'utf8');
const concurrency = 'BULK_UPLOAD_CONCURRENCY = 3;';
const uploadLoop = 'for (const [bucketIndex, bucket] of assetBuckets.entries()) {';
if (!source.includes(concurrency) || !source.includes(uploadLoop)) {
  throw new Error('This local transport adapter does not match the installed Wrangler version');
}
source = source.replace(concurrency, 'BULK_UPLOAD_CONCURRENCY = 1;');
source = source.replace(uploadLoop, 'for (const [bucketIndex, bucket] of assetBuckets.flatMap(bucket => bucket.map(entry => [entry])).entries()) {');
process.argv[1] = cliPath;
const runtime = new Module(cliPath);
runtime.filename = cliPath;
runtime.paths = Module._nodeModulePaths(path.dirname(cliPath));
runtime.id = '.';
process.mainModule = runtime;
Module._cache[cliPath] = runtime;
runtime._compile(source, cliPath);
