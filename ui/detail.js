import { jsonTree } from './json-tree.js';
import { state } from './state.js';
import { store } from './prefs.js';
import { $, esc, num, secs } from './format.js';
import { badge, shareBar } from './parts.js';
import { ttlLabel, timerHtml, tick } from './cache-timer.js';
import { render } from './list.js';

// ---------- detail ----------

const detail = $('detail');
const sectionsOpen = store.get('sections', {});
const treeStates = new Map(); // section key -> Map(path -> open), shared across requests
const copyable = new Map(); // section key -> value behind its "copiar" button
const trees = new Map();
let body = { id: null, value: undefined };
let generation = 0;

export function resetDetailCache() {
  generation++;
  body = { id: null, value: undefined };
  trees.clear();
  copyable.clear();
}

function section(key, title, content, { open = true, tools = '' } = {}) {
  const isOpen = sectionsOpen[key] ?? open;
  return `<details class="sec" data-sec="${key}"${isOpen ? ' open' : ''}>
    <summary><h2>${title}</h2><span class="sec-tools">${tools}</span></summary>
    <div class="sec-body">${content}</div>
  </details>`;
}

const tool = (act, key, text) => `<button class="btn small" type="button" data-act="${act}" data-key="${key}">${text}</button>`;
const copyTool = (key) => tool('copy', key, 'copiar');
const treeTools = (key) => tool('expand', key, 'expandir') + tool('collapse', key, 'contraer') + copyTool(key);
const treeHost = (key) => `<div data-tree="${key}"></div>`;

function mountTree(key, value, depth = 2) {
  const host = detail.querySelector(`[data-tree="${key}"]`);
  if (!host) return;
  copyable.set(key, value);
  if (value == null || (typeof value === 'object' && !Object.keys(value).length)) {
    host.innerHTML = '<p class="muted">sin datos</p>';
    return;
  }
  if (!treeStates.has(key)) treeStates.set(key, new Map());
  const tree = jsonTree(value, { state: treeStates.get(key), depth });
  trees.set(key, tree);
  host.replaceChildren(tree.el);
}

function summaryHtml(r) {
  const u = r.usage || {};
  const prevEffort = r.prev_id ? ` <span class="muted">(anterior #${r.prev_id}: ${esc(r.prev_effort ?? '–')})</span>` : '';
  const prefix = r.prev_id == null ? 'sin petición anterior' : r.prefix_intact ? 'intacto' : 'modificado en ' + esc(r.diverge_at);
  const gap = r.gap_s != null ? ` · ${r.gap_s} s tras la anterior` : '';
  const next = state.successors.get(r.id);
  const stopped = next ? `parado por #${next.id} a los ${next.age_s ?? next.gap_s} s · ` : '';
  const cacheNote = stopped + esc(ttlLabel(r));
  const reasoning = u.reasoning != null ? ` (razonamiento ${num(u.reasoning)})` : '';
  const tokens = r.usage
    ? `${shareBar(u, true)}
      <div class="legend">
        <span><i class="swatch kiwi"></i>leído ${num(u.read)}</span>
        <span><i class="swatch teal"></i>escrito ${num(u.write)}</span>
        <span><i class="swatch neutral"></i>sin caché ${num(u.uncached)}</span>
      </div>
      entrada ${num(u.input_total)} · salida ${num(u.output)}${reasoning}`
    : '–';
  return `<dl class="kv">
    <dt>Destino</dt><dd>${esc(r.host)}${esc(r.path)} → ${esc(r.status ?? '…')}</dd>
    <dt>Esfuerzo</dt><dd>${esc(r.effort ?? '–')}${prevEffort}</dd>
    <dt>Tamaño</dt><dd>${num(r.req_bytes)} bytes · ${r.n_tools} tools · ${r.n_msgs} mensajes · ${r.cc_marks} marcas cache_control</dd>
    <dt>Prefijo</dt><dd>${prefix}</dd>
    <dt>Tiempos</dt><dd>cabeceras ${secs(r.hdr_s)} · 1.er token ${secs(r.ttft_s)} · total ${secs(r.total_s)}${gap}</dd>
    <dt>Caché</dt><dd>${timerHtml(r)} <span class="muted">${cacheNote}</span></dd>
    <dt>Tokens</dt><dd>${tokens}</dd>
  </dl>`;
}

function diffHtml(diff, prevId) {
  const limit = Math.min(diff.before.length, diff.after.length);
  let same = 0;
  while (same < limit && diff.before[same] === diff.after[same]) same++;
  const side = (label, text, cls) => `<p class="diff-label">${label}</p>
    <pre class="code"><span class="diff-same">${esc(text.slice(0, same))}</span><mark class="${cls}">${esc(text.slice(same))}</mark></pre>`;
  return side(`Anterior #${prevId}`, diff.before, 'diff-old') + side('Esta petición', diff.after, 'diff-new');
}

function segmentsHtml(r) {
  const linked = r.prev_id != null;
  const rows = (r.segs || []).map((s) => {
    const diverged = linked && !s.same && r.diverge_at === s.name;
    const cls = !linked || s.same ? '' : diverged ? 'diverged' : 'added';
    const mark = !linked ? '' : s.same ? '=' : diverged ? '≠' : '+';
    return `<tr class="${cls}">
      <td class="mono">${mark}</td>
      <td class="mono">${esc(s.name)}</td>
      <td class="num">${num(s.bytes)}</td>
      <td class="mono">${s.hash}</td>
      <td class="mono">${s.cc ? 'sí' : ''}</td>
      <td>${esc(s.preview)}</td>
    </tr>`;
  });
  return `<table class="segments">
    <thead><tr>
      <th title="= igual que la anterior, ≠ primer cambio, + nuevo">Δ</th><th>Segmento</th><th class="num">Bytes</th>
      <th>Hash</th><th title="lleva cache_control">Marca</th><th>Vista previa</th>
    </tr></thead>
    <tbody>${rows.join('')}</tbody>
  </table>`;
}

/** The response is free text, unless the server answered with JSON (typically an error). */
function parseJson(text) {
  try {
    const value = JSON.parse(text);
    return value && typeof value === 'object' ? value : null;
  } catch {
    return null;
  }
}

async function loadBody(id) {
  const requestGeneration = generation;
  const host = detail.querySelector('[data-tree="body"]');
  if (!host) return;
  if (body.id !== id) {
    host.innerHTML = '<p class="muted">cargando…</p>';
    const res = await fetch(`/api/body/${id}`);
    if (requestGeneration !== generation || state.selected !== id) return;
    const text = res.ok ? await res.text() : '';
    if (requestGeneration !== generation || state.selected !== id) return;
    body = { id, value: parseJson(text) ?? text };
  }
  if (typeof body.value === 'string') {
    copyable.set('body', body.value);
    host.innerHTML = body.value ? `<pre class="code">${esc(body.value)}</pre>` : '<p class="muted">el cuerpo ya no está en memoria</p>';
    return;
  }
  mountTree('body', body.value, 1);
}

function renderDetail(r) {
  const scroll = detail.hidden ? 0 : detail.scrollTop;
  const outputJson = r.output ? parseJson(r.output) : null;
  const notes = (r.notes || ['en curso…']).map((n) => `<li>${esc(n)}</li>`).join('');
  const notesHtml = notes ? `<ul class="notes">${notes}</ul>` : '';
  const diff = r.diff
    ? section('diff', `Primer cambio del prefijo <small>${esc(r.diff.segment)} @ ${num(r.diff.offset)}</small>`, diffHtml(r.diff, r.prev_id))
    : '';
  const stop = r.stop_reason ? ` <small>${esc(r.stop_reason)}</small>` : '';
  const output = outputJson ? treeHost('output') : `<pre class="code">${esc(r.output || '(vacía)')}</pre>`;
  const raw = `<a class="btn small" href="/api/body/${r.id}" target="_blank" rel="noopener">abrir en crudo</a>`;

  trees.clear();
  copyable.clear();
  detail.innerHTML = `
    <header class="detail-head">
      <span class="detail-id">#${r.id}</span>${badge(r)}<span class="detail-model">${esc(r.model ?? '?')}</span>
      <button class="btn small" type="button" data-act="close">Cerrar</button>
    </header>
    ${notesHtml}
    ${section('summary', 'Resumen', summaryHtml(r))}
    ${diff}
    ${section('params', 'Parámetros enviados', treeHost('params'), { tools: treeTools('params') })}
    ${section('usage', 'Usage tal como lo devuelve el servidor', treeHost('usage'), { tools: treeTools('usage') })}
    ${section('headers', 'Cabeceras de respuesta (filtradas)', treeHost('headers'), { tools: treeTools('headers') })}
    ${section('output', `Respuesta${stop}`, output, { tools: outputJson ? treeTools('output') : copyTool('output') })}
    ${section('segments', 'Prefijo por segmentos', segmentsHtml(r))}
    ${section('body', 'Cuerpo de la petición', treeHost('body'), { open: false, tools: raw + treeTools('body') })}`;

  mountTree('params', r.effort_fields);
  mountTree('usage', r.raw_usage, 3);
  mountTree('headers', r.resp_headers);
  if (outputJson) mountTree('output', outputJson);
  else copyable.set('output', r.output || '');
  if (detail.querySelector('[data-sec="body"]').open) loadBody(r.id);

  detail.hidden = false;
  $('resizer').hidden = false;
  detail.scrollTop = scroll;
  tick();
}

export async function showDetail(id, reveal = false) {
  const requestGeneration = generation;
  state.selected = id;
  render();
  if (reveal) $('rows').querySelector('tr.selected')?.scrollIntoView({ block: 'nearest' });
  const res = await fetch(`/api/record/${id}`);
  if (!res.ok || requestGeneration !== generation || state.selected !== id) return;
  const record = await res.json();
  if (requestGeneration !== generation || state.selected !== id) return;
  renderDetail(record);
}

export function closeDetail() {
  state.selected = null;
  resetDetailCache();
  detail.hidden = true;
  detail.replaceChildren();
  $('resizer').hidden = true;
  render();
}

async function copy(button, key) {
  const value = copyable.get(key);
  await navigator.clipboard.writeText(typeof value === 'string' ? value : JSON.stringify(value, null, 2));
  button.textContent = 'copiado';
  setTimeout(() => (button.textContent = 'copiar'), 1200);
}

detail.addEventListener('click', (e) => {
  const button = e.target.closest('[data-act]');
  if (!button) return;
  e.preventDefault(); // buttons live inside <summary>: do not toggle the section
  const { act, key } = button.dataset;
  if (act === 'close') closeDetail();
  else if (act === 'copy') copy(button, key);
  else trees.get(key)?.setAll(act === 'expand');
});

// `toggle` does not bubble, so listen in the capture phase.
detail.addEventListener(
  'toggle',
  (e) => {
    const key = e.target.dataset?.sec;
    if (!key) return;
    sectionsOpen[key] = e.target.open;
    store.set('sections', sectionsOpen);
    if (key === 'body' && e.target.open) loadBody(state.selected);
  },
  true,
);

// ---------- panel width ----------

const resizer = $('resizer');
const savedWidth = store.get('detailWidth', null);
if (savedWidth) detail.style.setProperty('--detail-w', savedWidth + 'px');

resizer.addEventListener('pointerdown', (e) => {
  e.preventDefault();
  resizer.setPointerCapture(e.pointerId);
  resizer.classList.add('dragging');
  const move = (ev) => detail.style.setProperty('--detail-w', window.innerWidth - ev.clientX + 'px');
  const stop = () => {
    resizer.classList.remove('dragging');
    resizer.removeEventListener('pointermove', move);
    store.set('detailWidth', Math.round(detail.getBoundingClientRect().width));
  };
  resizer.addEventListener('pointermove', move);
  resizer.addEventListener('pointerup', stop, { once: true });
});
