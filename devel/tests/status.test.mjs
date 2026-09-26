import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
const script = readFileSync(new URL('../status.js', import.meta.url), 'utf8');
const builtAt = '2026-09-23T06:50:39.444050+00:00';
const built = Date.parse(builtAt);
const sha = 'a'.repeat(40);

async function setup({age = 0, fail = false, upstream = sha, iso = builtAt} = {}) {
  let now = built + age;
  let requests = 0;
  const nodes = {
    'preview-built-at': {dateTime: iso}, 'preview-relative-time': {textContent: ''},
    'preview-freshness': {textContent: ''}, 'devel-preview-status': {dataset: {sourceSha: sha}},
  };
  const timers = [];
  const listeners = {};
  const document = {hidden: false, getElementById: id => nodes[id],
    addEventListener: (name, fn) => {listeners[name] = fn;}};
  class Clock extends Date { static now() { return now; } }
  const context = vm.createContext({document, Date: Clock, Intl, AbortSignal,
    setInterval: (fn, delay) => {timers.push({fn, delay});},
    fetch: async () => {
      requests++;
      if (fail) throw new Error('offline');
      return {ok: true, json: async () => ({object: {sha: upstream}})};
    },
  });
  vm.runInContext(script, context);
  await new Promise(resolve => setImmediate(resolve));
  return {context, nodes, timers, listeners, document, setAge: age => {now = built + age;}, requests: () => requests};
}

test('formats absolute elapsed time across minute/hour/day boundaries', async () => {
  const {context} = await setup();
  const cases = [[0, 'Built just now'], [59000, 'Built just now'], [60000, 'Built 1 minute ago'],
    [300000, 'Built 5 minutes ago'], [3600000, 'Built 1 hour ago'], [21600000, 'Built 6 hours ago'],
    [86400000, 'Built 1 day ago'], [172800000, 'Built 2 days ago']];
  for (const [age, expected] of cases) assert.equal(context.relativeBuildTime(builtAt, built + age), expected);
});

test('initializes immediately and ticks every 30 seconds without extra requests', async () => {
  const s = await setup({age: 300000});
  assert.equal(s.nodes['preview-relative-time'].textContent, 'Built 5 minutes ago');
  assert.equal(s.timers.length, 1);
  assert.equal(s.timers[0].delay, 30000);
  s.setAge(360000);
  s.timers[0].fn();
  assert.equal(s.nodes['preview-relative-time'].textContent, 'Built 6 minutes ago');
  assert.equal(s.requests(), 1);
});

test('tab return catches up from fixed build time without replacing loaded SHA', async () => {
  const s = await setup({upstream: 'b'.repeat(40)});
  s.document.hidden = true;
  s.setAge(21600000);
  s.listeners.visibilitychange();
  assert.equal(s.nodes['preview-relative-time'].textContent, 'Built just now');
  s.document.hidden = false;
  s.listeners.visibilitychange();
  assert.equal(s.nodes['preview-relative-time'].textContent, 'Built 6 hours ago');
  assert.equal(s.nodes['devel-preview-status'].dataset.sourceSha, sha);
  assert.equal(s.nodes['preview-built-at'].dateTime, builtAt);
  assert.equal(s.nodes['preview-freshness'].textContent, '갱신 대기 (최신 bbbbbbbbbbbb)');
  assert.equal(s.requests(), 1);
});

test('freshness API failure does not interrupt local elapsed time', async () => {
  const s = await setup({fail: true});
  assert.equal(s.nodes['preview-freshness'].textContent, '최신 여부 확인 불가');
  s.setAge(60000);
  s.timers[0].fn();
  assert.equal(s.nodes['preview-relative-time'].textContent, 'Built 1 minute ago');
});

test('invalid time is explicit, client clock behind build never gives negative age', async () => {
  const s = await setup({iso: 'invalid'});
  assert.equal(s.nodes['preview-relative-time'].textContent, '빌드 시각 확인 불가');
  assert.equal(s.context.relativeBuildTime(builtAt, built - 60000), 'Built just now');
});

test('refreshing the page preserves age and freshness compares displayed SHA', async () => {
  const a = await setup({age: 3600000});
  const b = await setup({age: 3660000});
  assert.equal(a.nodes['preview-relative-time'].textContent, 'Built 1 hour ago');
  assert.equal(b.nodes['preview-relative-time'].textContent, 'Built 1 hour ago');
  assert.equal(b.nodes['preview-freshness'].textContent, '조회 시점 최신 devel');
});

test('malformed upstream SHA is never called latest', async () => {
  const s = await setup({upstream: 'bad'});
  assert.equal(s.nodes['preview-freshness'].textContent, '최신 여부 확인 불가');
});
