import assert from 'node:assert/strict';
import test, { beforeEach } from 'node:test';

import { applyEvent, state } from '../../../ui/state.js';

beforeEach(() => {
  state.recs.clear();
  state.visible = [];
  state.successors.clear();
  state.selected = null;
  state.ttl = 300;
  state.maxRecords = 300;
});

test('snapshot replaces records and applies the retention limit', () => {
  applyEvent({ type: 'snapshot', ttl: 60, max_records: 2, recs: [{ id: 1 }, { id: 2 }, { id: 3 }] });

  assert.deepEqual([...state.recs.keys()].sort(), [2, 3]);
  assert.equal(state.ttl, 60);
  assert.equal(state.maxRecords, 2);
});

test('repeated updates of the same record do not grow the map', () => {
  state.maxRecords = 2;
  applyEvent({ type: 'record', rec: { id: 1, value: 'first' } });
  applyEvent({ type: 'record', rec: { id: 1, value: 'updated' } });

  assert.equal(state.recs.size, 1);
  assert.equal(state.recs.get(1).value, 'updated');
});

test('record removes evicted IDs before inserting and retaining the newest IDs', () => {
  state.maxRecords = 2;
  applyEvent({ type: 'snapshot', ttl: 300, max_records: 2, recs: [{ id: 2 }, { id: 3 }] });
  applyEvent({ type: 'record', rec: { id: 4 }, evicted_ids: [2] });

  assert.deepEqual([...state.recs.keys()].sort(), [3, 4]);
});

test('snapshot and clear remove previous records and report stale selection', () => {
  state.selected = 2;
  state.recs.set(2, { id: 2 });
  assert.equal(applyEvent({ type: 'snapshot', ttl: 300, max_records: 2, recs: [{ id: 3 }] }), true);
  assert.deepEqual([...state.recs.keys()], [3]);

  state.selected = 3;
  assert.equal(applyEvent({ type: 'clear' }), true);
  assert.equal(state.recs.size, 0);
});

test('evict reports selection invalidation while events without evictions retain behavior', () => {
  state.selected = 1;
  state.recs.set(1, { id: 1 });
  assert.equal(applyEvent({ type: 'record', rec: { id: 2 } }), false);
  assert.deepEqual([...state.recs.keys()].sort(), [1, 2]);
  assert.equal(applyEvent({ type: 'evict', ids: [1] }), true);
  assert.deepEqual([...state.recs.keys()], [2]);
});
