import assert from 'node:assert/strict';
import test, {before, after} from 'node:test';
import {createRequire} from 'node:module';
import {mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve, join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {assertHwpxText, confirmSaveAs, waitForDocumentReady} from '../smoke-ui.mjs';

const require = createRequire(resolve(process.env.RHWP_SOURCE || 'source', 'rhwp-studio/package.json'));
const puppeteer = require('puppeteer-core');
let browser;
before(async () => {
  browser = await puppeteer.launch({executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage']});
});
after(async () => { await browser?.close(); });

async function fixture(t) {
  const page = await browser.newPage();
  t.after(() => page.close());
  await page.setContent('<title>reopened.hwpx</title><div id="scroll-container"><canvas></canvas></div><span id="sb-message">reopened.hwpx — 1페이지</span>');
  await page.evaluate(() => {
    window.context = {hasDocument: true, isDirty: false, canUndo: false};
    window.rhwpStudio = {automation: {getContext: () => window.context}};
    window.detectClicks = 0;
    window.substituteClicks = 0;
    window.confirmClicks = 0;
    window.addFontPrompt = () => {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.innerHTML = '<div class="dialog-wrap"><div class="dialog-title">로컬 글꼴 감지<button>×</button></div><div class="dialog-footer"><button class="dialog-btn-primary">로컬 글꼴 감지 (권장)</button><button class="substitute">대체 글꼴로 보기</button></div></div>';
      overlay.querySelector('.dialog-btn-primary').onclick = () => window.detectClicks++;
      overlay.querySelector('.substitute').onclick = () => {
        window.substituteClicks++;
        overlay.remove();
        setTimeout(() => {
          document.getElementById('sb-message').textContent = 'reopened.hwpx — 1페이지';
          document.documentElement.classList.remove('rhwp-busy');
        }, 50);
      };
      document.body.append(overlay);
    };
    window.addSaveDialog = () => {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.innerHTML = '<div class="dialog-wrap"><div class="dialog-title">다른 이름으로 저장<button>×</button></div><div class="dialog-body"><input type="text" value="old-name"></div><div class="dialog-footer"><button class="dialog-btn-primary">확인</button></div></div>';
      overlay.querySelector('.dialog-btn-primary').onclick = () => {
        window.savedName = overlay.querySelector('input').value;
        window.confirmClicks++;
        overlay.remove();
      };
      document.body.append(overlay);
    };
  });
  return page;
}

test('already-ready document needs no font prompt', async t => {
  const page = await fixture(t);
  assert.deepEqual(await waitForDocumentReady(page, 'reopened.hwpx'), {filename: 'reopened.hwpx', fontPrompts: 0});
});

test('title arrives before delayed font prompt and document initialization', async t => {
  const page = await fixture(t);
  await page.evaluate(() => {
    document.getElementById('sb-message').textContent = '파일 로딩 50% - 문서 초기화 중...';
    document.documentElement.classList.add('rhwp-busy');
    setTimeout(window.addFontPrompt, 100);
  });
  const result = await waitForDocumentReady(page, 'reopened.hwpx', {timeout: 3000});
  assert.equal(result.fontPrompts, 1);
  assert.deepEqual(await page.evaluate(() => [window.detectClicks, window.substituteClicks,
    document.documentElement.classList.contains('rhwp-busy'), document.querySelectorAll('.modal-overlay').length]),
  [0, 1, false, 0]);
});

test('ready status still waits for the final busy-to-idle transition', async t => {
  const page = await fixture(t);
  await page.evaluate(() => {
    document.documentElement.classList.add('rhwp-busy');
    window.initializationFinished = false;
    setTimeout(() => {
      window.initializationFinished = true;
      document.documentElement.classList.remove('rhwp-busy');
    }, 100);
  });
  await waitForDocumentReady(page, 'reopened.hwpx', {timeout: 3000});
  assert.equal(await page.evaluate(() => window.initializationFinished), true);
});

test('unknown modal fails closed without clicking its primary action', async t => {
  const page = await fixture(t);
  await page.evaluate(() => {
    window.addSaveDialog();
    document.querySelector('.dialog-title').firstChild.textContent = 'Unexpected warning';
  });
  await assert.rejects(waitForDocumentReady(page, 'reopened.hwpx', {timeout: 250}), /Waiting failed/);
  assert.equal(await page.evaluate(() => window.confirmClicks), 0);
});

test('stale status, busy state, dirty state, and old history cannot prove a reopened document ready', async t => {
  const page = await fixture(t);
  for (const state of ['status', 'busy', 'dirty', 'history']) {
    await page.evaluate(state => {
      document.getElementById('sb-message').textContent = state === 'status' ? 'old.hwpx' : 'reopened.hwpx';
      document.documentElement.classList.toggle('rhwp-busy', state === 'busy');
      window.context.isDirty = state === 'dirty';
      window.context.canUndo = state === 'history';
    }, state);
    await assert.rejects(waitForDocumentReady(page, 'reopened.hwpx', {timeout: 150}), /Waiting failed/);
  }
});

test('Save As confirms only its own input and primary button, never the font prompt', async t => {
  const page = await fixture(t);
  await page.evaluate(() => { window.addFontPrompt(); window.addSaveDialog(); });
  await confirmSaveAs(page, 'roundtrip-second.hwpx');
  assert.deepEqual(await page.evaluate(() => [window.savedName, window.confirmClicks, window.detectClicks,
    window.substituteClicks]), ['roundtrip-second', 1, 0, 0]);
});

test('font dialog above Save As prevents an obscured Save As click', async t => {
  const page = await fixture(t);
  await page.evaluate(() => { window.addSaveDialog(); window.addFontPrompt(); });
  await assert.rejects(confirmSaveAs(page, 'roundtrip-second.hwpx', {timeout: 250}), /Waiting failed/);
  assert.deepEqual(await page.evaluate(() => [window.confirmClicks, window.detectClicks, window.substituteClicks]), [0, 0, 0]);
});

test('hidden stale dialogs cannot steal Save As controls', async t => {
  const page = await fixture(t);
  await page.evaluate(() => {
    window.addSaveDialog();
    document.querySelector('.modal-overlay').style.display = 'none';
    window.addSaveDialog();
  });
  await confirmSaveAs(page, 'fresh.hwpx');
  assert.deepEqual(await page.evaluate(() => [window.savedName, document.querySelector('input').value]), ['fresh', 'old-name']);
});

test('second saved HWPX must contain the original and post-reopen edit markers', async t => {
  const dir = await mkdtemp(join(tmpdir(), 'preview-smoke-xml-'));
  t.after(() => rm(dir, {recursive: true, force: true}));
  const path = join(dir, 'roundtrip.hwpx');
  const write = text => execFileSync('python3', ['-c',
    'import sys,zipfile; z=zipfile.ZipFile(sys.argv[1],"w"); z.writestr("Contents/section0.xml", "<section><text>"+sys.argv[2]+"</text></section>")', path, text]);
  write('original marker');
  assertHwpxText(path, ['original marker']);
  assert.throws(() => assertHwpxText(path, ['original marker', 'edited after reopen']));
  write('original marker edited after reopen');
  assertHwpxText(path, ['original marker', 'edited after reopen']);
  assert.throws(() => assertHwpxText(path, ['missing original', 'edited after reopen']));
});
