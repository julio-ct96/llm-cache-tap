function isPositiveId(value) {
  return Number.isInteger(value) && value > 0;
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value) && isPositiveId(value.id);
}

function isIdArray(value) {
  return Array.isArray(value) && value.every(isPositiveId);
}

function isConvTotals(value) {
  return (
    value === undefined ||
    (value !== null &&
      typeof value === 'object' &&
      !Array.isArray(value) &&
      Object.values(value).every((total) => total !== null && typeof total === 'object' && Number.isFinite(total.usd)))
  );
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
        (event.max_records !== undefined && (!Number.isInteger(event.max_records) || event.max_records <= 0)) ||
        !isConvTotals(event.convs)
      ) {
        throw new TypeError('Invalid SSE snapshot');
      }
      break;
    case 'record':
      if (!isRecord(event.rec) || (event.evicted_ids !== undefined && !isIdArray(event.evicted_ids)) || !isConvTotals(event.convs)) {
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
