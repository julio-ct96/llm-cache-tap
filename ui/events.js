function isPositiveId(value) {
  return Number.isInteger(value) && value > 0;
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value) && isPositiveId(value.id);
}

function isIdArray(value) {
  return Array.isArray(value) && value.every(isPositiveId);
}

export function parseEvent(data) {
  const event = JSON.parse(data);
  if (event === null || typeof event !== 'object' || Array.isArray(event)) throw new TypeError('Invalid SSE event');

  switch (event.type) {
    case 'snapshot':
      if (
        !Array.isArray(event.recs) ||
        !event.recs.every(isRecord) ||
        typeof event.ttl !== 'number' ||
        !Number.isFinite(event.ttl) ||
        event.ttl <= 0 ||
        (event.max_records !== undefined && (!Number.isInteger(event.max_records) || event.max_records <= 0))
      ) {
        throw new TypeError('Invalid SSE snapshot');
      }
      break;
    case 'record':
      if (!isRecord(event.rec) || (event.evicted_ids !== undefined && !isIdArray(event.evicted_ids))) {
        throw new TypeError('Invalid SSE record');
      }
      break;
    case 'evict':
      if (!isIdArray(event.ids)) throw new TypeError('Invalid SSE eviction');
      break;
    case 'clear':
      break;
    default:
      throw new TypeError('Unknown SSE event');
  }

  return event;
}
