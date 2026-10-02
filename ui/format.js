export const $ = (id) => document.getElementById(id);
export const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
export const num = (n) => (n == null ? '–' : Number(n).toLocaleString('es-ES'));
export const secs = (n) => (n == null ? '–' : n.toFixed(2) + ' s');
export const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
export const duration = (s) => (s < 3600 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`);
