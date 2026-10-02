import { $ } from './format.js';
import { state } from './state.js';
import { tick } from './cache-timer.js';
import { showDetail, closeDetail } from './detail.js';
import { SELECT_FILTERS, TOGGLE_FILTERS, pressed, render, resetFilters } from './list.js';
import { connect } from './stream.js';

// ---------- events ----------

$('rows').addEventListener('click', (e) => {
  const tr = e.target.closest('tr');
  if (tr) showDetail(Number(tr.dataset.id));
});

for (const [id] of SELECT_FILTERS) $(id).addEventListener('change', render);
$('f-text').addEventListener('input', render);
$('reset').addEventListener('click', resetFilters);
for (const id of TOGGLE_FILTERS) {
  $(id).addEventListener('click', () => {
    $(id).setAttribute('aria-pressed', String(!pressed(id)));
    render();
  });
}

// Clearing drops every captured request, so it takes a second click to confirm.
const clear = $('clear');
let disarmTimer;
const disarm = () => {
  clearTimeout(disarmTimer);
  clear.classList.remove('armed');
  clear.textContent = 'Limpiar';
};
clear.addEventListener('click', () => {
  if (!clear.classList.contains('armed')) {
    clear.classList.add('armed');
    clear.textContent = '¿Borrar todo?';
    disarmTimer = setTimeout(disarm, 3000);
    return;
  }
  disarm();
  fetch('/api/clear', { method: 'POST' });
});

document.addEventListener('keydown', (e) => {
  const typing = e.target instanceof Element && e.target.matches('input, select, textarea');
  if (e.key === 'Escape') {
    if (typing) e.target.blur();
    else if (state.selected != null) closeDetail();
    return;
  }
  if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === '/') {
    e.preventDefault();
    $('f-text').focus();
    return;
  }
  const step = { ArrowDown: 1, j: 1, ArrowUp: -1, k: -1 }[e.key];
  if (!step || !state.visible.length) return;
  e.preventDefault();
  const index = state.visible.findIndex((r) => r.id === state.selected);
  const next = index === -1 ? 0 : Math.min(state.visible.length - 1, Math.max(0, index + step));
  showDetail(state.visible[next].id, true);
});

setInterval(tick, 1000);

$('help-open').addEventListener('click', () => $('help').showModal());

connect();
