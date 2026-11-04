import * as d3 from 'https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm';
import { parseArticle } from './article.js';
import { renderChart } from './charts.js';
import { renderCompare } from './compare.js';
import { addMonths, monthLabel, formatValue, categoryLabel, METHOD_LABEL } from './data.js';

const params = new URLSearchParams(location.search);
const mock = params.get('mock') === '1';
const SAMPLE = '_sample';
const $ = (sel) => document.querySelector(sel);

setupTheme();
main().catch((err) => showError(err.message));

async function main() {
  const [data, manifest] = await Promise.all([
    fetchJson(mock ? 'data/metrics.mock.json' : 'data/metrics.json',
      mock ? 'The mock data file is missing.' : 'The report data has not been published yet. Add ?mock=1 to the address to preview the layout with synthetic numbers.'),
    fetchJson('articles/index.json', 'The article list (articles/index.json) is missing.'),
  ]);
  const issues = [...manifest.months].sort().reverse();
  if (mock) issues.push(SAMPLE);
  if (!issues.length) throw new Error('No issue has been published yet.');

  const wanted = params.get('issue');
  const issue = issues.includes(wanted) ? wanted : issues[0];
  const res = await fetch(`articles/${issue}.md`);
  if (!res.ok) throw new Error(`The article for ${issue} could not be loaded.`);
  const article = parseArticle(await res.text());
  const until = [article.meta.month, data.latest_month].filter(Boolean).sort()[0];

  if (data.mock) $('#mock-banner').hidden = false;
  renderPicker(issues, issue);
  renderHeader(article.meta, until, data);
  renderRibbon(data, until);
  renderBody(article, data, until);
  renderGlossary(data);
}

async function fetchJson(url, message) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(message);
  return res.json();
}

function showError(message) {
  const body = $('#article-body');
  body.replaceChildren();
  const p = document.createElement('p');
  p.className = 'load-error';
  p.textContent = message;
  body.append(p);
  $('#headline').textContent = 'No issue to show yet';
  if (!$('#issue-picker').options.length) $('.picker').hidden = true;
  $('#glossary-title').hidden = true;
}

function setupTheme() {
  const button = $('#theme-toggle');
  const root = document.documentElement;
  const current = () => root.dataset.theme ?? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const label = () => {
    const next = current() === 'dark' ? 'light' : 'dark';
    button.textContent = `${next === 'dark' ? 'Dark' : 'Light'} theme`;
    button.setAttribute('aria-label', `Switch to ${next} theme`);
  };
  try {
    const saved = localStorage.getItem('theme');
    if (saved) root.dataset.theme = saved;
  } catch { /* storage blocked: follow the system setting */ }
  label();
  button.addEventListener('click', () => {
    root.dataset.theme = current() === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('theme', root.dataset.theme); } catch { /* not persisted */ }
    label();
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', label);
}

function renderPicker(issues, issue) {
  const select = $('#issue-picker');
  select.replaceChildren(...issues.map((m) => new Option(m === SAMPLE ? 'Sample issue (mock)' : monthLabel(m, 'long'), m, false, m === issue)));
  select.addEventListener('change', () => {
    params.set('issue', select.value);
    location.search = params.toString();
  });
}

function renderHeader(meta, until, data) {
  const headline = meta.headline ?? 'Untitled issue';
  $('#headline').textContent = headline;
  $('#dek').textContent = meta.dek ?? '';
  $('#byline').textContent = `By ${meta.byline ?? 'Software Engineering Job Report'}`;
  const time = $('#dateline');
  time.dateTime = until;
  time.textContent = `${monthLabel(until, 'long')} issue`;
  const generated = new Date(data.generated_at);
  $('#data-stamp').textContent = data.mock
    ? 'Mock data for layout testing'
    : `Data updated ${generated.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' })}`;
  document.title = `${headline} | Software Engineering Job Report`;
}

// Masthead strip: every month of hiring posts up to this issue, with the comparison months picked out.
function renderRibbon(data, until) {
  const metric = data.metrics['posts.hiring'];
  const wrap = $('#ribbon');
  const caption = $('#ribbon-caption');
  if (!metric) return;
  const pts = metric.series.filter((p) => p.month <= until);
  const marks = new Map([['5y', 60], ['1y', 12], ['3m', 3]].map(([k, n]) => [addMonths(until, -n), k]));
  marks.set(until, 'now');
  const defaultCaption = `${metric.label} each month since ${monthLabel(pts[0].month)}. Dark bars mark 3 months, 1 year and 5 years before ${monthLabel(until)}.`;
  caption.textContent = defaultCaption;
  wrap.setAttribute('aria-label', `${defaultCaption}. ${formatValue(pts.at(-1).value, 'count')} this month.`);

  const draw = () => {
    const width = wrap.clientWidth;
    if (!width) return;
    const height = width < 520 ? 56 : 72;
    const x = d3.scaleBand().domain(pts.map((p) => p.month)).range([0, width]).paddingInner(width / pts.length > 4 ? 0.25 : 0.1);
    const y = d3.scaleLinear().domain([0, d3.max(pts, (p) => p.value)]).range([height - 18, 2]);
    const svg = d3.create('svg').attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`).attr('aria-hidden', 'true');
    svg.selectAll('rect').data(pts).join('rect')
      .attr('class', (p) => (p.month === until ? 'now' : marks.has(p.month) ? 'mark' : null))
      .attr('x', (p) => x(p.month)).attr('width', Math.max(1, x.bandwidth()))
      .attr('y', (p) => y(p.value)).attr('height', (p) => y(0) - y(p.value));
    wrap.replaceChildren(svg.node());
    // Label the marked months in priority order and skip any label that would overlap one already placed.
    const placed = [];
    for (const key of ['now', '5y', '1y', '3m']) {
      const m = [...marks].find(([, k]) => k === key)?.[0];
      if (x(m) == null) continue;
      const cx = x(m) + x.bandwidth() / 2;
      const t = svg.append('text').attr('y', height - 4).attr('class', key === 'now' ? 'now' : null)
        .text(key === 'now' ? monthLabel(m) : `${key} ago`);
      const w = t.node().getComputedTextLength();
      const left = key === 'now' ? cx - w : Math.min(width - w, Math.max(0, cx - w / 2));
      t.attr('x', left);
      if (placed.some(([a, b]) => left < b + 8 && left + w > a - 8)) t.remove();
      else placed.push([left, left + w]);
    }
    svg.append('rect').attr('class', 'ribbon-hit').attr('width', width).attr('height', height)
      .on('pointermove', (ev) => {
        const i = Math.min(pts.length - 1, Math.max(0, Math.floor(d3.pointer(ev)[0] / x.step())));
        caption.textContent = `${monthLabel(pts[i].month, 'long')}: ${formatValue(pts[i].value, 'count')} companies hiring`;
      })
      .on('pointerleave', () => { caption.textContent = defaultCaption; });
  };
  new ResizeObserver(() => requestAnimationFrame(draw)).observe(wrap);
}

function renderBody(article, data, until) {
  const body = $('#article-body');
  body.innerHTML = article.html;
  for (const mount of body.querySelectorAll('.directive')) {
    const { name, attrs } = article.directives[mount.dataset.directive];
    try {
      if (name === 'compare') renderCompare(mount, attrs, data, until);
      else renderChart(mount, attrs, data, until);
    } catch (err) {
      mount.className = 'directive-error';
      mount.textContent = `Chart could not be drawn: ${err.message}`;
      console.error(err);
    }
  }
}

function renderGlossary(data) {
  const list = $('#glossary');
  const entries = [
    ...Object.entries(data.metrics).map(([key, m]) => ({ label: m.label, text: m.description, method: m.method, key })),
    ...Object.entries(data.breakdowns).map(([key, b]) => ({
      label: b.label,
      text: `${b.categories.map(categoryLabel).join(', ')}.${key === 'stack' ? ' Each term is its own share, so these do not add up to 100%.' : ' Shares add up to about 100% each month.'}`,
      method: b.method,
      key,
    })),
  ];
  list.replaceChildren(...entries.flatMap((e) => {
    const dt = document.createElement('dt');
    dt.textContent = e.label;
    const dd = document.createElement('dd');
    dd.textContent = `${e.text}. `.replace('.. ', '. ');
    const method = document.createElement('span');
    method.className = 'method';
    method.textContent = METHOD_LABEL[e.method] ?? e.method;
    dd.append(method);
    return [dt, dd];
  }));
}
