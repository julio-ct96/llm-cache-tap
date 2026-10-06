import { state } from './state.js';
import { $, esc, num, pct, usd } from './format.js';

// Why a request missed the cache, as the backend names it in miss_causes.
export const CAUSES = {
  model: 'cambio de modelo',
  effort: 'cambio de esfuerzo',
  params: 'cambio de thinking / tool_choice',
  prefix: 'prefijo modificado por el cliente',
  ttl: 'TTL vencido',
  prev_failed: 'la petición anterior no terminó bien',
  server: 'sin causa en el cliente',
};

export const SORTS = {
  cost: (r) => r.cost?.usd,
  lost: (r) => r.cost?.lost_usd,
  saved: (r) => r.cost?.saved_usd,
};

/** Highest first by the chosen amount; requests without it keep their order at the end. */
export function sortRecords(records, sort) {
  const amount = SORTS[sort];
  if (!amount) return records;
  return [...records].sort((a, b) => (amount(b) ?? -Infinity) - (amount(a) ?? -Infinity));
}

export function summarizeCosts(records) {
  const summary = { priced: 0, unpriced: 0, usd: 0, noCache: 0, saved: 0, lost: 0 };
  for (const r of records) {
    if (r.cost_missing) summary.unpriced++;
    if (!r.cost) continue;
    summary.priced++;
    summary.usd += r.cost.usd;
    summary.noCache += r.cost.no_cache_usd;
    summary.saved += r.cost.saved_usd;
    summary.lost += r.cost.lost_usd ?? 0;
  }
  return summary;
}

function groupCosts(records, keyOf) {
  const groups = new Map();
  for (const r of records) {
    const key = keyOf(r);
    if (key == null) continue;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }
  return [...groups].map(([key, group]) => ({ key, ...summarizeCosts(group) }));
}

/** Cost of each model under each price table, the most expensive first. */
export function costByModel(records) {
  return groupCosts(records, (r) => (r.cost ? `${r.model} · ${r.cost.tariff}` : r.cost_missing ? `${r.model ?? '?'} · sin precio` : null)).sort(
    (a, b) => b.usd - a.usd,
  );
}

/** What the misses wasted, charged to the first cause of each one. */
export function lostByCause(records) {
  return groupCosts(
    records.filter((r) => r.cost?.lost_usd),
    (r) => r.miss_causes?.[0] ?? 'server',
  ).sort((a, b) => b.lost - a.lost);
}

const cell = (html, cls = 'num') => `<td class="${cls}">${html}</td>`;
const empty = (columns, text) => `<tr><td colspan="${columns}" class="muted">${text}</td></tr>`;

function amounts(total) {
  return cell(usd(total.usd)) + cell(usd(total.saved)) + cell(pct(total.saved, total.noCache)) + cell(usd(total.lost));
}

export function renderCosts() {
  const visible = state.visible;
  const total = summarizeCosts(visible);
  const unpriced = total.unpriced ? ` · ${num(total.unpriced)} sin precio` : '';
  $('costs-total').textContent =
    `${num(total.priced)} peticiones con coste${unpriced}: ${usd(total.usd)} · sin caché habrían sido ${usd(total.noCache)} · ` +
    `ahorro ${usd(total.saved)} (${pct(total.saved, total.noCache)}) · perdido por fallos de caché ${usd(total.lost)}`;

  const models = costByModel(visible);
  $('costs-models').innerHTML = models.length
    ? models.map((m) => `<tr>${cell(esc(m.key), 'mono')}${cell(num(m.priced + m.unpriced))}${amounts(m)}</tr>`).join('')
    : empty(6, 'ninguna petición visible tiene coste');

  const causes = lostByCause(visible);
  $('costs-causes').innerHTML = causes.length
    ? causes.map((c) => `<tr>${cell(esc(CAUSES[c.key] ?? c.key), '')}${cell(num(c.priced))}${cell(usd(c.lost))}${cell(pct(c.lost, total.lost))}</tr>`).join('')
    : empty(4, 'ningún fallo de caché con coste entre lo visible');

  const shown = new Set(visible.map((r) => r.conv));
  const convs = [...state.convs].filter(([conv]) => shown.has(conv)).sort((a, b) => b[1].usd - a[1].usd);
  $('costs-convs').innerHTML = convs.length
    ? convs
        .map(([conv, t]) => {
          const requests = num(t.priced + t.unpriced) + (t.unpriced ? ` <span class="muted">(${num(t.unpriced)} sin precio)</span>` : '');
          const row = { usd: t.usd, saved: t.saved_usd, noCache: t.no_cache_usd, lost: t.lost_usd };
          return `<tr>${cell(esc(conv), 'mono')}${cell(requests)}${amounts(row)}</tr>`;
        })
        .join('')
    : empty(6, 'ninguna conversación visible tiene coste');
}
