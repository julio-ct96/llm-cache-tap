import { state } from './state.js';
import { esc, clock, duration } from './format.js';

export const ttlOf = (r) => r.ttl_s ?? state.ttl;

/** "TTL 5 min (puede durar hasta 1 h) · por defecto de Claude" */
export function ttlLabel(r) {
  const upTo = r.ttl_max_s ? ` (puede durar hasta ${duration(r.ttl_max_s)})` : '';
  return `TTL ${duration(ttlOf(r))}${upTo} · ${r.ttl_source ?? 'supuesto'}`;
}

/**
 * Cache lifetime of a request. It counts down from the start or the end of the
 * request, whichever its provider uses, and stops when the next request of its
 * conversation arrives. Between ttl_s and ttl_max_s the entry may or may not
 * still be there, so the timer says "dudosa" instead of "caducada".
 */
export function timerHtml(r) {
  if (r.state !== 'done' || r.ts_end == null || r.verdict === 'N/A') return '–';
  const total = ttlOf(r);
  const bar = (width) => `<span class="ttl-bar"><i style="width:${width}%"></i></span>`;
  const next = state.successors.get(r.id);
  if (!next) {
    const from = r.ttl_anchor === 'start' ? r.ts : r.ts_end;
    return `<span class="ttl" data-from="${from}" data-ttl="${total}" data-max="${r.ttl_max_s ?? 0}" title="${esc(ttlLabel(r))}">
      ${bar(0)}<span class="ttl-text"></span>
    </span>`;
  }
  const age = next.age_s ?? next.gap_s;
  const left = total - age;
  const title = esc(`parado por #${next.id} a los ${age} s · ${ttlLabel(r)}`);
  if (left > 0) return `<span class="ttl stopped" title="${title}">${bar((100 * left) / total)}<span class="ttl-text">${clock(left)}</span></span>`;
  const expiry = age < (r.ttl_max_s ?? 0) ? 'dudosa' : 'caducada';
  const cls = expiry === 'dudosa' ? 'doubtful' : 'over-ttl';
  return `<span class="ttl stopped ${cls}" title="${title}">${bar(0)}<span class="ttl-text">${expiry}</span></span>`;
}

export function tick() {
  const now = Date.now() / 1000;
  for (const timer of document.querySelectorAll('.ttl[data-from]')) {
    const { from, ttl: total, max } = timer.dataset;
    const age = now - Number(from);
    const left = Number(total) - age;
    const doubtful = left <= 0 && age < Number(max);
    timer.classList.toggle('stopped', left <= 0);
    timer.classList.toggle('doubtful', doubtful);
    timer.querySelector('i').style.width = Math.max(0, (100 * left) / Number(total)) + '%';
    timer.querySelector('.ttl-text').textContent = left > 0 ? clock(left) : doubtful ? 'dudosa' : 'caducada';
  }
}
