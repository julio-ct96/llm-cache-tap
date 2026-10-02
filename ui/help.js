import { $, esc } from './format.js';
import { clearStatus, showStatus } from './status.js';

const TOKENS = new Intl.NumberFormat('es-ES', { useGrouping: 'always' });

// Escape first, then turn each `backticked` span into a <code> element.
const rich = (text) => esc(text).replace(/`([^`]*)`/g, '<code>$1</code>');

const row = (cells) => `<tr>${cells.map(([html, cls]) => `<td${cls ? ` class="${cls}"` : ''}>${html}</td>`).join('')}</tr>`;

export async function loadHelp() {
  let ref;
  try {
    const res = await fetch('/api/reference');
    if (!res.ok) throw new Error('Reference request failed');
    ref = await res.json();
    if (
      ref === null ||
      typeof ref !== 'object' ||
      !Array.isArray(ref.ttl) ||
      !ref.ttl.every((row) => row && typeof row.models === 'string' && typeof row.ttl === 'string' && typeof row.anchor === 'string') ||
      !Array.isArray(ref.min_cacheable) ||
      !ref.min_cacheable.every((row) => row && typeof row.models === 'string' && Number.isFinite(row.tokens)) ||
      typeof ref.reviewed !== 'string'
    ) {
      throw new Error('Invalid reference response');
    }
  } catch {
    showStatus('No se pudo cargar la referencia de ayuda.');
    return;
  }
  clearStatus('No se pudo cargar la referencia de ayuda.');
  $('help-ttl').innerHTML = (ref.ttl ?? []).map((r) => row([[rich(r.models)], [rich(r.ttl)], [rich(r.anchor)]])).join('');
  $('help-min').innerHTML = (ref.min_cacheable ?? [])
    .map((r) => row([[rich(r.models)], [esc(TOKENS.format(r.tokens)), 'num']]))
    .join('');
  $('help-reviewed').textContent = ref.reviewed ?? '';
}
