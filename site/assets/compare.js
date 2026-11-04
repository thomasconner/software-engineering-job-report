// ::compare: each metric's value this month against 3 months, 1 year and 5 years earlier.
import d3 from './d3.js';
import {
  addMonths, monthLabel, resolveCompareRows, compareCells, sourceLine, MODEL_NOTE, needsModelNote,
  WINDOWS, WINDOW_LABEL,
} from './data.js';

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

function sparkline(series, until, windows) {
  const start = addMonths(until, -WINDOWS[windows.at(-1)] - 6);
  const pts = series.points.filter((p) => p.month >= start);
  const w = 112;
  const h = 28;
  const x = d3.scaleUtc().domain(d3.extent(pts, (p) => p.date)).range([4, w - 4]);
  const y = d3.scaleLinear().domain(d3.extent(pts, (p) => p.value)).range([h - 4, 4]);
  const svg = d3.create('svg').attr('class', 'spark').attr('width', w).attr('height', h).attr('viewBox', `0 0 ${w} ${h}`).attr('aria-hidden', 'true');
  svg.append('path').attr('d', d3.line().x((p) => x(p.date)).y((p) => y(p.value))(pts));
  for (const m of [...windows.map((a) => addMonths(until, -WINDOWS[a])), until]) {
    const p = pts.find((q) => q.month === m);
    if (p) svg.append('circle').attr('class', m === until ? 'now' : 'then').attr('cx', x(p.date)).attr('cy', y(p.value)).attr('r', m === until ? 3.5 : 2.5);
  }
  return svg.node();
}

export function renderCompare(mount, attrs, data, until) {
  const windows = (attrs.against ?? '3m,1y,5y').split(',').map((s) => s.trim()).filter((a) => WINDOWS[a]);
  const series = resolveCompareRows(data, attrs.metrics, until);
  const outside = series.some((s) => s.external);

  const figure = el('figure', 'compare');
  const head = el('figcaption', 'chart-head');
  const heading = el('div', 'chart-heading');
  head.append(heading);
  heading.append(el('h3', 'chart-title', attrs.title));
  const span = windows.map((a) => WINDOW_LABEL[a]).join(', ').replace(/, ([^,]*)$/, ' and $1');
  const outsideNote = outside ? ' Outside sources show the period their number describes and have no noise bar, so their changes carry no verdict; each change compares readings from the same release.' : '';
  heading.append(el('p', 'chart-sub', attrs.subtitle ?? `${monthLabel(until, 'long')} against ${span} earlier. Better and worse are from the point of view of people looking for work; moves within the noise are gray and marked \u2248 (about the same).${outsideNote}`));

  const table = el('table', 'compare-table');
  const hr = table.createTHead().insertRow();
  hr.append(el('th', 'c-measure', 'Measure'), el('th', 'c-trend', 'Last 5 years'), el('th', 'c-now', monthLabel(until)));
  for (const a of windows) hr.append(el('th', 'c-delta', `vs ${monthLabel(addMonths(until, -WINDOWS[a]))}`));
  const body = table.createTBody();
  for (const s of series) {
    const cells = compareCells(s, until, windows);
    const tr = body.insertRow();
    const measure = el('th', 'c-measure', s.label);
    measure.scope = 'row';
    // Unadjusted outside series swing with the seasons, so a 3-month change says little on its own.
    if (s.external && !s.seasonallyAdjusted) measure.append(el('span', 'c-flag', 'Not seasonally adjusted'));
    const trend = el('td', 'c-trend');
    trend.append(sparkline(s, until, windows));
    const nowCell = el('td', 'c-now', cells.value);
    nowCell.dataset.label = cells.ref ?? monthLabel(until);
    if (cells.ref) nowCell.append(el('span', 'c-ref', cells.ref));
    tr.append(measure, trend, nowCell);
    for (const { window, change: c, was, missing, seasonal } of cells.deltas) {
      const td = el('td', 'c-delta');
      td.dataset.label = window;
      if (seasonal) {
        // Different calendar months of an unadjusted series: the gap is mostly the season.
        const chip = el('span', 'd d-flat d-seasonal', 'seasonal');
        chip.title = 'Not seasonally adjusted, and these two months fall in different seasons';
        td.append(chip, el('span', 'd-was', was));
      } else if (!c) {
        td.append(el('span', 'd-none', missing ?? 'No data'));
      } else {
        const chip = el('span', `d d-${c.tone}`);
        const mark = el('span', 'd-arrow', c.mark);
        mark.setAttribute('aria-hidden', 'true');
        chip.append(mark, c.text);
        // The word carries the verdict for readers who can't tell the colors apart.
        if (c.word) chip.append(el('span', c.tone === 'flat' ? 'd-word d-word-quiet' : 'd-word', c.word));
        td.append(chip, el('span', 'd-was', was));
      }
      tr.append(td);
    }
  }
  const foot = el('div', 'chart-foot');
  foot.append(sourceNode(series, attrs));
  figure.append(head, table, foot);
  mount.replaceChildren(figure);
}

/**
 * The source line under a chart or strip: the HN threads used, the model note, the author's note,
 * then each outside source by name and license with what this report changed (CC BY asks for both).
 * `changes(s)` lists those changes for one series, e.g. "indexed to Oct 2025 = 100".
 */
export function sourceNode(series, attrs, changes = () => []) {
  const source = el('p', 'chart-source', sourceLine(series));
  if (needsModelNote(series, attrs.note)) source.append(' ', modelNote());
  if (series.some((s) => s.confidence === 'rough')) source.append(' ', el('span', 'chart-note', 'A rough measure: read it as a broad picture.'));
  if (attrs.note) source.append(' ', el('span', 'chart-note', attrs.note));
  const seen = new Set();
  for (const s of series.filter((x) => x.credit)) {
    if (seen.has(s.key)) continue;
    seen.add(s.key);
    const credit = el('span', 'chart-credit', 'Source: ');
    const link = (text, href) => {
      const a = el('a', null, text);
      a.href = href;
      return a;
    };
    credit.append(link(s.credit, s.url));
    if (s.license) credit.append(' (', s.licenseUrl ? link(s.license, s.licenseUrl) : s.license, ')');
    const changed = changes(s).filter(Boolean).join(', ');
    credit.append(changed ? `; ${changed} by this report.` : '.');
    source.append(' ', credit);
  }
  return source;
}

export function modelNote() {
  const span = el('span', 'chart-note');
  const [before, after] = MODEL_NOTE.split('How we measure this');
  const link = el('a', null, 'How we measure this');
  link.href = '#method-title';
  span.append(before, link, after);
  return span;
}
