export const state = {
  recs: new Map(),
  visible: [], // records that pass the filters, in display order
  successors: new Map(), // record id -> the next request of its conversation
  selected: null,
  ttl: 300,
};
