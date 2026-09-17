// Exercise the built release app at the actual project subpath, never Vite dev mode.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {readFile, mkdir, writeFile, stat} from 'node:fs/promises';
import {resolve, extname, sep} from 'node:path';
const source = resolve(process.argv[2]);
const dist = resolve(source, 'rhwp-studio/dist');
const require = createRequire(resolve(source, 'rhwp-studio/package.json'));
const puppeteer = require('puppeteer-core');
const base = '/rhwp-preview-lab/';
const mime = {'.html': 'text/html', '.js': 'application/javascript', '.wasm': 'application/wasm',
  '.css': 'text/css', '.json': 'application/json', '.woff2': 'font/woff2', '.svg': 'image/svg+xml'};
const server = createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    assert(pathname.startsWith(base));
    const file = resolve(dist, pathname.slice(base.length) || 'index.html');
    assert(file.startsWith(dist + sep));
    assert((await stat(file)).isFile());
    res.setHeader('Content-Type', mime[extname(file)] || 'application/octet-stream');
    res.end(await readFile(file));
  } catch { res.writeHead(404).end(); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const origin = `http://127.0.0.1:${server.address().port}`;
await mkdir('smoke-evidence', {recursive: true});
const evidence = {url: origin + base, requests: [], errors: [], console: [], roundtrip: null};
let browser;
let page;
try {
  browser = await puppeteer.launch({executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  page = await browser.newPage();
  await page.setViewport({width: 1400, height: 1000});
  page.on('pageerror', e => evidence.errors.push(String(e)));
  page.on('console', msg => { if (['error', 'warn'].includes(msg.type())) evidence.console.push(msg.text()); });
  page.on('response', r => {
    if (r.url().startsWith(origin)) evidence.requests.push({url: r.url().slice(origin.length), status: r.status(), mime: r.headers()['content-type']});
  });
  await page.evaluateOnNewDocument(() => {
    localStorage.setItem('rhwp-settings', JSON.stringify({version: 1, theme: {mode: 'system', skin: 'default', skinChosen: true}}));
  });
  await page.goto(origin + base + '?renderer=canvaskit', {waitUntil: 'networkidle0', timeout: 90000});
  await page.waitForFunction(() => window.rhwpStudio?.automation?.getContext().hasDocument, {timeout: 60000});
  const canvas = await page.waitForSelector('#scroll-container canvas', {timeout: 15000});
  const bounds = await canvas.boundingBox();
  await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + 100);
  const marker = 'devel Pages HWPX roundtrip';
  await page.keyboard.type(marker, {delay: 25});
  await page.waitForFunction(() => window.rhwpStudio.automation.getContext().canUndo);
  async function saveAsHwpx(filename) {
    // The real save command writes to a test file-picker sink; no dev globals.
    await page.evaluate(name => {
      window.__previewSaved = null;
      window.showSaveFilePicker = async () => ({name, createWritable: async () => ({
        write: async blob => {window.__previewSaved = Array.from(new Uint8Array(await blob.arrayBuffer()));},
        close: async () => {},
      })});
      const result = window.rhwpStudio.automation.execute('file:save-as-hwpx', undefined, {allowDialog: true});
      if (!result.ok) throw new Error(JSON.stringify(result));
    }, filename);
    await page.waitForSelector('.dialog-body input[type="text"]', {timeout: 10000});
    await page.click('.dialog-footer .dialog-btn-primary');
    await page.waitForFunction(() => window.__previewSaved?.length > 0, {timeout: 30000});
    const bytes = await page.evaluate(() => window.__previewSaved);
    assert.equal(bytes[0], 0x50); assert.equal(bytes[1], 0x4b);
    const path = resolve('smoke-evidence', filename);
    await writeFile(path, Buffer.from(bytes));
    execFileSync('python3', ['-c',
      'import sys,zipfile,xml.etree.ElementTree as E; z=zipfile.ZipFile(sys.argv[1]); text="".join("".join(E.fromstring(z.read(n)).itertext()) for n in z.namelist() if n.startswith("Contents/section") and n.endswith(".xml")); assert sys.argv[2] in text,repr(text)',
      path, marker]);
    return {path, bytes: bytes.length};
  }
  const first = await saveAsHwpx('roundtrip-original.hwpx');
  // Use a different file name so the title proves the normal file-open path completed.
  const reopenedPath = resolve('smoke-evidence/roundtrip-reopened.hwpx');
  await writeFile(reopenedPath, await readFile(first.path));
  await (await page.$('#file-input')).uploadFile(reopenedPath);
  await page.waitForFunction(() => document.title.includes('roundtrip-reopened.hwpx'), {timeout: 30000});
  const second = await saveAsHwpx('roundtrip-second.hwpx');
  evidence.roundtrip = {firstBytes: first.bytes, secondBytes: second.bytes, text: marker,
    verification: 'UI save -> HWPX XML text -> file input open -> UI save -> HWPX XML text'};
  evidence.metadata = JSON.parse(await readFile(resolve(dist, 'build.json'), 'utf8'));
  const layout = await page.evaluate(() => ({
    appBottom: document.getElementById('studio-root').getBoundingClientRect().bottom,
    bannerTop: document.getElementById('devel-preview-status').getBoundingClientRect().top,
  }));
  assert(layout.appBottom <= layout.bannerTop, 'preview status must not cover Studio controls');
  evidence.layout = layout;

  await page.screenshot({path: 'smoke-evidence/studio.png'});
  const failures = evidence.requests.filter(r => r.status >= 400 && !r.url.endsWith('favicon.ico'));
  assert.deepEqual(failures, [], 'local static requests must succeed under the project base');
  assert(evidence.requests.some(r => r.url.includes('rhwp') && r.url.endsWith('.wasm') && r.status === 200));
  assert(evidence.requests.some(r => r.url.includes('canvaskit') && r.url.endsWith('.wasm') && r.status === 200));
  assert(evidence.requests.some(r => r.url.includes('/fonts/') && r.status === 200));
  assert.deepEqual(evidence.errors, [], 'unhandled browser exceptions');
  evidence.passed = true;
} finally {
  if (page) {
    await page.screenshot({path: 'smoke-evidence/studio.png'}).catch(() => {});
    evidence.visibleText = await page.evaluate(() => document.body.innerText).catch(() => 'unavailable');
  }
  await writeFile('smoke-evidence/result.json', JSON.stringify(evidence, null, 2));
  await browser?.close();
  server.close();
}
