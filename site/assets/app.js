import { parseArticle } from './article.js';
import { isEditorsNote, mountDirective as mountWith, toplinePlan } from './directives.js';
import { renderChart } from './charts.js';
import { renderCompare } from './compare.js';
import { AuthoringError, monthLabel, categoryLabel, METHOD_LABEL, prepare, periodLabel } from './data.js';

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

const fetchData = (url) => fetchJson(url, `${url} could not be loaded.`);
const draw = (mount, name, attrs, data, until) => (name === 'compare' ? renderCompare : renderChart)(mount, attrs, data, until);

function mountDirective(mount, name, attrs, data, until) {
  return mountWith(mount, name, attrs, data, until, { render: draw, fetchJson: fetchData, onError: showDirectiveError });
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
  const mounts = [...body.querySelectorAll('.directive')];
  // A ::compare written before the first section head is the issue's topline (see directives.toplinePlan).
  const blocks = [...body.children];
  const plan = toplinePlan(blocks.map((el) => {
    const entry = el.classList.contains('directive') ? article.directives[el.dataset.directive] : null;
    const only = el.childElementCount === 1 ? el.firstElementChild : null;
    return {
      tag: el.tagName, name: entry?.name, error: Boolean(entry?.error),
      editorsNote: isEditorsNote({ tag: el.tagName, text: el.textContent, allItalic: only?.tagName === 'EM' && only.textContent.trim() === el.textContent.trim() }),
    };
  }));
  if (plan) {
    const strip = blocks[plan.from];
    strip.classList.add('topline');
    if (plan.from !== plan.to) blocks[plan.to].before(strip);
  }
  for (const mount of mounts) {
    const { name, attrs, error } = article.directives[mount.dataset.directive];
    if (error) showDirectiveError(mount, error);
    else mountDirective(mount, name, attrs, data, until);
  }
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
