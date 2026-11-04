// ::compare: each metric's value this month against 3 months, 1 year and 5 years earlier.
import d3 from './d3.js';
import {
  addMonths, monthLabel, makeFormat, delta, tone, TONE_WORD, resolveSeries, valueAt, sourceLine,
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
  const w = 120;
  const h = 30;
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
  head.append(el('p', 'chart-sub', attrs.subtitle ?? `${monthLabel(until, 'long')} against ${windows.map((a) => `${WINDOW_LABEL[a]}`).join(', ').replace(/, ([^,]*)$/, ' and $1')} earlier. Changes marked better or worse are judged from the point of view of people looking for work.`));

  const table = el('table', 'compare-table');
  const hr = table.createTHead().insertRow();
  hr.append(el('th', 'c-measure', 'Measure'), el('th', 'c-now', monthLabel(until)));
  for (const a of windows) hr.append(el('th', 'c-delta', `vs ${monthLabel(addMonths(until, -WINDOWS[a]))}`));
  const body = table.createTBody();
  for (const s of series) {
    const now = valueAt(s, until);
    const thens = windows.map((a) => valueAt(s, addMonths(until, -WINDOWS[a])));
    const fmt = makeFormat(s.unit, [now, ...thens]);
    const tr = body.insertRow();
    const measure = el('th', 'c-measure');
    measure.scope = 'row';
    measure.append(el('span', 'm-label', s.label), sparkline(s, until, windows));
    const nowCell = el('td', 'c-now', fmt(now));
    nowCell.dataset.label = monthLabel(until);
    tr.append(measure, nowCell);
    windows.forEach((a, k) => {
      const d = delta(now, thens[k], s.unit);
      const td = el('td', 'c-delta');
      td.dataset.label = `vs ${WINDOW_LABEL[a]} ago`;
      if (!d) {
        td.append(el('span', 'd-none', 'No data'));
      } else {
        const t = tone(d.sign, s.polarity);
        const chip = el('span', `d d-${t}`);
        const arrow = el('span', 'd-arrow', d.sign > 0 ? '▲' : d.sign < 0 ? '▼' : '');
        arrow.setAttribute('aria-hidden', 'true');
        chip.append(arrow, d.text);
        // The word carries better/worse for readers who can't tell the colors apart.
        if (t !== 'flat') chip.append(el('span', 'd-word', TONE_WORD[t]));
        td.append(chip, el('span', 'd-was', `from ${fmt(thens[k])}`));
      }
      tr.append(td);
    });
  }
  const foot = el('p', 'chart-source', sourceLine(series));
  if (attrs.note) foot.append(' ', el('span', 'chart-note', attrs.note));
  figure.append(head, table, foot);
  mount.replaceChildren(figure);
}
