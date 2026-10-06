import { state } from './state.js';
import { esc, num, pct, rate, usd } from './format.js';

function convTotalHtml(r) {
  const t = state.convs.get(r.conv);
  if (!t) return '';
  const unpriced = t.unpriced ? ` (${num(t.unpriced)} sin precio)` : '';
  return `<dt>Conversación ${esc(r.conv)}</dt><dd>${num(t.priced + t.unpriced)} peticiones${unpriced} · coste ${usd(t.usd)} · ahorro ${usd(t.saved_usd)} (${pct(t.saved_usd, t.no_cache_usd)}) · perdido ${usd(t.lost_usd)}</dd>`;
}

/** The "Coste" section of the detail panel: tokens by price, what the cache saved and the conversation total. */
export function costHtml(r) {
  const c = r.cost;
  if (!c) {
    const why = r.cost_missing ?? (r.state === 'done' ? 'la respuesta no trae usage' : 'en curso…');
    return `<p class="muted">Sin coste: ${esc(why)}.</p><dl class="kv">${convTotalHtml(r)}</dl>`;
  }
  const u = r.usage || {};
  const hour = c.write_1h ? ` <span class="muted">(${num(c.write_1h)} a 1 h: ${rate(c.rates.write_1h)})</span>` : '';
  const reasoning = u.reasoning != null ? ` <span class="muted">(razonamiento ${num(u.reasoning)})</span>` : '';
  const line = (label, tokens, price, amount) =>
    `<tr><td>${label}</td><td class="num">${num(tokens)}</td><td class="num">${price}</td><td class="num">${usd(amount)}</td></tr>`;
  const long = c.long_over ? ` · contexto largo: más de ${num(c.long_over)} tokens de entrada` : '';
  const note = c.note ? ` · ${esc(c.note)}` : '';
  const lost = c.lost_usd ? `<dt>Perdido</dt><dd><span class="lost">${usd(c.lost_usd)}</span> de más por no leer de caché el prefijo de #${r.prev_id}</dd>` : '';
  return `<table class="costs">
      <thead><tr><th>Concepto</th><th class="num">Tokens</th><th class="num">$ / 1M</th><th class="num">Coste</th></tr></thead>
      <tbody>
        ${line('Entrada sin caché', u.uncached, rate(c.rates.input), c.parts.uncached)}
        ${line('Leído de caché', u.read, rate(c.rates.read), c.parts.read)}
        ${line(`Escrito en caché${hour}`, u.write, rate(c.rates.write), c.parts.write)}
        ${line(`Salida${reasoning}`, u.output, rate(c.rates.output), c.parts.output)}
      </tbody>
      <tfoot><tr><td>Total</td><td></td><td></td><td class="num">${usd(c.usd)}</td></tr></tfoot>
    </table>
    <dl class="kv">
      <dt>Tarifa</dt><dd>${esc(c.tariff)}${long}${note}</dd>
      <dt>Sin caché</dt><dd>habría costado ${usd(c.no_cache_usd)}</dd>
      <dt>Ahorro</dt><dd><span class="${c.saved_usd > 0 ? 'saved' : c.saved_usd < 0 ? 'lost' : ''}">${usd(c.saved_usd)}</span> (${pct(c.saved_usd, c.no_cache_usd)})</dd>
      ${lost}
      ${convTotalHtml(r)}
    </dl>`;
}
