// ::compare: each metric's value this month against 3 months, 1 year and 5 years earlier.
import d3 from './d3.js';
import {
  addMonths, monthLabel, makeFormat, change, resolveSeries, valueAt, sourceLine, MODEL_NOTE, needsModelNote,
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
  const series = resolveSeries(data, attrs, until);

  const figure = el('figure', 'compare');
  const head = el('figcaption', 'chart-head');
  head.append(el('h3', 'chart-title', attrs.title));
  const span = windows.map((a) => WINDOW_LABEL[a]).join(', ').replace(/, ([^,]*)$/, ' and $1');
  head.append(el('p', 'chart-sub', attrs.subtitle ?? `${monthLabel(until, 'long')} against ${span} earlier. Better and worse are from the point of view of people looking for work; moves within the noise are gray and marked \u2248 (about the same).`));

  const table = el('table', 'compare-table');
  const hr = table.createTHead().insertRow();
  hr.append(el('th', 'c-measure', 'Measure'), el('th', 'c-trend', 'Last 5 years'), el('th', 'c-now', monthLabel(until)));
  for (const a of windows) hr.append(el('th', 'c-delta', `vs ${monthLabel(addMonths(until, -WINDOWS[a]))}`));
  const body = table.createTBody();
  for (const s of series) {
    const fmt = makeFormat(s.unit);
    const tr = body.insertRow();
    const measure = el('th', 'c-measure', s.label);
    measure.scope = 'row';
    const trend = el('td', 'c-trend');
    trend.append(sparkline(s, until, windows));
    const nowCell = el('td', 'c-now', fmt(valueAt(s, until)));
    nowCell.dataset.label = monthLabel(until);
    tr.append(measure, trend, nowCell);
    for (const a of windows) {
      const thenMonth = addMonths(until, -WINDOWS[a]);
      const c = change(s, thenMonth, until);
      const td = el('td', 'c-delta');
      td.dataset.label = a;
      if (!c) {
        td.append(el('span', 'd-none', 'No data'));
      } else {
        const chip = el('span', `d d-${c.tone}`);
        const mark = el('span', 'd-arrow', c.mark);
        mark.setAttribute('aria-hidden', 'true');
        chip.append(mark, c.text);
        // The word carries the verdict for readers who can't tell the colors apart.
        if (c.word) chip.append(el('span', c.tone === 'flat' ? 'd-word d-word-quiet' : 'd-word', c.word));
        td.append(chip, el('span', 'd-was', `from ${fmt(valueAt(s, thenMonth))}`));
      }
      tr.append(td);
    }
  }
  const foot = el('p', 'chart-source', sourceLine(series));
  if (needsModelNote(series, attrs.note)) foot.append(' ', modelNote());
  if (attrs.note) foot.append(' ', el('span', 'chart-note', attrs.note));
  figure.append(head, table, foot);
  mount.replaceChildren(figure);
}

export function modelNote() {
  const span = el('span', 'chart-note');
  const [before, after] = MODEL_NOTE.split('How we measure this');
  const link = el('a', null, 'How we measure this');
  link.href = '#method-title';
  span.append(before, link, after);
  return span;
}
