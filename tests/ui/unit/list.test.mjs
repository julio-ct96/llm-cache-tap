import assert from 'node:assert/strict';
import test from 'node:test';

import { filterRecords, summarizeRecords } from '../../../ui/list.js';

const records = [
  { id: 1, model: 'claude', conv: 'a', verdict: 'HIT', state: 'done', effort_changed: true, prev_id: 0, usage: { read: 8, input_total: 10 }, notes: ['stable prefix'] },
  { id: 2, model: 'gpt', conv: 'b', verdict: 'PARTIAL', state: 'done', effort_changed: true, prev_id: 1, server_side: true, usage: { read: 2, input_total: 10 }, notes: ['changed prompt'] },
  { id: 3, model: 'gpt', conv: 'a', verdict: 'MISS', state: 'pending', effort_changed: true, prev_id: 2, notes: ['waiting'] },
];

test('filterRecords applies explicit model, conversation, toggle, and text criteria', () => {
  assert.deepEqual(filterRecords(records, { model: '', conv: '', bad: false, effort: false, text: '' }), records);
  assert.deepEqual(filterRecords(records, { model: 'gpt', conv: 'b', bad: true, effort: true, text: 'CHANGED' }), [records[1]]);
  assert.deepEqual(filterRecords(records, { model: '', conv: '', bad: false, effort: false, text: '#3' }), [records[2]]);
  assert.deepEqual(filterRecords(records, { model: 'claude', conv: 'b', bad: false, effort: false, text: '' }), []);
});

test('summarizeRecords preserves visible counts and usage percentages input', () => {
  assert.deepEqual(summarizeRecords(records), {
    count: 3, hit: 1, miss: 1, server: 1, effortHit: 0, effort: 1, read: 10, total: 20,
  });
  assert.deepEqual(summarizeRecords([]), {
    count: 0, hit: 0, miss: 0, server: 0, effortHit: 0, effort: 0, read: 0, total: 0,
  });
});

test('filterRecords keeps only requests at or above the minimum cost', () => {
  const filters = { model: '', conv: '', bad: false, effort: false, text: '' };
  const priced = [{ id: 3, cost: { usd: 2 } }, { id: 2, cost: { usd: 0.5 } }, { id: 1, cost_missing: 'sin precio' }, { id: 0 }];
  assert.deepEqual(filterRecords(priced, { ...filters, minCost: 2 }).map((r) => r.id), [3]);
  assert.deepEqual(filterRecords(priced, { ...filters, minCost: 0.5 }).map((r) => r.id), [3, 2]);
  assert.equal(filterRecords(priced, { ...filters, minCost: 0 }).length, 4);
});
