import assert from 'node:assert/strict';
import test from 'node:test';

import { esc } from '../../../ui/format.js';
import { state } from '../../../ui/state.js';

test('escapes HTML-sensitive characters', () => {
  assert.equal(esc('&<>"'), '&amp;&lt;&gt;&quot;');
});

test('starts with empty collections and no selected record', () => {
  assert.equal(state.recs.size, 0);
  assert.deepEqual(state.visible, []);
  assert.equal(state.successors.size, 0);
  assert.equal(state.selected, null);
  assert.equal(state.ttl, 300);
});
