import { state, applyEvent } from './state.js';
import { $ } from './format.js';
import { render, syncFilters } from './list.js';
import { showDetail, closeDetail, resetDetailCache } from './detail.js';

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
    if (ev.type === 'snapshot' || ev.type === 'clear') resetDetailCache();
    const selectionInvalid = applyEvent(ev);
    if (selectionInvalid) {
      closeDetail();
    } else if (ev.type === 'snapshot' && state.selected != null) {
      showDetail(state.selected);
    } else if (ev.type === 'record') {
      // a new request also stops the timer of the one it follows
      if (ev.rec.id === state.selected || ev.rec.prev_id === state.selected) showDetail(state.selected);
    }
    syncFilters();
    render();
  };
}
