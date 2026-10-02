import { state } from './state.js';
import { $ } from './format.js';
import { render, syncFilters } from './list.js';
import { showDetail, closeDetail } from './detail.js';

function setConnected(on) {
  $('conn').className = 'conn ' + (on ? 'on' : 'off');
  $('conn-text').textContent = on ? 'en vivo' : 'sin conexión, reintentando';
}

export function connect() {
  const source = new EventSource('/events');
  source.onopen = () => setConnected(true);
  source.onerror = () => setConnected(false);
  source.onmessage = (message) => {
    const ev = JSON.parse(message.data);
    if (ev.type === 'snapshot') {
      state.recs.clear();
      state.ttl = ev.ttl;
      ev.recs.forEach((r) => state.recs.set(r.id, r));
    } else if (ev.type === 'clear') {
      state.recs.clear();
      closeDetail();
    } else if (ev.type === 'record') {
      state.recs.set(ev.rec.id, ev.rec);
      // a new request also stops the timer of the one it follows
      if (ev.rec.id === state.selected || ev.rec.prev_id === state.selected) showDetail(state.selected);
    }
    syncFilters();
    render();
  };
}
