import { esc } from './format.js';

export function badge(r) {
  if (r.state !== 'done' && r.state !== 'error') {
    return `<span class="badge v-pending">${r.state === 'streaming' ? 'stream' : 'espera'}</span>`;
  }
  const cls = 'v-' + String(r.verdict ?? 'na').toLowerCase().replace(/[^a-z]/g, '');
  return `<span class="badge ${cls}">${esc(r.verdict)}</span>`;
}

export function shareBar(u, wide = false) {
  const total = u.input_total;
  if (!total) return '';
  const pct = (v) => (100 * (v || 0)) / total;
  const title = `leído ${pct(u.read).toFixed(1)} % · escrito ${pct(u.write).toFixed(1)} % · sin caché ${pct(u.uncached).toFixed(1)} %`;
  return `<div class="bar${wide ? ' wide' : ''}" role="img" aria-label="${title}" title="${title}">
    <i class="read" style="width:${pct(u.read)}%"></i>
    <i class="write" style="width:${pct(u.write)}%"></i>
    <i class="uncached" style="width:${pct(u.uncached)}%"></i>
  </div>`;
}
