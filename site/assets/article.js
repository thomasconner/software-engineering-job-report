// Turns an article file (front matter + Markdown + ::chart / ::compare directives) into HTML and a directive list.
import { marked } from './vendor/marked-15.0.12.esm.js';
import { AuthoringError, EXTERNAL_PREFIX, WINDOWS, isMonth } from './data.js';

const FRONT_MATTER = /^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/;
const DIRECTIVE = /^::(chart|compare)\{(.*)\}\s*$/;
const FENCE = /^\s*(```|~~~)/;
// key="value" or key='value' with backslash escapes, or a value wrapped in curly quotes by a word processor.
const ATTR = /([\w-]+)\s*=\s*(?:"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'|\u201C([^\u201D]*)\u201D|\u2018([^\u2019]*)\u2019)/g;

// Which attributes each directive accepts (docs/architecture.md, "Directive attributes").
const COMMON = ['title', 'subtitle', 'note'];
const TIME = ['from', 'to', 'annotate'];
const ALLOWED = {
  line: ['metric', 'highlight', 'external', 'base', ...TIME],
  'stacked-area': ['metric', 'breakdown', 'categories', 'highlight', ...TIME],
  'small-multiples': ['metric', 'breakdown', 'categories', 'highlight', ...TIME],
  slope: ['metric', 'breakdown', 'categories', 'highlight', 'vs', 'months'],
  dot: ['metric', 'breakdown', 'categories', 'highlight', 'vs'],
  bar: ['metric', 'breakdown', 'categories', 'highlight', ...TIME],
  compare: ['metrics', 'against'],
};

const unescape = (s) => s.replace(/\\(.)/g, '$1');

function parseFrontMatter(text) {
  const match = text.match(FRONT_MATTER);
  if (!match) return { meta: {}, body: text };
  const meta = {};
  for (const line of match[1].split(/\r?\n/)) {
    const kv = line.match(/^(\w+):\s*(.*?)\s*$/);
    if (!kv) continue;
    const quoted = kv[2].match(/^"((?:\\.|[^"\\])*)"$|^'((?:''|[^'])*)'$/);
    meta[kv[1]] = quoted ? (quoted[1] != null ? unescape(quoted[1]) : quoted[2].replaceAll("''", "'")) : kv[2];
  }
  return { meta, body: text.slice(match[0].length) };
}

function parseAttrs(source) {
  const attrs = {};
  const leftover = source.replace(ATTR, (_, key, dq, sq, cdq, csq) => {
    attrs[key] = dq != null ? unescape(dq) : sq != null ? unescape(sq) : (cdq ?? csq);
    return '';
  });
  if (leftover.trim()) throw new AuthoringError(`Could not read "${leftover.trim()}". Write attributes as key="value".`);
  return attrs;
}

// Contract-level checks that need no data: attribute names, required fields and value formats.
function checkDirective(name, attrs) {
  const type = name === 'compare' ? 'compare' : attrs.type;
  if (!ALLOWED[type]) throw new AuthoringError(`Unknown chart type "${attrs.type ?? ''}"`);
  const allowed = new Set([...COMMON, ...ALLOWED[type], ...(name === 'chart' ? ['type'] : [])]);
  const unknown = Object.keys(attrs).filter((k) => !allowed.has(k));
  if (unknown.length) throw new AuthoringError(`${type} does not take ${unknown.map((k) => `"${k}"`).join(', ')}`);
  if (!attrs.title) throw new AuthoringError(`${type} needs a title that states the finding`);
  if (name === 'compare') {
    if (!attrs.metrics) throw new AuthoringError('compare needs metrics');
    const ids = attrs.metrics.split(',').map((s) => s.trim());
    const empty = ids.filter((id) => !id || id === EXTERNAL_PREFIX);
    if (empty.length) throw new AuthoringError(`metrics="${attrs.metrics}" has an empty id; outside series are written external:<key>`);
    const bad = (attrs.against ?? '').split(',').map((s) => s.trim()).filter((a) => a && !WINDOWS[a]);
    if (bad.length) throw new AuthoringError(`against takes 3m, 1y, 5y, not ${bad.join(', ')}`);
    return;
  }
  // A line can draw an outside series on its own (raw values) or paired with one HN metric (both indexed to base).
  const externalOnly = attrs.external && !attrs.metric && !attrs.breakdown;
  if (!externalOnly && !attrs.metric === !attrs.breakdown) throw new AuthoringError(`${type} needs either metric or breakdown`);
  if (externalOnly) {
    if (attrs.base) throw new AuthoringError('base indexes an external series against a metric; drop base to draw the external series on its own, in its own unit');
  } else if (attrs.external || attrs.base) {
    if (!attrs.external || !isMonth(attrs.base)) throw new AuthoringError('external with a metric needs base="YYYY-MM", the month both lines are indexed to 100');
    if (!attrs.metric || attrs.metric.includes(',')) throw new AuthoringError('external pairs with exactly one metric');
  }
  for (const key of ['from', 'to']) {
    if (attrs[key] && !isMonth(attrs[key])) throw new AuthoringError(`${key}="${attrs[key]}" must be YYYY-MM`);
  }
  const months = attrs.months?.split(',').map((m) => m.trim());
  if (months && (months.length !== 2 || !months.every(isMonth))) {
    throw new AuthoringError(`months="${attrs.months}" must be two months, like "2021-10,2026-10"`);
  }
  for (const a of (attrs.annotate ?? '').split(';').map((s) => s.trim()).filter(Boolean)) {
    if (!isMonth(a.slice(0, 7)) || a[7] !== ':') throw new AuthoringError(`annotate entry "${a}" must look like 2022-11:Label`);
  }
}

export function parseArticle(text) {
  const { meta, body } = parseFrontMatter(text.replace(/^\uFEFF/, ''));
  const directives = [];
  let fence = null;
  // Directives become empty placeholders so Markdown never sees them; charts mount into the placeholders later.
  const md = body.split(/\r?\n/).map((line) => {
    const f = line.match(FENCE);
    if (f) fence = fence === null ? f[1] : fence === f[1] ? null : fence;
    const d = fence === null && line.trim().match(DIRECTIVE);
    if (!d) return line;
    const entry = { name: d[1], attrs: {}, error: null };
    try {
      entry.attrs = parseAttrs(d[2]);
      checkDirective(entry.name, entry.attrs);
    } catch (err) {
      entry.error = err;
    }
    directives.push(entry);
    return `\n<div class="directive" data-directive="${directives.length - 1}"></div>\n`;
  }).join('\n');
  return { meta, directives, html: marked.parse(md) };
}
