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

function passes(r) {
  if ($('f-model').value && r.model !== $('f-model').value) return false;
  if ($('f-conv').value && r.conv !== $('f-conv').value) return false;
  if (pressed('f-bad') && !BAD_VERDICTS.includes(r.verdict)) return false;
  if (pressed('f-eff') && !r.effort_changed) return false;
  const query = $('f-text').value.trim().toLowerCase();
  if (!query) return true;
  const haystack = [`#${r.id}`, r.model, r.conv, r.verdict, r.effort, ...(r.notes || [])].join(' ').toLowerCase();
  return haystack.includes(query);
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

export function render() {
  state.successors = new Map();
  for (const r of [...state.recs.values()].sort((a, b) => a.id - b.id)) {
    if (r.prev_id != null && !state.successors.has(r.prev_id)) state.successors.set(r.prev_id, r);
  }
  state.visible = [...state.recs.values()].filter(passes).sort((a, b) => b.id - a.id);
  $('rows').innerHTML = state.visible.map(rowHtml).join('');
  tick();
  $('empty').hidden = state.recs.size > 0;
  $('no-match').hidden = state.recs.size === 0 || state.visible.length > 0;

  const done = state.visible.filter((r) => r.state === 'done');
  const effort = done.filter((r) => r.effort_changed && r.prev_id);
  const read = done.reduce((sum, r) => sum + (r.usage?.read || 0), 0);
  const total = done.reduce((sum, r) => sum + (r.usage?.input_total || 0), 0);
  $('s-n').textContent = state.visible.length;
  $('s-hit').textContent = done.filter((r) => r.verdict === 'HIT').length;
  $('s-miss').textContent = done.filter((r) => ['MISS', 'PARTIAL'].includes(r.verdict)).length;
  $('s-srv').textContent = done.filter((r) => r.server_side).length;
  $('s-eff').textContent = `${effort.filter((r) => r.verdict === 'HIT').length} / ${effort.length}`;
  $('s-rate').textContent = total ? ((100 * read) / total).toFixed(1) + ' %' : '–';
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
