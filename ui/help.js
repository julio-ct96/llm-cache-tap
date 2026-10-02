import { $, esc } from './format.js';

const TOKENS = new Intl.NumberFormat('es-ES', { useGrouping: 'always' });

// Escape first, then turn each `backticked` span into a <code> element.
const rich = (text) => esc(text).replace(/`([^`]*)`/g, '<code>$1</code>');

const row = (cells) => `<tr>${cells.map(([html, cls]) => `<td${cls ? ` class="${cls}"` : ''}>${html}</td>`).join('')}</tr>`;

export async function loadHelp() {
  let ref;
  try {
    const res = await fetch('/api/reference');
    if (!res.ok) return;
    ref = await res.json();
  } catch {
    return;
  }
  $('help-ttl').innerHTML = (ref.ttl ?? []).map((r) => row([[rich(r.models)], [rich(r.ttl)], [rich(r.anchor)]])).join('');
  $('help-min').innerHTML = (ref.min_cacheable ?? [])
    .map((r) => row([[rich(r.models)], [esc(TOKENS.format(r.tokens)), 'num']]))
    .join('');
  $('help-reviewed').textContent = ref.reviewed ?? '';
}
