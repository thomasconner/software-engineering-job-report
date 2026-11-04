// ::compare — each metric's value this month against 3 months, 1 year and 5 years earlier.
import * as d3 from 'https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm';
import {
  addMonths, monthLabel, formatValue, delta, polarity, resolveSeries, valueAt, sourceLine,
  AGAINST_MONTHS, AGAINST_LABEL,
} from './data.js';

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

const TONE = { 1: 'good', '-1': 'bad', 0: 'flat' };

function sparkline(series, until, marks) {
  const start = addMonths(until, -AGAINST_MONTHS[marks.at(-1)] - 6);
  const pts = series.points.filter((p) => p.month >= start);
  const w = 120;
  const h = 30;
  const x = d3.scaleUtc().domain(d3.extent(pts, (p) => p.date)).range([3, w - 4]);
  const y = d3.scaleLinear().domain(d3.extent(pts, (p) => p.value)).range([h - 4, 4]);
  const svg = d3.create('svg').attr('class', 'spark').attr('width', w).attr('height', h).attr('viewBox', `0 0 ${w} ${h}`).attr('aria-hidden', 'true');
  svg.append('path').attr('d', d3.line().x((p) => x(p.date)).y((p) => y(p.value)).curve(d3.curveMonotoneX)(pts));
  for (const m of [...marks.map((a) => addMonths(until, -AGAINST_MONTHS[a])), until]) {
    const p = pts.find((q) => q.month === m);
    if (p) svg.append('circle').attr('class', m === until ? 'now' : 'then').attr('cx', x(p.date)).attr('cy', y(p.value)).attr('r', m === until ? 3.5 : 2.5);
  }
  return svg.node();
}

export function renderCompare(mount, attrs, data, until) {
  const against = (attrs.against ?? '3m,1y,5y').split(',').map((s) => s.trim()).filter((a) => AGAINST_MONTHS[a]);
  const series = resolveSeries(data, attrs, until);

  const figure = el('figure', 'compare');
  const head = el('figcaption', 'chart-head');
  head.append(el('h3', 'chart-title', attrs.title ?? `${monthLabel(until, 'long')} against the past`));
  head.append(el('p', 'chart-sub', attrs.subtitle ?? 'Green and red mark changes that are better or worse for people looking for work. Gray changes are neither.'));

  const table = el('table', 'compare-table');
  const hr = table.createTHead().insertRow();
  hr.append(el('th', 'c-measure', 'Measure'), el('th', 'c-now', monthLabel(until)));
  for (const a of against) {
    const th = el('th', 'c-delta', `vs ${AGAINST_LABEL[a]} ago`);
    th.title = monthLabel(addMonths(until, -AGAINST_MONTHS[a]));
    hr.append(th);
  }
  const body = table.createTBody();
  for (const s of series) {
    const now = valueAt(s, until);
    const tr = body.insertRow();
    const measure = el('th', 'c-measure');
    measure.scope = 'row';
    measure.append(el('span', 'm-label', s.label), sparkline(s, until, against));
    tr.append(measure, el('td', 'c-now', formatValue(now, s.unit)));
    for (const a of against) {
      const thenMonth = addMonths(until, -AGAINST_MONTHS[a]);
      const then = valueAt(s, thenMonth);
      const d = delta(now, then, s.unit);
      const td = el('td', 'c-delta');
      td.dataset.label = `vs ${AGAINST_LABEL[a]} ago`;
      if (!d) {
        td.append(el('span', 'd-none', 'No data'));
      } else {
        const tone = TONE[d.sign * polarity(s.key)];
        const chip = el('span', `d d-${tone}`);
        const arrow = el('span', 'd-arrow', d.sign > 0 ? '▲' : d.sign < 0 ? '▼' : '▬');
        arrow.setAttribute('aria-hidden', 'true');
        chip.append(arrow, d.text);
        if (tone !== 'flat') chip.append(el('span', 'sr-only', tone === 'good' ? ' (better for job seekers)' : ' (worse for job seekers)'));
        td.append(chip, el('span', 'd-was', `from ${formatValue(then, s.unit)}`));
      }
      tr.append(td);
    }
  }
  const foot = el('p', 'chart-source', sourceLine(series));
  if (attrs.note) foot.append(' ', el('span', 'chart-note', `Note: ${attrs.note}`));
  figure.append(head, table, foot);
  mount.replaceChildren(figure);
}
