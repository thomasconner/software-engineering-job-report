import d3 from './d3.js';
import { parseArticle } from './article.js';
import { renderChart } from './charts.js';
import { renderCompare } from './compare.js';
import {
  AuthoringError, WINDOWS, addMonths, monthLabel, makeFormat, categoryLabel, METHOD_LABEL, prepare, resolveCompareRows,
  periodLabel, ribbonKey,
} from './data.js';

const params = new URLSearchParams(location.search);
const mock = params.get('mock') === '1';
// Authors (mock previews and local servers) see directive mistakes in full; readers see a quiet placeholder.
const authoring = mock || ['localhost', '127.0.0.1'].includes(location.hostname);
const SAMPLE = '_sample';
const $ = (sel) => document.querySelector(sel);

setupTheme();
main().catch((err) => showError(err.message));

async function main() {
  const [raw, manifest] = await Promise.all([
    fetchJson(mock ? 'data/metrics.mock.json' : 'data/metrics.json',
      mock ? 'The mock data file is missing.' : 'The first issue has not been published yet. Add ?mock=1 to the address to preview the layout with synthetic numbers.'),
    fetchJson('articles/index.json', 'The article list (articles/index.json) is missing.'),
  ]);
  const data = prepare(raw);
  const issues = manifest.months.filter((m) => !data.pending.has(m)).sort().reverse();
  if (mock) issues.push(SAMPLE);
  if (!issues.length) throw new Error('The first issue has not been published yet.');

  const wanted = params.get('issue');
  // Samples (files starting with _) are reachable by name only in authoring mode (mock data or a local server).
  const issue = issues.includes(wanted) || (authoring && wanted?.startsWith('_')) ? wanted : issues[0];
  const res = await fetch(`articles/${issue}.md`);
  if (!res.ok) throw new Error(`The article for ${issue} could not be loaded.`);
  const article = parseArticle(await res.text());
  // Never past the last complete month, even if the article claims a later one.
  const until = [article.meta.month, data.lastComplete].filter(Boolean).sort()[0];

  if (data.mock) $('#mock-banner').hidden = false;
  renderPicker(issues, issue);
  renderHeader(article.meta, until, data);
  renderRibbon(data, until, ribbonKey(article.meta));
  renderBody(article, data, until);
  renderMethodology(data, until);
}

async function fetchJson(url, message) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(message);
  return res.json();
}

function showError(message) {
  const p = document.createElement('p');
  p.className = 'load-error';
  p.textContent = message;
  $('#article-body').replaceChildren(p);
  $('#headline').textContent = 'No issue to show yet';
  if (!$('#issue-picker').options.length) $('.picker').hidden = true;
  $('#glossary-title').hidden = true;
  $('#sources-title').hidden = true;
  $('#sources-intro').hidden = true;
  $('.ribbon-figure').hidden = true;
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
  const options = issues.includes(issue) ? issues : [...issues, issue];
  select.replaceChildren(...options.map((m) => new Option(m === SAMPLE ? 'Sample issue (mock)' : m.startsWith('_') ? `${m.slice(1)} (sample)` : monthLabel(m, 'long'), m, false, m === issue)));
  select.addEventListener('change', () => {
    params.set('issue', select.value);
    location.search = params.toString();
  });
}

function renderHeader(meta, until, data) {
  const headline = meta.headline ?? 'Untitled issue';
  $('#headline').textContent = headline;
  $('#dek').textContent = meta.dek ?? '';
  $('#byline').textContent = `By ${meta.byline ?? 'Software Engineering Jobs Report'}`;
  const time = $('#dateline');
  time.dateTime = until;
  time.textContent = `${monthLabel(until, 'long')} issue`;
  $('#data-stamp').textContent = data.mock
    ? 'Mock data for layout testing'
    : `Data updated ${new Date(data.generated_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' })}`;
  document.title = `${headline} | Software Engineering Jobs Report`;
}

// Masthead strip: one series (front matter `ribbon`, see data.ribbonKey) for every complete month up
// to this issue, with the comparison months marked.
function renderRibbon(data, until, key) {
  const wrap = $('#ribbon');
  const caption = $('#ribbon-caption');
  let series;
  try {
    [series] = resolveCompareRows(data, key, until);
  } catch (err) {
    if (authoring) console.warn(`ribbon: ${err.message}`);
    $('.ribbon-figure').hidden = true;
    return;
  }
  const pts = series.points;
  if (!pts.length) {
    $('.ribbon-figure').hidden = true;
    return;
  }
  const marks = new Map(Object.entries(WINDOWS).map(([k, n]) => [addMonths(until, -n), k]));
  const fmt = makeFormat(series.unit);
  const what = series.external
    ? `${series.label} in each issue since ${monthLabel(pts[0].month)}, as published by its date`
    : `${series.label} in Hacker News's "Who is hiring?" thread each month since ${monthLabel(pts[0].month)}`;
  const defaultCaption = `${what}. Marked bars show 5 years, 1 year and 3 months before ${monthLabel(until)}.`;
  caption.textContent = defaultCaption;
  wrap.setAttribute('aria-label', `${defaultCaption} Use the arrow keys to read each month.`);
  let idx = pts.length - 1;
  let x;

  const read = (i, keyboard) => {
    idx = Math.max(0, Math.min(pts.length - 1, i));
    const p = pts[idx];
    const text = series.external
      ? `${monthLabel(p.month, 'long')} issue: ${fmt(p.value)} (${periodLabel(p.ref_period)} data)`
      : `${monthLabel(p.month, 'long')}: ${fmt(p.value)} hiring posts on Hacker News`;
    caption.textContent = text;
    wrap.querySelector('.cursor')?.setAttribute('x', x(pts[idx].month));
    wrap.querySelector('.cursor')?.removeAttribute('hidden');
    if (keyboard) $('#ribbon-live').textContent = text;
  };
  const reset = () => {
    caption.textContent = defaultCaption;
    wrap.querySelector('.cursor')?.setAttribute('hidden', '');
  };

  const draw = () => {
    const width = wrap.clientWidth;
    if (!width) return;
    const phone = width < 520;
    const barsH = phone ? 50 : 62;
    x = d3.scaleBand().domain(pts.map((p) => p.month)).range([0, width]).paddingInner(width / pts.length > 4 ? 0.25 : 0.1);
    const y = d3.scaleLinear().domain([0, d3.max(pts, (p) => p.value)]).range([barsH, 4]);
    const svg = d3.create('svg').attr('width', width).attr('aria-hidden', 'true');
    svg.selectAll('rect.bar').data(pts).join('rect')
      .attr('class', (p) => (p.month === until ? 'bar now' : marks.has(p.month) ? 'bar mark' : 'bar'))
      .attr('x', (p) => x(p.month)).attr('width', Math.max(1, x.bandwidth()))
      .attr('y', (p) => y(p.value)).attr('height', (p) => y(0) - y(p.value));
    svg.append('rect').attr('class', 'cursor').attr('y', 0).attr('height', barsH).attr('width', Math.max(2, x.bandwidth())).attr('hidden', '');
    wrap.replaceChildren(svg.node());
    // The issue month is named above its own bar, so it never competes with the window labels underneath.
    const now = pts.at(-1);
    svg.append('text').attr('class', 'now').attr('x', width).attr('y', Math.max(10, y(now.value) - 5))
      .attr('text-anchor', 'end').text(monthLabel(until));
    // Window labels go on the first row that has room; the strip grows another row rather than dropping one.
    const rows = [];
    for (const [m, key] of [...marks].reverse()) {
      if (x(m) == null) continue;
      const cx = x(m) + x.bandwidth() / 2;
      svg.append('line').attr('class', 'tick').attr('x1', cx).attr('x2', cx).attr('y1', barsH + 1).attr('y2', barsH + 5);
      const t = svg.append('text').text(phone ? key : `${key} ago`);
      const w = t.node().getComputedTextLength();
      const left = Math.min(width - w, Math.max(0, cx - w / 2));
      let r = rows.findIndex((row) => !row.some(([a, b]) => left < b + 6 && left + w > a - 6));
      if (r === -1) r = rows.push([]) - 1;
      rows[r].push([left, left + w]);
      t.attr('x', left).attr('y', barsH + 16 + r * 13);
    }
    const height = barsH + 6 + rows.length * 13;
    svg.attr('height', height).attr('viewBox', `0 0 ${width} ${height}`);
  };

  // pointerdown as well as pointermove, so a tap on a phone reads a month too.
  const onPoint = (ev) => {
    if (x) read(Math.floor((ev.clientX - wrap.getBoundingClientRect().left) / x.step()));
  };
  wrap.addEventListener('pointermove', onPoint);
  wrap.addEventListener('pointerdown', onPoint);
  wrap.addEventListener('pointerleave', reset);
  wrap.addEventListener('focus', () => read(idx, true));
  wrap.addEventListener('blur', () => { reset(); idx = pts.length - 1; });
  wrap.addEventListener('keydown', (ev) => {
    const step = { ArrowLeft: -1, ArrowRight: 1, Home: -Infinity, End: Infinity }[ev.key];
    if (step == null) return;
    read(idx + (Number.isFinite(step) ? step : step > 0 ? pts.length : -pts.length), true);
    ev.preventDefault();
  });
  new ResizeObserver(() => requestAnimationFrame(draw)).observe(wrap);
}

function mountDirective(mount, name, attrs, data, until) {
  try {
    if (name === 'compare') renderCompare(mount, attrs, data, until);
    else renderChart(mount, attrs, data, until);
  } catch (err) {
    showDirectiveError(mount, err);
  }
}

function showDirectiveError(mount, err) {
  const box = document.createElement('p');
  if (authoring) {
    box.className = 'directive-error';
    box.textContent = `${err instanceof AuthoringError ? 'Directive error' : 'Chart failed'}: ${err.message}`;
    console.warn(err);
  } else {
    box.className = 'directive-unavailable';
    box.textContent = 'This chart is unavailable.';
  }
  mount.replaceChildren(box);
}

function renderBody(article, data, until) {
  const body = $('#article-body');
  body.innerHTML = article.html;
  for (const mount of body.querySelectorAll('.directive')) {
    const { name, attrs, error } = article.directives[mount.dataset.directive];
    if (error) showDirectiveError(mount, error);
    else mountDirective(mount, name, attrs, data, until);
  }
  arrangeFigures(body, article.directives);
}

// On wide screens regular charts float beside the text, alternating right and left; the strip, small multiples
// and `layout="wide"` charts span the page. Keep the breakpoint in step with style.css.
const FLOAT_QUERY = matchMedia('(min-width: 80rem)');
const MIN_PROSE = 500; // characters, about ten lines beside a float
const isProse = (node) => ['P', 'UL', 'OL', 'BLOCKQUOTE'].includes(node?.tagName);

function arrangeFigures(body, directives) {
  const hoisted = [];
  let floats = 0;
  for (const mount of body.querySelectorAll('.directive')) {
    const { name, attrs } = directives[mount.dataset.directive];
    if (!mount.querySelector('.chart, .compare')) continue; // errors stay in the column
    if (name === 'compare' || attrs.type === 'small-multiples' || attrs.layout === 'wide') {
      mount.dataset.layout = 'wide';
      continue;
    }
    // Articles put a chart after the paragraphs it backs. A float only wraps the text that follows it, so on
    // wide screens the chart moves up to the start of that run of paragraphs and goes back on narrow ones.
    // A sentence or two beside a chart leaves a hole under it, so a short run stays in the column.
    let start = mount;
    let text = 0;
    while (isProse(start.previousElementSibling)) {
      start = start.previousElementSibling;
      text += start.textContent.length;
    }
    for (let next = mount.nextElementSibling; start === mount && isProse(next); next = next.nextElementSibling) {
      text += next.textContent.length;
    }
    if (text < MIN_PROSE) continue;
    mount.dataset.layout = 'float';
    mount.dataset.side = floats++ % 2 ? 'left' : 'right';
    if (start === mount) continue;
    const anchor = document.createComment('chart');
    mount.before(anchor);
    hoisted.push({ mount, start, anchor });
  }
  if (!hoisted.length) return;
  const place = () => {
    for (const { mount, start, anchor } of hoisted) {
      if (FLOAT_QUERY.matches) start.before(mount);
      else anchor.after(mount);
    }
  };
  FLOAT_QUERY.addEventListener('change', place);
  place();
}

// Plain names for the Jev questions scored in validation.json, and the measures they feed.
const QUESTIONS = [
  ['work_mode', 'Remote, hybrid or onsite', 'work_mode'],
  ['seniority', 'Seniority of the roles', 'seniority'],
  ['industry', 'What the company makes', 'industry'],
  ['funding_stage', 'Funding stage', 'funding_stage'],
  ['ai_native', 'Describes an AI product', 'ai_native_share.hiring'],
  ['new_grad', 'Open to new grads', 'new_grad_share.hiring'],
  ['eng_leadership', 'Hiring engineering leads', 'eng_leadership_share.hiring'],
  ['seeker_mood', 'Job-seeker mood', 'seeker_mood.seeking'],
];

async function renderValidation(data) {
  const res = await fetch('data/validation.json');
  if (!res.ok) return;
  const v = await res.json();
  const pct = (x) => `${Math.round(x * 100)}%`;
  const table = document.createElement('table');
  table.className = 'validation-table';
  const head = table.createTHead().insertRow();
  for (const h of ['Question', 'Right on held-out posts', 'Posts checked']) {
    const th = document.createElement('th');
    th.textContent = h;
    head.append(th);
  }
  const body = table.createTBody();
  for (const [q, name, key] of QUESTIONS) {
    const held = v.holdout?.questions?.[q]?.overall;
    const ref = v.reference?.questions?.[q]?.overall;
    if (!held && !ref) continue;
    const row = body.insertRow();
    const th = document.createElement('th');
    th.scope = 'row';
    th.textContent = name;
    const measure = data.metrics[key] ?? data.breakdowns[key];
    if (measure?.confidence === 'rough') {
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = 'rough';
      th.append(' ', badge);
    }
    const acc = row.insertCell();
    const n = row.insertCell();
    if (held?.n) {
      acc.textContent = pct(held.accuracy);
      n.textContent = held.n;
    } else {
      // No held-out labels yet: show the score on the posts used to write the question, and say so.
      acc.textContent = `${pct(ref.accuracy)}*`;
      n.textContent = `${ref.n}*`;
    }
    row.prepend(th);
  }
  const notes = document.createElement('p');
  notes.className = 'validation-note';
  notes.textContent = `Held-out posts are ${v.holdout?.n_labels ?? 'a set of'} hiring posts never used to write or tune the questions. "Right" means the model's top answer matched the label both annotators agreed on. "Rough" marks a measure to read as a broad picture, not a precise share.${body.textContent.includes('*') ? ' * Scored only on the posts used to write the question, so likely optimistic.' : ''}`;
  $('#validation').replaceChildren(table, notes);
}

// One entry per source from metrics.json `sources`: what it measures, coverage, newest data, lag,
// credit and caveat. A back issue shows only what existed by its month.
function renderSources(data, until) {
  const sources = (data.sources ?? []).filter((s) => s.coverage_start <= until);
  const newestRef = (s) => s.series.map((key) => data.external?.[key]?.series.filter((p) => p.month <= until).at(-1)?.ref_period)
    .filter(Boolean).sort().at(-1);
  $('#sources').replaceChildren(...sources.flatMap((s) => {
    const dt = document.createElement('dt');
    dt.textContent = s.name;
    const dd = document.createElement('dd');
    const line = (label, text) => {
      const p = document.createElement('p');
      const b = document.createElement('span');
      b.className = 'source-field';
      b.textContent = `${label}: `;
      p.append(b, text);
      return p;
    };
    const credit = document.createElement('span');
    const name = s.credit || s.name;
    if (s.url) {
      const link = document.createElement('a');
      link.href = s.url;
      link.textContent = name;
      credit.append(link);
    } else {
      credit.append(name);
    }
    if (s.license) {
      let lic = s.license;
      if (s.license_url) {
        lic = document.createElement('a');
        lic.href = s.license_url;
        lic.textContent = s.license;
      }
      credit.append(' (', lic, ')');
    }
    const end = s.coverage_end < until ? s.coverage_end : until;
    const ref = newestRef(s);
    dd.append(
      line('Measures', s.measures),
      line('Coverage', `${monthLabel(s.coverage_start, 'long')} to ${monthLabel(end, 'long')} issues${ref ? `; this issue carries ${periodLabel(ref)} data` : ''}`),
      line('Lag', s.lag),
      line('Credit', credit),
    );
    if (s.caveat) dd.append(line('Caveat', s.caveat));
    return [dt, dd];
  }));
  for (const id of ['#sources-title', '#sources-intro']) $(id).hidden = !sources.length;
}

function renderMethodology(data, until) {
  renderSources(data, until);
  renderValidation(data).catch(() => { /* the table is optional; the prose still explains the checks */ });
  const removed = ['removed_share.hiring', 'removed_share.seeking'].filter((k) => data.metrics[k]);
  if (removed.length) {
    mountDirective($('#removed-chart'), 'chart', {
      type: 'line',
      metric: removed.join(','),
      title: 'Share of posts deleted or removed before our snapshot',
      note: 'Removed posts are counted here but not added back into post counts.',
    }, data, until);
  }

  const entries = [
    ...Object.entries(data.metrics).map(([, m]) => ({ label: m.label, text: m.description, method: m.method })),
    ...Object.entries(data.breakdowns).map(([key, b]) => ({
      label: b.label,
      text: `${b.categories.map((c) => categoryLabel(c, b)).join(', ')}. ${b.description ?? (key === 'stack' ? 'Each term is its own share, so these do not add up to 100%.' : 'Shares add up to about 100% each month.')}`,
      method: b.method,
    })),
  ];
  $('#glossary').replaceChildren(...entries.flatMap((e) => {
    const dt = document.createElement('dt');
    dt.textContent = e.label;
    const dd = document.createElement('dd');
    dd.textContent = `${e.text.replace(/\.$/, '')}. `;
    const method = document.createElement('span');
    method.className = 'method';
    method.textContent = METHOD_LABEL[e.method] ?? e.method;
    dd.append(method);
    return [dt, dd];
  }));
}
