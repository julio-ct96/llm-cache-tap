import assert from 'node:assert/strict';
import test from 'node:test';

import { costByModel, lostByCause, sortRecords, summarizeCosts } from '../../../ui/costs.js';

const cost = (usd, saved, lost, tariff = 'Copilot') => ({
  tariff, usd, no_cache_usd: usd + saved, saved_usd: saved, ...(lost ? { lost_usd: lost } : {}),
});
const records = [
  { id: 4, model: 'gpt-6-luna', cost: cost(0.5, 1.5) },
  { id: 3, model: 'gpt-6-luna', cost: cost(2, -0.25, 1.5), miss_causes: ['ttl', 'prefix'] },
  { id: 2, model: 'claude-opus-5.5', cost: cost(4, 0, 3, 'Anthropic'), miss_causes: ['prefix'] },
  { id: 1, model: 'gpt-5.2', cost_missing: 'sin precio para gpt-5.2 en la tarifa de Copilot' },
  { id: 0, model: 'gpt-6-luna' },
];

test('summarizeCosts adds what has a cost and counts apart what has no price', () => {
  assert.deepEqual(summarizeCosts(records), { priced: 3, unpriced: 1, usd: 6.5, noCache: 7.75, saved: 1.25, lost: 4.5 });
  assert.deepEqual(summarizeCosts([]), { priced: 0, unpriced: 0, usd: 0, noCache: 0, saved: 0, lost: 0 });
});

test('costByModel separates price tables and keeps unpriced models visible', () => {
  assert.deepEqual(
    costByModel(records).map((m) => [m.key, m.priced, m.unpriced, m.usd]),
    [
      ['claude-opus-5.5 · Anthropic', 1, 0, 4],
      ['gpt-6-luna · Copilot', 2, 0, 2.5],
      ['gpt-5.2 · sin precio', 0, 1, 0],
    ],
  );
});

test('lostByCause charges each miss to its first cause, the costliest first', () => {
  assert.deepEqual(
    lostByCause(records).map((c) => [c.key, c.priced, c.lost]),
    [
      ['prefix', 1, 3],
      ['ttl', 1, 1.5],
    ],
  );
});

test('sortRecords orders by amount and leaves requests without it at the end', () => {
  const ids = (sort) => sortRecords(records, sort).map((r) => r.id);
  assert.deepEqual(ids(''), [4, 3, 2, 1, 0]);
  assert.deepEqual(ids('cost'), [2, 3, 4, 1, 0]);
  assert.deepEqual(ids('lost'), [2, 3, 4, 1, 0]);
  assert.deepEqual(ids('saved'), [4, 2, 3, 1, 0]);
  assert.equal(sortRecords(records, ''), records);
});
