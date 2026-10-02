// Browser checklist for the dashboard, with no dependencies: starts tests/replay/serve.py and a headless
// Chrome, drives the page over the DevTools protocol and prints one line per check.
//
//   node tests/ui/check.mjs          short list (C1-C6, C15)
//   node tests/ui/check.mjs --full   every check
//
// CHROME_BIN, TAP_UI_PORT (default 8901) and TAP_DEBUG_PORT (default 9334) override the defaults.

import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const FULL = process.argv.includes('--full');
const UI_PORT = process.env.TAP_UI_PORT || '8901';
const DEBUG_PORT = process.env.TAP_DEBUG_PORT || '9334';
const CHROME = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const URL = `http://127.0.0.1:${UI_PORT}/`;

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
const children = [];
let profile;

function cleanup() {
  for (const child of children) child.kill();
  if (profile) rmSync(profile, { recursive: true, force: true });
}

async function until(what, probe, timeout = 8000) {
  const end = Date.now() + timeout;
  for (;;) {
    try {
      const value = await probe();
      if (value) return value;
    } catch {
      /* not ready yet */
    }
    if (Date.now() > end) throw new Error(`timeout waiting for ${what}`);
    await sleep(100);
  }
}

// ---------- processes ----------

async function startServer() {
  const busy = await fetch(URL).then(() => true, () => false);
  if (busy) throw new Error(`port ${UI_PORT} is already in use: stop the other serve.py first`);
  const env = { ...process.env, TAP_UI_PORT: UI_PORT };
  children.push(spawn(join(ROOT, 'venv/bin/python'), [join(ROOT, 'tests/replay/serve.py')], { env, stdio: 'ignore' }));
  await until('serve.py', () => fetch(URL).then((res) => res.ok));
}

async function startChrome() {
  profile = mkdtempSync(join(tmpdir(), 'tap-ui-'));
  const args = ['--headless=new', `--remote-debugging-port=${DEBUG_PORT}`, `--user-data-dir=${profile}`, '--no-first-run', '--window-size=1600,900', 'about:blank'];
  children.push(spawn(CHROME, args, { stdio: 'ignore' }));
  const base = `http://127.0.0.1:${DEBUG_PORT}`;
  await until('chrome', () => fetch(`${base}/json/version`).then((res) => res.ok));
  const target = await fetch(`${base}/json/new?about:blank`, { method: 'PUT' }).then((res) => res.json());
  return target.webSocketDebuggerUrl;
}

// ---------- DevTools protocol ----------

function connect(wsUrl) {
  const socket = new WebSocket(wsUrl);
  const pending = new Map();
  const problems = [];
  let nextId = 1;
  socket.onmessage = (message) => {
    const data = JSON.parse(message.data);
    if (data.id) {
      const { done, fail } = pending.get(data.id);
      pending.delete(data.id);
      if (data.error) fail(new Error(data.error.message));
      else done(data.result);
      return;
    }
    const p = data.params;
    if (data.method === 'Runtime.exceptionThrown') problems.push('exception: ' + (p.exceptionDetails.exception?.description || p.exceptionDetails.text));
    if (data.method === 'Runtime.consoleAPICalled' && p.type === 'error') problems.push('console.error: ' + p.args.map((a) => a.value ?? a.description).join(' '));
    if (data.method === 'Network.responseReceived' && p.response.status >= 400) problems.push(`${p.response.status} ${p.response.url}`);
  };
  const send = (method, params = {}) =>
    new Promise((done, fail) => {
      const id = nextId++;
      pending.set(id, { done, fail });
      socket.send(JSON.stringify({ id, method, params }));
    });
  const opened = new Promise((done, fail) => {
    socket.onopen = done;
    socket.onerror = () => fail(new Error('cannot connect to chrome'));
  });
  return { send, opened, problems };
}

// ---------- checks ----------

async function main() {
  await startServer();
  const page = connect(await startChrome());
  await page.opened;
  for (const domain of ['Runtime', 'Network', 'Page']) await page.send(`${domain}.enable`);

  const js = async (expression) => {
    const { result, exceptionDetails } = await page.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (exceptionDetails) throw new Error(exceptionDetails.exception?.description || exceptionDetails.text);
    return result.value;
  };
  const click = (selector) => js(`document.querySelector(${JSON.stringify(selector)}).click()`);
  const KEYS = { Escape: 27, ArrowDown: 40, '/': 191 };
  const press = async (key) => {
    const event = { key, code: key === '/' ? 'Slash' : key, windowsVirtualKeyCode: KEYS[key] };
    await page.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', ...event });
    await page.send('Input.dispatchKeyEvent', { type: 'keyUp', ...event });
  };
  const type = (selector, value, eventName) =>
    js(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); el.value = ${JSON.stringify(value)}; el.dispatchEvent(new Event('${eventName}', { bubbles: true })); })()`);
  const rows = () => js(`document.querySelectorAll('#rows tr').length`);
  const text = (selector) => js(`document.querySelector(${JSON.stringify(selector)})?.textContent ?? null`);
  const hidden = (selector) => js(`document.querySelector(${JSON.stringify(selector)}).hidden`);

  let failed = 0;
  const check = async (name, what, run) => {
    try {
      const detail = await run();
      console.log(`ok   ${name}  ${what}`);
      return detail;
    } catch (error) {
      failed++;
      console.log(`FAIL ${name}  ${what}: ${error.message}`);
    }
  };
  const expect = (actual, expected, label) => {
    if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  };
  const expectRows = async (expected, label) => {
    await until(label, async () => (await rows()) === expected, 3000).catch(() => {});
    expect(await rows(), expected, label);
  };
  const detailHas = async (...parts) => {
    const missing = async () => {
      if (await hidden('#detail')) return ['(detail is hidden)'];
      const content = (await text('#detail')) || '';
      return parts.filter((part) => !content.includes(part));
    };
    await until('detail', async () => (await missing()).length === 0, 4000).catch(() => {});
    const left = await missing();
    if (left.length) throw new Error(`detail lacks ${left.join(', ')}`);
  };

  await page.send('Page.navigate', { url: URL });
  await until('rows', async () => (await rows()) > 0).catch(() => {});

  await check('C2', '44 rows and live connection', async () => {
    await expectRows(44, 'rows');
    await until('live', async () => (await text('#conn-text')) === 'en vivo', 4000).catch(() => {});
    expect(await text('#conn-text'), 'en vivo', '#conn-text');
  });
  await check('C3', 'header counters', async () => {
    const got = await js(`['s-n','s-hit','s-miss','s-srv','s-eff','s-rate'].map((id) => document.getElementById(id).textContent)`);
    expect(got, ['44', '9', '9', '2', '2 / 3', '33.6 %'], 'counters');
  });
  await check('C4', 'click on row 6 opens its detail', async () => {
    await click('#rows tr[data-id="6"]');
    await detailHas('#6', 'MISS', 'Primer cambio del prefijo', 'system @ 40');
  });
  await check('C5', 'Escape closes, ArrowDown opens the first row', async () => {
    await press('Escape');
    expect(await hidden('#detail'), true, 'detail hidden after Escape');
    await press('ArrowDown');
    await detailHas('#44');
  });
  await check('C6', 'miss / partial toggle', async () => {
    await press('Escape');
    await click('#f-bad');
    await expectRows(10, 'rows with the toggle on');
    await click('#f-bad');
    await expectRows(44, 'rows with the toggle off');
  });
  await check('C15', 'a live cache timer counts down', async () => {
    const read = () => js(`document.querySelector('.ttl[data-from]:not(.stopped) .ttl-text')?.textContent ?? null`);
    const before = await read();
    if (before == null) throw new Error('no live timer found');
    await sleep(2100);
    if ((await read()) === before) throw new Error(`timer stuck at ${before}`);
  });

  if (FULL) {
    await check('C7', 'effort change toggle', async () => {
      await click('#f-eff');
      await expectRows(3, 'rows with the toggle on');
      await click('#f-eff');
      await expectRows(44, 'rows with the toggle off');
    });
    await check('C8', 'model filter', async () => {
      await type('#f-model', 'gpt-5.6', 'change');
      await expectRows(5, 'rows for gpt-5.6');
      await type('#f-model', '', 'change');
      await expectRows(44, 'rows without filter');
    });
    await check('C9', 'text filter and reset', async () => {
      await type('#f-text', 'c13', 'input');
      await expectRows(3, 'rows for c13');
      await type('#f-text', 'zzz', 'input');
      await expectRows(0, 'rows for zzz');
      expect(await hidden('#no-match'), false, '#no-match hidden');
      await click('#reset');
      await expectRows(44, 'rows after reset');
      expect(await js(`document.getElementById('f-text').value`), '', '#f-text value');
    });
    await check('C10', 'slash focuses the filter', async () => {
      await js(`document.activeElement.blur()`);
      await press('/');
      expect(await js(`document.activeElement.id`), 'f-text', 'focused element');
      await js(`document.activeElement.blur()`);
    });
    await check('C11', 'request body loads as a tree', async () => {
      await click('#rows tr[data-id="1"]');
      await detailHas('#1');
      if (!(await js(`document.querySelector('[data-sec="body"]').open`))) await click('[data-sec="body"] > summary');
      await until('body tree', async () => ((await text('[data-tree="body"]')) || '').includes('model'), 4000).catch(() => {});
      const body = (await text('[data-tree="body"]')) || '';
      if (!body.includes('model') || body.includes('cargando')) throw new Error(`body section shows ${JSON.stringify(body.slice(0, 60))}`);
    });
    await check('C13', 'resizer visible with the detail open', async () => {
      expect(await hidden('#resizer'), false, '#resizer hidden');
    });
    await check('C12', 'help dialog and its tables', async () => {
      await click('#help-open');
      expect(await js(`document.getElementById('help').open`), true, 'dialog open');
      await until('help tables', () => js(`document.querySelectorAll('#help table')[1].tBodies[0].rows.length > 0`), 3000).catch(() => {});
      const sizes = await js(`[...document.querySelectorAll('#help table')].map((table) => table.tBodies[0].rows.length)`);
      const minimum = (await js(`!!document.getElementById('help-min')`)) ? 5 : 4;
      expect(sizes, [5, 5, minimum], 'rows per help table');
      await js(`document.getElementById('help').close()`);
    });
    await check('C16', 'the bundled fonts load', async () => {
      await js(`document.fonts.ready.then(() => true)`);
      const loaded = await js(`[...document.fonts].filter((font) => font.status === 'loaded').length`);
      if (!loaded) throw new Error('no font face reached status "loaded"');
    });
    await check('C14', 'clear takes two clicks', async () => {
      await click('#clear');
      await click('#clear');
      await expectRows(0, 'rows after clearing');
      expect(await hidden('#empty'), false, '#empty hidden');
    });
  }

  await check('C1', 'no console errors, exceptions or failed requests', async () => {
    if (page.problems.length) throw new Error(page.problems.slice(0, 5).join(' | '));
  });

  console.log(failed ? `\n${failed} check(s) failed` : `\nall checks passed (${FULL ? 'full' : 'short'} list)`);
  return failed ? 1 : 0;
}

let code = 1;
try {
  code = await main();
} catch (error) {
  console.log(`FAIL setup: ${error.message}`);
} finally {
  cleanup();
}
process.exit(code);
