import { state, applyEvent } from './state.js';
import { $ } from './format.js';
import { render, syncFilters } from './list.js';
import { showDetail, closeDetail, resetDetailCache } from './detail.js';
import { parseEvent } from './events.js';
import { clearStatus, showStatus } from './status.js';

function setConnected(on) {
  $('conn').className = 'conn ' + (on ? 'on' : 'off');
  $('conn-text').textContent = on ? 'en vivo' : 'sin conexión, reintentando';
}

export function connect() {
  let source;
  let retryTimer;
  let closed = false;
  let paintFrame;
  let refreshId;
  const invalidSelections = new Set();

  const schedulePaint = () => {
    if (paintFrame !== undefined) return;
    paintFrame = requestAnimationFrame(() => {
      paintFrame = undefined;
      const invalid = [...invalidSelections];
      invalidSelections.clear();
      const refresh = refreshId;
      refreshId = undefined;
      syncFilters();
      if (invalid.includes(state.selected)) closeDetail();
      else if (refresh != null && state.selected === refresh) showDetail(refresh);
      else render();
    });
  };

  const open = () => {
    source = new EventSource('/events');
    const current = source;
    current.onopen = () => {
      if (current === source) setConnected(true);
    };
    current.onerror = () => {
      if (current === source) setConnected(false);
    };
    current.onmessage = (message) => {
      if (current !== source) return;
      let ev;
      try {
        ev = parseEvent(message.data);
      } catch {
        setConnected(false);
        showStatus('Se recibió un evento inválido; reconectando.');
        current.close();
        if (retryTimer === undefined && !closed) {
          retryTimer = setTimeout(() => {
            retryTimer = undefined;
            if (!closed) open();
          }, 1000);
        }
        return;
      }
      clearStatus('Se recibió un evento inválido; reconectando.');
      if (ev.type === 'snapshot' || ev.type === 'clear') resetDetailCache();
      const selectionInvalid = applyEvent(ev);
      if (selectionInvalid) {
        invalidSelections.add(state.selected);
        if (refreshId === state.selected) refreshId = undefined;
      } else if (ev.type === 'snapshot' && state.selected != null) {
        if (!invalidSelections.has(state.selected)) refreshId = state.selected;
      } else if (ev.type === 'record') {
        // a new request also stops the timer of the one it follows
        if ((ev.rec.id === state.selected || ev.rec.prev_id === state.selected) && !invalidSelections.has(state.selected)) {
          refreshId = state.selected;
        }
      }
      schedulePaint();
    };
  };

  open();
  return () => {
    closed = true;
    clearTimeout(retryTimer);
    retryTimer = undefined;
    if (paintFrame !== undefined) cancelAnimationFrame(paintFrame);
    paintFrame = undefined;
    refreshId = undefined;
    invalidSelections.clear();
    source?.close();
  };
}
