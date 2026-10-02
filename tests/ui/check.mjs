// Browser checklist for the dashboard, with no dependencies: starts tests/replay/serve.py and a headless
// Chrome, drives the page over the DevTools protocol and prints one line per check.
//
//   node tests/ui/check.mjs          short list (C1-C6, C15)
//   node tests/ui/check.mjs --full   every check
//   node tests/ui/check.mjs --styles out.json   also dump the computed styles of every element, to compare two versions of the CSS
//
// CHROME_BIN, TAP_UI_PORT (default 8901) and TAP_DEBUG_PORT (default 9334) override the defaults.

import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const FULL = process.argv.includes('--full');
const STYLES = process.argv.includes('--styles') ? process.argv[process.argv.indexOf('--styles') + 1] : null;
const UI_PORT = process.env.TAP_UI_PORT || '8901';
const DEBUG_PORT = process.env.TAP_DEBUG_PORT || '9334';
const CHROME = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const URL = `http://127.0.0.1:${UI_PORT}/`;

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
// every request has a deadline: a fetch that never connects would otherwise hang the whole run
const get = (url, options = {}) => fetch(url, { ...options, signal: AbortSignal.timeout(1500) });
const children = [];
let profile;

function cleanup() {
  for (const child of children) child.kill();
  if (!profile) return;
  try {
    // chrome may still be writing its profile for a moment after the kill
    rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
  } catch {
    /* a leftover temp folder must not turn a passing run into a failure */
  }
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
  const busy = await get(URL).then(() => true, () => false);
  if (busy) throw new Error(`port ${UI_PORT} is already in use: stop the other serve.py first`);
  const env = { ...process.env, TAP_UI_PORT: UI_PORT };
  children.push(spawn(join(ROOT, 'venv/bin/python'), [join(ROOT, 'tests/replay/serve.py')], { env, stdio: 'ignore' }));
  await until('serve.py', () => get(URL).then((res) => res.ok));
}

async function startChrome() {
  profile = mkdtempSync(join(tmpdir(), 'tap-ui-'));
  const args = ['--headless=new', `--remote-debugging-port=${DEBUG_PORT}`, `--user-data-dir=${profile}`, '--no-first-run', '--window-size=1600,900', 'about:blank'];
  children.push(spawn(CHROME, args, { stdio: 'ignore' }));
  // chrome binds its debugging port to IPv4 or to IPv6 depending on the run: take whichever answers
  const bases = [`http://127.0.0.1:${DEBUG_PORT}`, `http://[::1]:${DEBUG_PORT}`];
  const base = await until('chrome', async () => {
    for (const candidate of bases) {
      if (await get(`${candidate}/json/version`).then((res) => res.ok, () => false)) return candidate;
    }
    return null;
  }, 15000);
  const target = await get(`${base}/json/new?about:blank`, { method: 'PUT' }).then((res) => res.json());
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
  if (STYLES) {
    // layout-independent properties only: widths and timer texts change from one run to the next
    await js(`document.fonts.ready.then(() => true)`);
    await sleep(300);
    const props = ['display', 'position', 'color', 'background-color', 'font-family', 'font-size', 'font-weight', 'line-height', 'padding', 'margin', 'border', 'border-radius', 'text-align', 'white-space', 'overflow', 'gap', 'flex', 'opacity', 'cursor'];
    const styles = await js(`[...document.querySelectorAll('body, body *')].map((el) => {
      const computed = getComputedStyle(el);
      return el.tagName + '.' + el.className + '|' + ${JSON.stringify(props)}.map((p) => computed.getPropertyValue(p)).join(';');
    })`);
    writeFileSync(STYLES, JSON.stringify(styles, null, 1));
    console.log(`     styles of ${styles.length} elements written to ${STYLES}`);
  }
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
      if (minimum === 5) {
        const first = await js(`(() => { const row = document.querySelector('#help-ttl tr'); return [row.cells[0].textContent, [...row.querySelectorAll('code')].map((c) => c.textContent)]; })()`);
        expect(first, ['Claude (todos)', ['cache_control', 'ttl: "1h"']], 'first TTL row');
        const tokens = await js(`[...document.querySelectorAll('#help-min tr')].map((row) => row.cells[1].textContent)`);
        expect(tokens, ['512', '1.024', '2.048', '4.096', '1.024'], 'minimum cacheable column');
        expect(await text('#help-reviewed'), 'octubre de 2026', '#help-reviewed');
      }
      await js(`document.getElementById('help').close()`);
    });
    await check('C16', 'the bundled fonts load', async () => {
      await js(`document.fonts.ready.then(() => true)`);
      const loaded = await js(`[...document.fonts].filter((font) => font.status === 'loaded').length`);
      if (!loaded) throw new Error('no font face reached status "loaded"');
    });
    await check('C17', 'clear failure is visible and preserves local records', async () => {
      const result = await js(`(async () => {
        const original = window.fetch;
        window.fetch = async (url) => url === '/api/clear' ? new Response('', { status: 503 }) : original(url);
        try {
          document.getElementById('clear').click();
          document.getElementById('clear').click();
          await new Promise((resolve) => setTimeout(resolve, 0));
          return { status: document.getElementById('action-status').textContent,
            hidden: document.getElementById('action-status').hidden,
            disabled: document.getElementById('clear').disabled,
            rows: document.querySelectorAll('#rows tr').length };
        } finally { window.fetch = original; }
      })()`);
      expect(result, { status: 'No se pudieron limpiar las peticiones. Inténtalo de nuevo.', hidden: false, disabled: false, rows: 44 }, 'clear failure');
    });
    await check('C18', 'invalid SSE event reports error and reconnects once', async () => {
      const result = await js(`(async () => {
        const original = window.EventSource;
        const sources = [];
        window.EventSource = class {
          constructor(url) { this.url = url; this.closed = false; sources.push(this); }
          close() { this.closed = true; }
        };
        let stop;
        try {
          const { connect } = await import('/stream.js');
          stop = connect();
          sources[0].onmessage({ data: '{"type":"unknown"}' });
          const firstClosed = sources[0].closed;
          const status = document.getElementById('action-status').textContent;
          await new Promise((resolve) => setTimeout(resolve, 1100));
          const reconnects = sources.length;
          sources[1].onmessage({ data: '{"type":"unknown"}' });
          stop();
          await new Promise((resolve) => setTimeout(resolve, 1100));
          return { firstClosed, status, reconnects, afterClose: sources.length };
        } finally { stop?.(); window.EventSource = original; }
      })()`);
      expect(result, { firstClosed: true, status: 'Se recibió un evento inválido; reconectando.', reconnects: 2, afterClose: 2 }, 'invalid SSE recovery');
    });
    await check('C19', 'help failure is visible without a failed network request', async () => {
      const result = await js(`(async () => {
        const original = window.fetch;
        window.fetch = async (url) => url === '/api/reference' ? new Response('', { status: 503 }) : original(url);
        try {
          const { loadHelp } = await import('/help.js');
          await loadHelp();
          const status = document.getElementById('action-status');
          return { message: status.textContent, hidden: status.hidden };
        } finally { window.fetch = original; }
      })()`);
      expect(result, { message: 'No se pudo cargar la referencia de ayuda.', hidden: false }, 'help failure');
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

  await check('R1', 'retention event evicts selection, releases detail and renders retained records', async () => {
    const result = await js(`(async () => {
      const { state, applyEvent } = await import('/state.js');
      const { showDetail, closeDetail } = await import('/detail.js');
      const { render, syncFilters } = await import('/list.js');
      state.selected = null;
      const sample = (id) => ({ id, time: '12:00', state: 'done', verdict: 'HIT', model: 'gpt-test', conv: 'retention', n_tools: 0, n_msgs: 1, cc_marks: 0, req_bytes: 0, notes: [], usage: {}, effort_fields: {}, raw_usage: [], resp_headers: {}, output: '', segs: [] });
      applyEvent({ type: 'snapshot', ttl: 300, max_records: 2, recs: [sample(43), sample(44)] });
      render();
      await showDetail(44);
      const invalid = applyEvent({ type: 'evict', ids: [44] });
      if (invalid) closeDetail();
      syncFilters();
      render();
      return { invalid, selected: state.selected, hidden: document.getElementById('detail').hidden,
        detailChildren: document.getElementById('detail').childElementCount,
        rows: [...document.querySelectorAll('#rows tr')].map((row) => row.dataset.id) };
    })()`);
    expect(result, { invalid: true, selected: null, hidden: true, detailChildren: 0, rows: ['43'] }, 'retention UI state');
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
