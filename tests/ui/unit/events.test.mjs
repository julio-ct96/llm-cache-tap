import assert from 'node:assert/strict';
import test from 'node:test';

import { parseEvent } from '../../../ui/events.js';

test('accepts every SSE variant and records that are only partially populated', () => {
  assert.deepEqual(parseEvent('{"type":"snapshot","recs":[{"id":1,"state":"pending"}],"ttl":300,"max_records":2}'), {
    type: 'snapshot', recs: [{ id: 1, state: 'pending' }], ttl: 300, max_records: 2,
  });
  assert.deepEqual(parseEvent('{"type":"snapshot","recs":[],"ttl":1}').recs, []);
  assert.deepEqual(parseEvent('{"type":"record","rec":{"id":3},"evicted_ids":[1,2]}').evicted_ids, [1, 2]);
  assert.deepEqual(parseEvent('{"type":"evict","ids":[3]}').ids, [3]);
  assert.equal(parseEvent('{"type":"clear"}').type, 'clear');
});

test('rejects malformed JSON, unknown variants, invalid IDs and invalid snapshot limits', () => {
  for (const data of [
    '{',
    'null',
    '[]',
    '{"type":"other"}',
    '{"type":"record","rec":{"id":0}}',
    '{"type":"record","rec":{"id":1},"evicted_ids":[1.5]}',
    '{"type":"evict","ids":"1"}',
    '{"type":"snapshot","recs":[{}],"ttl":300}',
    '{"type":"snapshot","recs":[],"ttl":0}',
    '{"type":"snapshot","recs":[],"ttl":300,"max_records":1.5}',
  ]) {
    assert.throws(() => parseEvent(data));
  }
});
