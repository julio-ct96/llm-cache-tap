import assert from 'node:assert/strict';
import test from 'node:test';

import { pct, rate, usd } from '../../../ui/format.js';

test('usd shows more decimals the smaller the amount', () => {
  assert.equal(usd(null), '–');
  assert.equal(usd(0), '0,00 $');
  assert.equal(usd(12.345), '12,35 $');
  assert.equal(usd(0.0126), '0,013 $');
  assert.equal(usd(0.00268), '0,0027 $');
  assert.equal(usd(-0.003), '-0,0030 $');
  assert.equal(usd(0.00001), '< 0,0001 $');
});

test('pct and rate use the Spanish decimal comma and a dash for what is unknown', () => {
  assert.equal(pct(1, 4), '25,0 %');
  assert.equal(pct(1, 0), '–');
  assert.equal(rate(0.125), '0,125');
  assert.equal(rate(10), '10');
  assert.equal(rate(null), '–');
});
