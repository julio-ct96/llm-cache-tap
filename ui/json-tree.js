/*
 * Collapsible JSON viewer, in the spirit of the Chrome DevTools network panel.
 *
 * Children are built the first time a node opens, so large request bodies stay
 * cheap. Strings that hold JSON or a query string can be opened as objects.
 */

const PREVIEW_MAX = 80;
const STRING_MAX = 300;

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

const isContainer = (v) => v !== null && typeof v === 'object';
const size = (v) => (Array.isArray(v) ? v.length : Object.keys(v).length);

/** Structured data hidden inside a string value, if any. */
function embedded(s) {
  const t = s.trim();
  const wrapped = (a, b) => t.startsWith(a) && t.endsWith(b);
  if (t.length > 1 && (wrapped('{', '}') || wrapped('[', ']'))) {
    try {
      const value = JSON.parse(t);
      if (isContainer(value)) return { kind: 'json', value };
    } catch {
      /* not JSON after all */
    }
  }
  if (/^[^\s=&]+=[^\s&]*(&[^\s=&]+=[^\s&]*)+$/.test(s)) {
    return { kind: 'query', value: Object.fromEntries(new URLSearchParams(s)) };
  }
  return null;
}

function brief(v) {
  if (typeof v === 'string') return JSON.stringify(v.length > 24 ? v.slice(0, 24) + '…' : v);
  if (!isContainer(v)) return String(v);
  if (Array.isArray(v)) return v.length ? '[…]' : '[]';
  return size(v) ? '{…}' : '{}';
}

/** One-line summary of a collapsed container. */
function preview(v) {
  const isArray = Array.isArray(v);
  const entries = isArray ? v.map(brief) : Object.entries(v).map(([k, x]) => `${k}: ${brief(x)}`);
  const parts = [];
  let length = 0;
  for (const entry of entries) {
    if (length + entry.length > PREVIEW_MAX) {
      parts.push('…');
      break;
    }
    parts.push(entry);
    length += entry.length + 2;
  }
  return (isArray ? '[' : '{') + parts.join(', ') + (isArray ? ']' : '}');
}

function stringLeaf(s) {
  const span = el('span', 'jt-string');
  if (s.length <= STRING_MAX) {
    span.textContent = JSON.stringify(s);
    return span;
  }
  // Long strings are mostly prompts: collapsed they stay on one escaped line,
  // expanded they show their real line breaks.
  const short = JSON.stringify(s.slice(0, STRING_MAX)).slice(0, -1) + '…';
  const text = el('span', null, short);
  const more = el('button', 'jt-more');
  more.type = 'button';
  let open = false;
  const paint = () => {
    span.classList.toggle('jt-block', open);
    text.textContent = open ? s : short;
    more.textContent = open ? 'ver menos' : `ver todo · ${s.length.toLocaleString('es-ES')} caracteres`;
  };
  more.addEventListener('click', () => {
    open = !open;
    paint();
  });
  paint();
  span.append(text, more);
  return span;
}

function leaf(value) {
  if (typeof value === 'string') return stringLeaf(value);
  if (isContainer(value)) return el('span', 'jt-punct', Array.isArray(value) ? '[]' : '{}');
  return el('span', value === null ? 'jt-null' : `jt-${typeof value}`, String(value));
}

function label(key) {
  if (key === null) return [];
  return [el('span', typeof key === 'number' ? 'jt-index' : 'jt-key', String(key)), el('span', 'jt-punct', ': ')];
}

function build(key, value, path, level, ctx) {
  const inner = typeof value === 'string' ? embedded(value) : null;
  const kids = inner ? inner.value : value;

  if (!isContainer(kids) || size(kids) === 0) {
    const row = el('div', 'jt-row');
    row.append(...label(key), leaf(value));
    return row;
  }

  const node = el('div', 'jt-node');
  const head = el('div', 'jt-head');
  const summary = el('span', 'jt-preview');
  const children = el('div', 'jt-children');
  head.tabIndex = 0;
  head.setAttribute('role', 'button');
  head.append(el('span', 'jt-caret'), ...label(key));
  if (inner) head.append(el('span', 'jt-tag', inner.kind));
  head.append(summary);
  node.append(head, children);

  const count = Array.isArray(kids) ? `[${kids.length}]` : `{${size(kids)}}`;
  let built = false;
  const setOpen = (open) => {
    node.classList.toggle('open', open);
    head.setAttribute('aria-expanded', String(open));
    summary.textContent = open ? count : preview(kids);
    if (!open || built) return;
    built = true;
    const entries = Array.isArray(kids) ? kids.map((v, i) => [i, v]) : Object.entries(kids);
    for (const [k, v] of entries) children.append(build(k, v, `${path}/${k}`, level + 1, ctx));
  };
  const toggle = () => {
    const open = !node.classList.contains('open');
    ctx.state.set(path, open);
    setOpen(open);
  };

  head.addEventListener('click', () => {
    // Let the user select text in a header without toggling it.
    if (!String(window.getSelection())) toggle();
  });
  head.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    toggle();
  });

  const all = ctx.state.get('*');
  const byDefault = all ?? (level < ctx.depth && !inner);
  setOpen(ctx.state.has(path) ? ctx.state.get(path) : byDefault);
  return node;
}

/**
 * @param value  any JSON value
 * @param state  Map of path -> open, kept by the caller so the tree survives re-renders
 * @param depth  levels open by default
 */
export function jsonTree(value, { state = new Map(), depth = 1 } = {}) {
  const root = el('div', 'jt');
  const ctx = { state, depth };
  const paint = () => root.replaceChildren(build(null, value, '$', 0, ctx));
  paint();
  return {
    el: root,
    setAll(open) {
      state.clear();
      state.set('*', open);
      paint();
    },
  };
}
