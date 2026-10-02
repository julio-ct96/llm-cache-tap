import { state } from './state.js';
import { $, esc, num, secs } from './format.js';
import { badge, shareBar } from './parts.js';
import { ttlOf, timerHtml, tick } from './cache-timer.js';

const BAD_VERDICTS = ['MISS', 'PARTIAL', 'ERR'];
export const SELECT_FILTERS = [
  ['f-model', 'model', 'todos los modelos'],
  ['f-conv', 'conv', 'todas las conversaciones'],
];
export const TOGGLE_FILTERS = ['f-bad', 'f-eff'];

export const pressed = (id) => $(id).getAttribute('aria-pressed') === 'true';

// ---------- list ----------

export function filterRecords(records, filters) {
  const query = filters.text.trim().toLowerCase();
  return records.filter((r) => {
    if (filters.model && r.model !== filters.model) return false;
    if (filters.conv && r.conv !== filters.conv) return false;
    if (filters.bad && !BAD_VERDICTS.includes(r.verdict)) return false;
    if (filters.effort && !r.effort_changed) return false;
    if (!query) return true;
    const haystack = [`#${r.id}`, r.model, r.conv, r.verdict, r.effort, ...(r.notes || [])].join(' ').toLowerCase();
    return haystack.includes(query);
  });
}

export function summarizeRecords(records) {
  const summary = { count: records.length, hit: 0, miss: 0, server: 0, effortHit: 0, effort: 0, read: 0, total: 0 };
  for (const r of records) {
    if (r.state !== 'done') continue;
    if (r.verdict === 'HIT') summary.hit++;
    if (['MISS', 'PARTIAL'].includes(r.verdict)) summary.miss++;
    if (r.server_side) summary.server++;
    if (r.effort_changed && r.prev_id) {
      summary.effort++;
      if (r.verdict === 'HIT') summary.effortHit++;
    }
    summary.read += r.usage?.read || 0;
    summary.total += r.usage?.input_total || 0;
  }
  return summary;
}

function readFilters() {
  return {
    model: $('f-model').value,
    conv: $('f-conv').value,
    bad: pressed('f-bad'),
    effort: pressed('f-eff'),
    text: $('f-text').value,
  };
}

function rowHtml(r) {
  const u = r.usage || {};
  const effort = r.effort_changed
    ? `<span class="chip changed">${esc(r.prev_effort ?? '∅')} → ${esc(r.effort ?? '∅')}</span>`
    : `<span class="chip">${esc(r.effort ?? '–')}</span>`;
  const prevRec = state.recs.get(r.prev_id);
  const late = prevRec && (r.age_s ?? r.gap_s) > ttlOf(prevRec);
  const gap = r.gap_s == null ? '–' : `<span class="${late ? 'over-ttl' : ''}">${r.gap_s.toFixed(0)} s</span>`;
  const prev = r.prev_id ? ` <span class="muted">← #${r.prev_id}</span>` : '';
  const classes = [r.id === state.selected ? 'selected' : '', r.server_side ? 'server' : ''].join(' ');
  return `<tr data-id="${r.id}" class="${classes}">
    <td class="num">${r.id}</td>
    <td class="mono">${esc(r.time)}</td>
    <td>${badge(r)}</td>
    <td>${timerHtml(r)}</td>
    <td class="mono">${esc(r.model ?? '?')}</td>
    <td>${effort}</td>
    <td class="num">${num(u.input_total)}</td>
    <td class="num">${num(u.read)}</td>
    <td class="num">${num(u.write)}</td>
    <td>${shareBar(u)}</td>
    <td class="num">${secs(r.ttft_s)}</td>
    <td class="num">${secs(r.total_s)}</td>
    <td class="num">${gap}</td>
    <td class="mono">${esc(r.conv)}${prev}</td>
    <td class="diagnosis">${(r.notes || []).map(esc).join(' · ')}</td>
  </tr>`;
}

/** Render in O(R log R + T): one ID sort plus text length inspected by filters. */
export function render() {
  const filters = readFilters();
  state.successors = new Map();
  const records = [...state.recs.values()].sort((a, b) => b.id - a.id);
  for (const r of records) {
    if (r.prev_id != null) state.successors.set(r.prev_id, r);
  }
  state.visible = filterRecords(records, filters);
  $('rows').innerHTML = state.visible.map(rowHtml).join('');
  tick();
  $('empty').hidden = state.recs.size > 0;
  $('no-match').hidden = state.recs.size === 0 || state.visible.length > 0;

  const summary = summarizeRecords(state.visible);
  $('s-n').textContent = summary.count;
  $('s-hit').textContent = summary.hit;
  $('s-miss').textContent = summary.miss;
  $('s-srv').textContent = summary.server;
  $('s-eff').textContent = `${summary.effortHit} / ${summary.effort}`;
  $('s-rate').textContent = summary.total ? ((100 * summary.read) / summary.total).toFixed(1) + ' %' : '–';
}

export function syncFilters() {
  for (const [id, key, all] of SELECT_FILTERS) {
    const select = $(id);
    const current = select.value;
    const values = [...new Set([...state.recs.values()].map((r) => r[key]).filter(Boolean))].sort();
    select.innerHTML = `<option value="">${all}</option>` + values.map((v) => `<option>${esc(v)}</option>`).join('');
    select.value = values.includes(current) ? current : '';
  }
}

export function resetFilters() {
  $('f-text').value = '';
  for (const [id] of SELECT_FILTERS) $(id).value = '';
  for (const id of TOGGLE_FILTERS) $(id).setAttribute('aria-pressed', 'false');
  render();
}
