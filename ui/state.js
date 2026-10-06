export const state = {
  recs: new Map(),
  visible: [], // records that pass the filters, in display order
  successors: new Map(), // record id -> the next request of its conversation
  convs: new Map(), // conversation -> its running cost, which outlives evicted requests
  selected: null,
  ttl: 300,
  maxRecords: 300,
};

function retainHighestIds() {
  const ids = [...state.recs.keys()].sort((a, b) => b - a);
  for (const id of ids.slice(state.maxRecords)) state.recs.delete(id);
}

export function applyEvent(ev) {
  const selected = state.selected;

  if (ev.type === 'snapshot') {
    state.recs.clear();
    state.convs = new Map(Object.entries(ev.convs ?? {}));
    state.ttl = ev.ttl;
    state.maxRecords = ev.max_records ?? 300;
    ev.recs.forEach((record) => state.recs.set(record.id, record));
    retainHighestIds();
  } else if (ev.type === 'clear') {
    state.recs.clear();
    state.convs.clear();
  } else if (ev.type === 'record') {
    for (const id of ev.evicted_ids || []) state.recs.delete(id);
    state.recs.set(ev.rec.id, ev.rec);
    for (const [conv, total] of Object.entries(ev.convs ?? {})) state.convs.set(conv, total);
    retainHighestIds();
  } else if (ev.type === 'evict') {
    for (const id of ev.ids) state.recs.delete(id);
  }

  return selected != null && !state.recs.has(selected);
}
