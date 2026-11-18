import assert from 'node:assert/strict';
import test from 'node:test';

import { cacheReadIndicator } from '../../../ui/parts.js';

test('shows observed cache reads independently of verdict and model', () => {
  const cases = [
    [13789, 13847, '99,6 %', true, { verdict: 'N/A', context_partial: true, transport: 'websocket' }],
    [9000, 10000, '90,0 %', true],
    [8999, 10000, '&lt;90 %', false],
    [1400, 1600, '87,5 %', false, { verdict: 'HIT' }],
    [0, 10000, '0,0 %', false],
    [10000, 10000, '100,0 %', true],
  ];
  for (const [read, input_total, label, high, fields] of cases) {
    const html = cacheReadIndicator({ state: 'done', usage: { read, input_total }, ...fields });
    assert.equal(html, `<span class="cache-read${high ? ' cache-read-high' : ''}">Leído de caché: ${label}</span>`);
  }
});

test('shows no percentage for absent or invalid counters', () => {
  const invalid = [[0, 0], [-1, 100], [101, 100], [0.5, 100], [1, 100.5], ['90', 100], [90, '100'], [NaN, 100], [1, NaN], [1, Number.MAX_SAFE_INTEGER + 1], [1, -1]];
  const usages = [undefined, null, {}, ...invalid.map(([read, input_total]) => ({ read, input_total }))];
  for (const usage of usages) {
    assert.equal(cacheReadIndicator({ state: 'done', usage }), '<span class="cache-read">Lectura de caché: sin datos</span>');
  }
});

test('omits the indicator until the request is done', () => {
  for (const state of ['pending', 'streaming', 'error']) {
    assert.equal(cacheReadIndicator({ state, usage: { read: 90, input_total: 100 } }), '');
  }
});
