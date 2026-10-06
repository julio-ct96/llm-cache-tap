export const $ = (id) => document.getElementById(id);
export const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
export const num = (n) => (n == null ? '–' : Number(n).toLocaleString('es-ES'));
export const secs = (n) => (n == null ? '–' : n.toFixed(2) + ' s');
export const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
export const duration = (s) => (s < 3600 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`);

const MONEY = [2, 3, 4].map((digits) => new Intl.NumberFormat('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits }));
const RATE = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 4 });

/** Dollars with more decimals the smaller the amount, since most requests cost a fraction of a cent. */
export function usd(n) {
  if (n == null) return '–';
  const abs = Math.abs(n);
  if (abs > 0 && abs < 0.00005) return `${n < 0 ? '> −' : '< '}0,0001 $`;
  return MONEY[abs === 0 || abs >= 1 ? 0 : abs >= 0.01 ? 1 : 2].format(n) + ' $';
}
export const rate = (n) => (n == null ? '–' : RATE.format(n));
export const pct = (part, whole) => (whole ? ((100 * part) / whole).toFixed(1).replace('.', ',') + ' %' : '–');
