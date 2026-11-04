// Directive renderers: line, bar, stacked-area, small-multiples, slope, dot.
import * as d3 from 'https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm';
import {
  addMonths, monthDate, monthLabel, formatValue, delta, tickFormat, resolveSeries, valueAt, sourceLine,
  AGAINST_MONTHS,
} from './data.js';

const MAX_COLORED = 6; // past this a stack folds its smallest categories into "Other"
const color = (i) => `var(--s${i + 1})`;
const DEEMPH = 'var(--deemph)';
const isPhone = (width) => width < 520;

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

export function renderChart(mount, attrs, data, until) {
  const type = attrs.type ?? 'line';
  const renderer = RENDERERS[type];
  if (!renderer) throw new Error(`Unknown chart type "${type}"`);
  const series = resolveSeries(data, attrs, until);
  const fig = figureShell(mount, attrs, series);
  renderer(fig, series, attrs, until);
}

// ---------- shared chrome ----------

function figureShell(mount, attrs, series) {
  const figure = el('figure', 'chart');
  const head = el('figcaption', 'chart-head');
  const single = series.length === 1;
  const sameSource = series.every((s) => s.description === series[0].description);
  const fallbackTitle = single ? series[0].label : sameSource ? series[0].description : series.map((s) => s.label).join(' and ');
  head.append(el('h3', 'chart-title', attrs.title ?? fallbackTitle));
  const sub = attrs.subtitle ?? (single ? series[0].description : subtitleFor(series));
  if (sub) head.append(el('p', 'chart-sub', sub));
  const controls = el('div', 'chart-controls');
  const legend = el('ul', 'legend');
  const presets = el('div', 'presets');
  controls.append(legend, presets);
  const plot = el('div', 'chart-plot');
  const foot = el('p', 'chart-source', sourceLine(series));
  if (attrs.note) foot.append(' ', el('span', 'chart-note', `Note: ${attrs.note}`));
  const table = el('details', 'chart-table');
  table.append(el('summary', null, 'Show the numbers'));
  figure.append(head, controls, plot, foot, table);
  mount.replaceChildren(figure);
  return { figure, legend, presets, plot, table };
}

function subtitleFor(series) {
  if (series[0].description && series.every((s) => s.description === series[0].description)) {
    return `${series[0].description}, as a share of hiring posts`;
  }
  return series.every((s) => s.unit === 'share') ? 'Share of hiring posts each month' : '';
}

// Width of a label as it will render, so label columns are sized to their text instead of guessed.
function textWidth(svg, strings, cls) {
  const t = svg.append('text').attr('class', cls).attr('visibility', 'hidden');
  const widest = d3.max(strings, (str) => t.text(str).node().getComputedTextLength()) ?? 0;
  t.remove();
  return Math.ceil(widest);
}

function setLegend(legend, items, mark = 'line') {
  legend.replaceChildren(...items.map(({ label, color: c }) => {
    const li = el('li');
    const key = el('span', `key key-${mark}`);
    key.style.setProperty('--key', c);
    li.append(key, document.createTextNode(label));
    return li;
  }));
}

function setTable(details, columns, rows) {
  // Built on first open: the "All" table for a 15-year series is a few hundred rows nobody needs until asked.
  details.addEventListener('toggle', () => {
    if (!details.open || details.querySelector('table')) return;
    const wrap = el('div', 'table-scroll');
    const table = el('table');
    const thead = table.createTHead().insertRow();
    for (const c of columns) thead.append(el('th', null, c));
    const tbody = table.createTBody();
    for (const r of rows) {
      const tr = tbody.insertRow();
      r.forEach((v, i) => tr.append(el(i === 0 ? 'th' : 'td', null, v)));
    }
    wrap.append(table);
    details.append(wrap);
  });
}

function seriesTable(details, series) {
  const months = [...new Set(series.flatMap((s) => s.points.map((p) => p.month)))].sort().reverse();
  setTable(details, ['Month', ...series.map((s) => s.label)],
    months.map((m) => [monthLabel(m), ...series.map((s) => formatValue(valueAt(s, m), s.unit))]));
}

function makeTooltip(plot) {
  const tip = el('div', 'tooltip');
  tip.setAttribute('role', 'status');
  tip.hidden = true;
  plot.append(tip);
  return {
    show(x, y, header, rows) {
      const h = el('div', 'tip-head', header);
      tip.replaceChildren(h, ...rows.map((r) => {
        const row = el('div', 'tip-row');
        if (r.color) {
          const key = el('span', 'key key-line');
          key.style.setProperty('--key', r.color);
          row.append(key);
        }
        row.append(el('strong', null, r.value), el('span', null, r.label ?? ''));
        return row;
      }));
      tip.hidden = false;
      const pw = plot.clientWidth;
      const tw = tip.offsetWidth;
      const left = x + 14 + tw > pw ? x - 14 - tw : x + 14;
      tip.style.left = `${Math.max(0, left)}px`;
      tip.style.top = `${y}px`;
    },
    hide() { tip.hidden = true; },
  };
}

// Re-render on width change only; height follows width.
function responsive(plot, draw) {
  let lastWidth = 0;
  const run = () => {
    const width = Math.floor(plot.clientWidth);
    if (width && width !== lastWidth) {
      lastWidth = width;
      draw(width);
    }
  };
  new ResizeObserver(() => requestAnimationFrame(run)).observe(plot);
  run();
  return () => { lastWidth = 0; run(); };
}

// Hover and arrow-key focus for charts made of discrete items (slope lines, dot rows, bars).
// The tooltip anchors to the item, so keyboard and pointer readers see the same thing in the same place.
function bindItems(svg, marks, items, pickIndex, describe, tooltip) {
  let idx = -1;
  const show = (i) => {
    idx = i;
    marks.classed('dim', (d) => d !== items[i]);
    const { x, y, header, rows } = describe(items[i]);
    tooltip.show(x, y, header, rows);
  };
  const hide = () => { marks.classed('dim', false); tooltip.hide(); };
  svg.on('pointermove', (ev) => {
    const i = pickIndex(...d3.pointer(ev));
    if (i == null || i < 0 || i >= items.length) hide();
    else show(i);
  }).on('pointerleave', hide).on('focus', () => show(Math.max(0, idx))).on('blur', hide)
    .on('keydown', (ev) => {
      const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[ev.key];
      if (step) {
        show((Math.max(0, idx) + step + items.length) % items.length);
        ev.preventDefault();
      } else if (ev.key === 'Escape') hide();
    });
}

function newSvg(plot, width, height, label) {
  plot.querySelector('svg')?.remove();
  return d3.select(plot).insert('svg', ':first-child')
    .attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`)
    .attr('role', 'img').attr('aria-label', label).attr('tabindex', 0);
}

function parseAnnotations(text) {
  if (!text) return [];
  return text.split(/[;|]/).map((s) => s.trim()).filter(Boolean)
    .map((s) => ({ month: s.slice(0, 7), label: s.slice(8).trim() }));
}

function yDomain(unit, values) {
  const max = d3.max(values) ?? 1;
  const min = d3.min(values) ?? 0;
  if (unit === 'score') return [0, 4];
  if (unit === 'share') return [0, Math.min(1, max * 1.08)];
  if (unit === 'usd') return [min * 0.85, max * 1.05];
  return [0, max * 1.08];
}

function rangePresets(container, first, until, initialFrom, onChange) {
  const options = [];
  if (initialFrom && initialFrom > first) {
    const label = initialFrom.endsWith('-01') ? initialFrom.slice(0, 4) : monthLabel(initialFrom);
    options.push({ label: `Since ${label}`, from: initialFrom });
  }
  for (const [label, n] of [['1Y', 12], ['5Y', 60]]) {
    const from = addMonths(until, -n + 1);
    if (from > first && !options.some((o) => o.from === from)) options.push({ label, from });
  }
  options.push({ label: 'All', from: first });
  const group = el('div', 'segmented');
  group.setAttribute('role', 'group');
  group.setAttribute('aria-label', 'Time range');
  const initial = initialFrom && initialFrom > first ? options[0] : options.at(-1);
  const buttons = options.map((o) => {
    const b = el('button', null, o.label);
    b.type = 'button';
    b.setAttribute('aria-pressed', String(o === initial));
    b.addEventListener('click', () => {
      buttons.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      onChange(o.from);
    });
    return b;
  });
  group.append(...buttons);
  container.replaceChildren(group);
  return initial.from;
}

function drawYAxis(g, y, width, unit, left) {
  const fmt = tickFormat(unit);
  const ticks = y.ticks(5);
  const grid = g.append('g').attr('class', 'grid');
  grid.selectAll('line').data(ticks).join('line')
    .attr('x1', left).attr('x2', width).attr('y1', (d) => y(d)).attr('y2', (d) => y(d))
    .attr('class', (d) => (d === 0 ? 'baseline' : null));
  grid.selectAll('text').data(ticks).join('text')
    .attr('x', left - 6).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('text-anchor', 'end').text(fmt);
}

function drawXAxis(g, x, y0, width, start, end) {
  const months = d3.utcMonth.count(start, end);
  const short = months <= 24;
  const maxTicks = Math.max(2, Math.floor(width / (short ? 80 : 60)));
  const every = short ? [1, 2, 3, 4, 6, 12].find((k) => months / k <= maxTicks) ?? 12 : Math.ceil(months / 12 / maxTicks);
  const ticks = x.ticks(short ? d3.utcMonth.every(every) : d3.utcYear.every(every));
  const fmt = d3.utcFormat(short ? '%b %Y' : '%Y');
  const axis = g.append('g').attr('class', 'xaxis');
  axis.selectAll('text').data(ticks).join('text')
    .attr('x', (d) => x(d)).attr('y', y0 + 18).attr('text-anchor', 'middle').text(fmt);
  axis.selectAll('line').data(ticks).join('line')
    .attr('x1', (d) => x(d)).attr('x2', (d) => x(d)).attr('y1', y0).attr('y2', y0 + 4);
}

// Annotation labels sit above the plot; a label that would run into the previous one drops to the next row.
function layoutAnnotations(annotations, x, start, end, right) {
  let lastRight = -Infinity;
  let row = 0;
  return annotations.filter((a) => monthDate(a.month) >= start && monthDate(a.month) <= end).map((a) => {
    const ax = x(monthDate(a.month));
    const estimate = a.label.length * 6.4;
    const anchorEnd = ax + estimate > right;
    row = (anchorEnd ? ax - estimate : ax) < lastRight + 8 ? row + 1 : 0;
    lastRight = anchorEnd ? ax : ax + estimate;
    return { ...a, ax, anchorEnd, row };
  });
}

function drawAnnotations(g, placed, top, bottom) {
  const rows = d3.max(placed, (p) => p.row) ?? 0;
  for (const p of placed) {
    const ty = top - 10 - (rows - p.row) * 14;
    const ag = g.append('g').attr('class', 'annotation');
    ag.append('line').attr('x1', p.ax).attr('x2', p.ax).attr('y1', ty + 4).attr('y2', bottom);
    ag.append('text').attr('x', p.anchorEnd ? p.ax - 4 : p.ax + 4).attr('y', ty)
      .attr('text-anchor', p.anchorEnd ? 'end' : 'start').text(p.label);
  }
}

// Break a line wherever a month is missing instead of drawing across the hole.
function withGaps(points) {
  const out = [];
  points.forEach((p, i) => {
    if (i && addMonths(points[i - 1].month, 1) !== p.month) out.push({ ...p, value: null });
    out.push(p);
  });
  return out;
}

function roundedBar(x, y, w, h, r, horizontal) {
  r = Math.min(r, horizontal ? h / 2 : w / 2, horizontal ? w : h);
  if (w <= 0 || h <= 0) return '';
  if (horizontal) {
    return `M${x},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${h - 2 * r}a${r},${r} 0 0 1 ${-r},${r}h${-(w - r)}Z`;
  }
  return `M${x},${y + h}v${-(h - r)}a${r},${r} 0 0 1 ${r},${-r}h${w - 2 * r}a${r},${r} 0 0 1 ${r},${r}v${h - r}Z`;
}

// ---------- time series: line, stacked-area, bar over time ----------

function foldForStack(series) {
  if (series.length <= MAX_COLORED) return series;
  const last = (s) => s.points.at(-1)?.value ?? 0;
  const ranked = [...series].sort((a, b) => last(b) - last(a));
  const keep = new Set(ranked.slice(0, MAX_COLORED - 1).map((s) => s.key));
  const kept = series.filter((s) => keep.has(s.key) && s.key !== 'other');
  const rest = series.filter((s) => !kept.includes(s));
  const byMonth = d3.rollup(rest.flatMap((s) => s.points), (v) => d3.sum(v, (p) => p.value), (p) => p.month);
  const other = {
    ...rest[0], key: 'other', label: 'Everything else', folded: true,
    points: kept[0].points.map((p) => ({ ...p, value: byMonth.get(p.month) ?? 0 })),
  };
  return [...kept, other];
}

function timeChart(fig, series, attrs, until, mode) {
  if (mode === 'area') series = foldForStack(series);
  const unit = series[0].unit;
  const highlight = attrs.highlight?.split(',').map((s) => s.trim());
  const colorOf = (s, i) => (s.folded ? DEEMPH : highlight && !highlight.includes(s.key) ? DEEMPH : color(i));
  const annotations = parseAnnotations(attrs.annotate);
  const first = d3.min(series, (s) => s.points[0]?.month);
  const tooltip = makeTooltip(fig.plot);

  if (series.length > 1) setLegend(fig.legend, series.map((s, i) => ({ label: s.label, color: colorOf(s, i) })), mode === 'line' ? 'line' : 'rect');
  seriesTable(fig.table, series);

  let from = rangePresets(fig.presets, first, until, attrs.from ?? (mode === 'bar' ? addMonths(until, -23) : null), (f) => {
    from = f;
    redraw();
  });

  const redraw = responsive(fig.plot, (width) => {
    const visible = series.map((s) => ({ ...s, points: s.points.filter((p) => p.month >= from) }));
    const months = [...new Set(visible.flatMap((s) => s.points.map((p) => p.month)))].sort();
    const phone = isPhone(width);
    const height = mode === 'bar' ? (phone ? 220 : 260) : phone ? 240 : 320;
    const directLabels = mode !== 'bar' && visible.length <= 4;
    const twoLine = visible.length > 1 && !phone;
    const start = monthDate(months[0]);
    const end = monthDate(months.at(-1));
    const svg = newSvg(fig.plot, width, height, `${series.map((s) => s.label).join(', ')}, ${monthLabel(months[0])} to ${monthLabel(months.at(-1))}`);
    const margin = { top: 16, bottom: 28, left: 40, right: 12 };
    const draft = layoutAnnotations(annotations, d3.scaleUtc().domain([start, end]).range([margin.left, width - 12]), start, end, width - 12);
    if (draft.length) margin.top = 30 + (d3.max(draft, (p) => p.row) + 1) * 14;
    const g = svg.append('g');

    let stacked;
    let values;
    if (mode === 'area') {
      const rows = months.map((m) => Object.fromEntries([['month', m], ...visible.map((s) => [s.key, valueAt(s, m) ?? 0])]));
      stacked = d3.stack().keys(visible.map((s) => s.key))(rows);
      values = [d3.max(stacked.at(-1), (d) => d[1])];
    } else {
      values = visible.flatMap((s) => s.points.map((p) => p.value));
    }
    const y = d3.scaleLinear().domain(mode === 'area' ? [0, Math.min(1, values[0])] : yDomain(unit, values)).nice()
      .range([height - margin.bottom, margin.top]);

    // End labels: value (and name, for several series) at the right edge. Lines that end too close together
    // lose their labels entirely rather than being nudged off their lines; the legend still names them.
    let endLabels = [];
    if (directLabels) {
      const labels = visible.map((s, i) => {
        const p = s.points.at(-1);
        const yv = mode === 'area' ? (stacked[i].at(-1)[0] + stacked[i].at(-1)[1]) / 2 : p.value;
        return { s, i, p, y: y(yv), text: formatValue(p.value, unit) };
      }).sort((a, b) => a.y - b.y);
      const bandHeight = (l) => Math.abs(y(stacked[l.i].at(-1)[0]) - y(stacked[l.i].at(-1)[1]));
      endLabels = mode === 'area'
        ? labels.filter((l) => bandHeight(l) >= (twoLine ? 30 : 14))
        : labels.some((l, k) => k && l.y - labels[k - 1].y < (twoLine ? 30 : 15)) ? [] : labels;
      const texts = endLabels.flatMap((l) => [l.text, ...(twoLine ? [l.s.label] : [])]);
      if (texts.length) margin.right = textWidth(svg, texts, 'end-label') + 14;
    }
    const x = d3.scaleUtc().domain([start, end]).range([margin.left, width - margin.right]);
    const band = d3.scaleBand().domain(months).range([margin.left, width - margin.right]).paddingInner(0.15);
    if (mode === 'bar') x.range([margin.left + band.bandwidth() / 2, width - margin.right - band.bandwidth() / 2]);

    drawYAxis(g, y, width - margin.right, unit, margin.left);
    drawXAxis(g, x, height - margin.bottom, width, start, end);

    const marks = g.append('g').attr('class', 'marks');
    if (mode === 'area') {
      marks.selectAll('path').data(stacked).join('path')
        .attr('class', (d, i) => (visible[i].folded ? 'band band-other' : 'band'))
        .attr('fill', (d, i) => colorOf(visible[i], i))
        .attr('d', d3.area().x((d) => x(monthDate(d.data.month))).y0((d) => y(d[0])).y1((d) => y(d[1])).curve(d3.curveMonotoneX));
    } else if (mode === 'bar') {
      const bw = Math.min(24, Math.max(1, band.bandwidth()));
      const pts = visible[0].points;
      marks.selectAll('path').data(pts).join('path')
        .attr('class', 'bar').attr('fill', color(0))
        .attr('d', (p) => roundedBar(band(p.month) + (band.bandwidth() - bw) / 2, y(p.value), bw, y(y.domain()[0]) - y(p.value), bw > 6 ? 4 : 0));
    } else {
      const line = d3.line().defined((p) => p.value != null).x((p) => x(p.date)).y((p) => y(p.value)).curve(d3.curveMonotoneX);
      if (visible.length === 1) {
        marks.append('path').attr('class', 'wash').attr('fill', color(0))
          .attr('d', d3.area().defined((p) => p.value != null).x((p) => x(p.date)).y0(y(y.domain()[0])).y1((p) => y(p.value)).curve(d3.curveMonotoneX)(withGaps(visible[0].points)));
      }
      // Draw de-emphasized series first so highlighted ones sit on top.
      const order = visible.map((s, i) => [s, i]).sort(([a, ai], [b, bi]) => (colorOf(a, ai) === DEEMPH) - (colorOf(b, bi) === DEEMPH)).reverse();
      for (const [s, i] of order) {
        marks.append('path').attr('class', 'line').attr('stroke', colorOf(s, i)).attr('d', line(withGaps(s.points)));
      }
    }

    drawAnnotations(g, layoutAnnotations(annotations, x, start, end, width - margin.right), margin.top, height - margin.bottom);

    if (endLabels.length) {
      const lg = g.append('g').attr('class', 'end-labels');
      for (const l of endLabels) {
        if (mode === 'line') {
          lg.append('circle').attr('class', 'end-dot').attr('cx', x(l.p.date)).attr('cy', l.y).attr('r', 4).attr('fill', colorOf(l.s, l.i));
        }
        const t = lg.append('text').attr('x', width - margin.right + 8).attr('y', l.y).attr('dy', twoLine ? '-0.1em' : '0.32em');
        t.append('tspan').attr('class', 'end-value').text(l.text);
        if (twoLine) t.append('tspan').attr('x', width - margin.right + 8).attr('dy', '1.15em').attr('class', 'end-name').text(l.s.label);
      }
    }

    // Hover / keyboard layer: the crosshair snaps to the nearest month.
    const cross = g.append('g').attr('class', 'crosshair').style('display', 'none');
    cross.append('line').attr('y1', margin.top).attr('y2', height - margin.bottom);
    const dots = cross.selectAll('circle').data(visible).join('circle').attr('r', 4)
      .attr('fill', (s, i) => colorOf(s, i));
    const show = (idx) => {
      const m = months[idx];
      const cx = x(monthDate(m));
      cross.style('display', null);
      cross.select('line').attr('x1', cx).attr('x2', cx);
      dots.attr('cx', cx).attr('cy', (s, i) => {
        const v = valueAt(s, m);
        if (v == null) return -99;
        return mode === 'area' ? y(stacked[i].find((d) => d.data.month === m)[1]) : y(v);
      });
      const rows = visible.map((s, i) => ({ color: colorOf(s, i), value: formatValue(valueAt(s, m), unit), label: visible.length > 1 ? s.label : '', v: valueAt(s, m) ?? -1 }));
      if (mode !== 'area') rows.sort((a, b) => b.v - a.v);
      // A post count is redundant beside a count metric, but tells the reader how solid a share or median is.
      const n = unit === 'count' ? null : visible[0].points.find((p) => p.month === m)?.n;
      if (mode === 'area') rows.reverse();
      tooltip.show(cx, margin.top, `${monthLabel(m, 'long')}${n ? `, ${n.toLocaleString('en-US')} posts` : ''}`, rows);
    };
    const hide = () => { cross.style('display', 'none'); tooltip.hide(); };
    let idx = months.length - 1;
    g.append('rect').attr('class', 'hit')
      .attr('x', margin.left).attr('y', margin.top).attr('width', width - margin.left - margin.right).attr('height', height - margin.top - margin.bottom)
      .on('pointermove', (ev) => {
        const [px] = d3.pointer(ev);
        const date = x.invert(px);
        idx = d3.minIndex(months, (m) => Math.abs(monthDate(m) - date));
        show(idx);
      })
      .on('pointerleave', hide);
    svg.on('focus', () => show(idx)).on('blur', hide).on('keydown', (ev) => {
      if (ev.key === 'ArrowLeft' || ev.key === 'ArrowRight') {
        idx = Math.max(0, Math.min(months.length - 1, idx + (ev.key === 'ArrowLeft' ? -1 : 1)));
        show(idx);
        ev.preventDefault();
      } else if (ev.key === 'Escape') hide();
    });
  });
}

// ---------- small multiples: one panel per series, shared scales, synced crosshair ----------

function smallMultiples(fig, series, attrs, until) {
  const unit = series[0].unit;
  const sharedY = new Set(series.map((s) => s.unit)).size === 1;
  const first = d3.min(series, (s) => s.points[0]?.month);
  const annotations = parseAnnotations(attrs.annotate);
  seriesTable(fig.table, series);
  const grid = el('div', 'multiples');
  fig.plot.append(grid);
  const tooltip = makeTooltip(fig.plot);

  let from = rangePresets(fig.presets, first, until, attrs.from, (f) => { from = f; redraw(); });
  const redraw = responsive(fig.plot, (width) => {
    const cols = width < 420 ? 2 : width < 640 ? 3 : 4;
    const gap = 16;
    const pw = Math.floor((width - gap * (cols - 1)) / cols);
    const ph = 110;
    const visible = series.map((s) => ({ ...s, points: s.points.filter((p) => p.month >= from) }));
    const months = [...new Set(visible.flatMap((s) => s.points.map((p) => p.month)))].sort();
    const start = monthDate(months[0]);
    const end = monthDate(months.at(-1));
    const x = d3.scaleUtc().domain([start, end]).range([4, pw - 4]);
    const all = visible.flatMap((s) => s.points.map((p) => p.value));
    const scaleFor = (s) => d3.scaleLinear().domain(yDomain(s.unit, sharedY ? all : s.points.map((p) => p.value))).nice().range([ph - 18, 6]);
    const line = (y) => d3.line().defined((p) => p.value != null).x((p) => x(p.date)).y((p) => y(p.value)).curve(d3.curveMonotoneX);
    const yearFmt = d3.utcFormat('%Y');

    const panels = visible.map((s) => {
      const y = scaleFor(s);
      const panel = el('div', 'panel');
      const head = el('div', 'panel-head');
      const name = el('span', 'panel-name', s.label);
      const val = el('span', 'panel-value', formatValue(s.points.at(-1)?.value, s.unit));
      head.append(name, val);
      panel.append(head);
      const svg = d3.select(panel).append('svg').attr('width', pw).attr('height', ph).attr('viewBox', `0 0 ${pw} ${ph}`)
        .attr('role', 'img').attr('aria-label', `${s.label}: ${formatValue(s.points[0]?.value, s.unit)} in ${monthLabel(months[0])}, ${formatValue(s.points.at(-1)?.value, s.unit)} in ${monthLabel(months.at(-1))}`);
      const ticks = y.ticks(3);
      svg.append('g').attr('class', 'grid').selectAll('line').data(ticks).join('line')
        .attr('x1', 0).attr('x2', pw).attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).attr('class', (d) => (d === 0 ? 'baseline' : null));
      for (const a of annotations) {
        const d = monthDate(a.month);
        if (d >= start && d <= end) svg.append('line').attr('class', 'annotation-line').attr('x1', x(d)).attr('x2', x(d)).attr('y1', 8).attr('y2', ph - 18);
      }
      svg.append('path').attr('class', 'wash').attr('fill', color(0))
        .attr('d', d3.area().defined((p) => p.value != null).x((p) => x(p.date)).y0(y(y.domain()[0])).y1((p) => y(p.value)).curve(d3.curveMonotoneX)(withGaps(s.points)));
      svg.append('path').attr('class', 'line').attr('stroke', color(0)).attr('d', line(y)(withGaps(s.points)));
      // Tick labels go on top of the line (with a paper halo); the topmost is skipped so it never crowds the panel title.
      svg.append('g').attr('class', 'grid').selectAll('text').data(ticks.filter((d) => d !== 0 && y(d) > 18)).join('text')
        .attr('x', 0).attr('y', (d) => y(d) - 3).text(tickFormat(s.unit));
      const ax = svg.append('g').attr('class', 'xaxis');
      ax.append('text').attr('x', 4).attr('y', ph - 4).text(yearFmt(start));
      ax.append('text').attr('x', pw - 4).attr('y', ph - 4).attr('text-anchor', 'end').text(yearFmt(end));
      const cross = svg.append('g').attr('class', 'crosshair').style('display', 'none');
      cross.append('line').attr('y1', 8).attr('y2', ph - 18);
      cross.append('circle').attr('r', 4).attr('fill', color(0));
      return { s, y, svg, cross, val, panel };
    });
    grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
    grid.replaceChildren(...panels.map((p) => p.panel));

    const show = (m, hovered) => {
      const cx = x(monthDate(m));
      for (const p of panels) {
        const v = valueAt(p.s, m);
        p.val.textContent = formatValue(v, p.s.unit);
        p.cross.style('display', v == null ? 'none' : null);
        p.cross.select('line').attr('x1', cx).attr('x2', cx);
        p.cross.select('circle').attr('cx', cx).attr('cy', v == null ? -99 : p.y(v));
      }
      if (hovered) {
        const v = valueAt(hovered.s, m);
        const box = hovered.panel.getBoundingClientRect();
        const host = fig.plot.getBoundingClientRect();
        tooltip.show(box.left - host.left + cx, box.top - host.top + 24, monthLabel(m, 'long'), [{ color: color(0), value: formatValue(v, hovered.s.unit), label: hovered.s.label }]);
      }
    };
    const reset = () => {
      tooltip.hide();
      for (const p of panels) {
        p.cross.style('display', 'none');
        p.val.textContent = formatValue(p.s.points.at(-1)?.value, p.s.unit);
      }
    };
    for (const p of panels) {
      p.svg.on('pointermove', (ev) => {
        const date = x.invert(d3.pointer(ev)[0]);
        show(months[d3.minIndex(months, (m) => Math.abs(monthDate(m) - date))], p);
      }).on('pointerleave', reset);
    }
    let idx = months.length - 1;
    grid.tabIndex = 0;
    grid.setAttribute('aria-label', `${series.length} small charts. Use the arrow keys to move through months.`);
    grid.onkeydown = (ev) => {
      if (ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight') return;
      idx = Math.max(0, Math.min(months.length - 1, idx + (ev.key === 'ArrowLeft' ? -1 : 1)));
      show(months[idx]);
      ev.preventDefault();
    };
    grid.onblur = reset;
  });
}

// ---------- two-month comparisons: slope and dot ----------

function comparisonMonths(attrs, until, defaultAgainst) {
  const to = attrs.to ?? until;
  const from = attrs.from ?? addMonths(to, -AGAINST_MONTHS[attrs.against ?? defaultAgainst]);
  return { from, to };
}

function comparisonRows(series, from, to) {
  return series.map((s, i) => {
    const a = valueAt(s, from);
    const b = valueAt(s, to);
    return { s, i, a, b, d: delta(b, a, s.unit) };
  }).filter((r) => r.a != null && r.b != null);
}

function comparisonTable(details, rows, from, to) {
  setTable(details, ['', monthLabel(from), monthLabel(to), 'Change'],
    rows.map((r) => [r.s.label, formatValue(r.a, r.s.unit), formatValue(r.b, r.s.unit), r.d?.text ?? 'n/a']));
}

function dodge(items, minGap, lo, hi) {
  items.sort((a, b) => a.y - b.y);
  for (let k = 1; k < items.length; k++) items[k].y = Math.max(items[k].y, items[k - 1].y + minGap);
  const overflow = items.at(-1).y - hi;
  if (overflow > 0) for (const it of items) it.y -= overflow;
  for (let k = items.length - 2; k >= 0; k--) items[k].y = Math.min(items[k].y, items[k + 1].y - minGap);
  if (items[0].y < lo) {
    const shift = lo - items[0].y;
    for (const it of items) it.y += shift;
  }
  return items;
}

function slopeChart(fig, series, attrs, until) {
  const { from, to } = comparisonMonths(attrs, until, '5y');
  const rows = comparisonRows(series, from, to);
  const unit = series[0].unit;
  const highlight = attrs.highlight?.split(',').map((s) => s.trim())
    ?? [d3.greatest(rows, (r) => Math.abs(r.b - r.a))?.s.key];
  const colorOf = (r) => (highlight.includes(r.s.key) ? color(highlight.indexOf(r.s.key)) : DEEMPH);
  comparisonTable(fig.table, rows, from, to);
  setLegend(fig.legend, rows.filter((r) => highlight.includes(r.s.key)).map((r) => ({ label: r.s.label, color: colorOf(r) })));
  const tooltip = makeTooltip(fig.plot);

  responsive(fig.plot, (width) => {
    const phone = isPhone(width);
    const height = Math.max(240, rows.length * 22 + 70);
    const svg = newSvg(fig.plot, width, height, `${series[0].description}: ${monthLabel(from)} compared with ${monthLabel(to)}`);
    const leftText = rows.map((r) => (phone ? formatValue(r.a, unit) : `${r.s.label} ${formatValue(r.a, unit)}`));
    const rightText = rows.map((r) => `${formatValue(r.b, unit)} ${r.s.label}`);
    const m = {
      top: 34, bottom: 16,
      left: Math.max(36, textWidth(svg, leftText, 'slope-label') + 14),
      right: Math.max(36, textWidth(svg, rightText, 'slope-label') + 14),
    };
    const y = d3.scaleLinear().domain(yDomain(unit, rows.flatMap((r) => [r.a, r.b]))).range([height - m.bottom, m.top]);
    const x0 = m.left;
    const x1 = width - m.right;
    const g = svg.append('g');
    g.append('text').attr('class', 'col-head').attr('x', x0).attr('y', 14).attr('text-anchor', 'middle').text(monthLabel(from));
    g.append('text').attr('class', 'col-head').attr('x', x1).attr('y', 14).attr('text-anchor', 'middle').text(monthLabel(to));
    g.append('line').attr('class', 'axis-rule').attr('x1', x0).attr('x2', x0).attr('y1', m.top - 8).attr('y2', height - m.bottom);
    g.append('line').attr('class', 'axis-rule').attr('x1', x1).attr('x2', x1).attr('y1', m.top - 8).attr('y2', height - m.bottom);

    const ordered = [...rows].sort((a, b) => (colorOf(a) === DEEMPH) - (colorOf(b) === DEEMPH)).reverse();
    const lines = g.append('g').selectAll('g').data(ordered).join('g').attr('class', 'slope');
    lines.append('line').attr('x1', x0).attr('x2', x1).attr('y1', (r) => y(r.a)).attr('y2', (r) => y(r.b)).attr('stroke', colorOf);
    lines.append('circle').attr('cx', x0).attr('cy', (r) => y(r.a)).attr('r', 4).attr('fill', colorOf);
    lines.append('circle').attr('cx', x1).attr('cy', (r) => y(r.b)).attr('r', 4).attr('fill', colorOf);

    const left = dodge(rows.map((r) => ({ r, y: y(r.a) })), 15, m.top, height - m.bottom);
    const right = dodge(rows.map((r) => ({ r, y: y(r.b) })), 15, m.top, height - m.bottom);
    g.append('g').attr('class', 'slope-labels').selectAll('text').data(left).join('text')
      .attr('x', x0 - 10).attr('y', (d) => d.y).attr('dy', '0.32em').attr('text-anchor', 'end')
      .attr('class', (d) => (colorOf(d.r) === DEEMPH ? 'muted' : null))
      .text((d) => (phone ? formatValue(d.r.a, unit) : `${d.r.s.label} ${formatValue(d.r.a, unit)}`));
    g.append('g').attr('class', 'slope-labels').selectAll('text').data(right).join('text')
      .attr('x', x1 + 10).attr('y', (d) => d.y).attr('dy', '0.32em')
      .attr('class', (d) => (colorOf(d.r) === DEEMPH ? 'muted' : null))
      .text((d) => `${formatValue(d.r.b, unit)} ${d.r.s.label}`);

    const yAt = (r, px) => {
      const t = Math.max(0, Math.min(1, (px - x0) / (x1 - x0)));
      return y(r.a) + (y(r.b) - y(r.a)) * t;
    };
    bindItems(svg, lines, rows, (px, py) => {
      if (px < x0 - 24 || px > x1 + 24) return null;
      const i = d3.minIndex(rows, (r) => Math.abs(yAt(r, px) - py));
      return Math.abs(yAt(rows[i], px) - py) < 24 ? i : null;
    }, (r) => ({
      x: (x0 + x1) / 2, y: (y(r.a) + y(r.b)) / 2 + 12, header: r.s.label,
      rows: [
        { value: formatValue(r.a, unit), label: monthLabel(from) },
        { value: formatValue(r.b, unit), label: monthLabel(to) },
        { value: r.d?.text ?? 'n/a', label: 'change' },
      ],
    }), tooltip);
  });
}

function dotChart(fig, series, attrs, until) {
  const { from, to } = comparisonMonths(attrs, until, '1y');
  const rows = comparisonRows(series, from, to).sort((a, b) => b.b - a.b);
  const unit = series[0].unit;
  comparisonTable(fig.table, rows, from, to);
  setLegend(fig.legend, [
    { label: monthLabel(to), color: color(0) },
    { label: monthLabel(from), color: 'var(--then)' },
  ], 'dot');
  const tooltip = makeTooltip(fig.plot);

  responsive(fig.plot, (width) => {
    const phone = isPhone(width);
    const rowH = 30;
    const height = rows.length * rowH + 8 + 26;
    const svg = newSvg(fig.plot, width, height, `${series[0].description}: ${monthLabel(to)} compared with ${monthLabel(from)}`);
    const m = {
      top: 8, bottom: 26,
      left: textWidth(svg, rows.map((r) => r.s.label), 'row-label') + 16,
      right: textWidth(svg, rows.map((r) => `${formatValue(r.b, unit)} ${r.d?.text ?? ''}`), 'row-value') + (phone ? 16 : 24),
    };
    const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => Math.max(r.a, r.b)) * 1.05]).nice().range([m.left, width - m.right]);
    const g = svg.append('g');
    const ticks = x.ticks(phone ? 3 : 5);
    const grid = g.append('g').attr('class', 'grid');
    grid.selectAll('line').data(ticks).join('line').attr('x1', (d) => x(d)).attr('x2', (d) => x(d)).attr('y1', m.top).attr('y2', height - m.bottom)
      .attr('class', (d) => (d === 0 ? 'baseline' : null));
    grid.selectAll('text').data(ticks).join('text').attr('x', (d) => x(d)).attr('y', height - 8).attr('text-anchor', 'middle').text(tickFormat(unit));

    const row = g.append('g').selectAll('g').data(rows).join('g').attr('class', 'dot-row')
      .attr('transform', (r, k) => `translate(0,${m.top + k * rowH + rowH / 2})`);
    row.append('text').attr('class', 'row-label').attr('x', m.left - 12).attr('dy', '0.32em').attr('text-anchor', 'end').text((r) => r.s.label);
    row.append('line').attr('class', 'connector').attr('x1', (r) => x(r.a)).attr('x2', (r) => x(r.b));
    row.append('circle').attr('class', 'then-dot').attr('cx', (r) => x(r.a)).attr('r', 5);
    row.append('circle').attr('class', 'now-dot').attr('cx', (r) => x(r.b)).attr('r', 5).attr('fill', color(0));
    const val = row.append('text').attr('class', 'row-value').attr('x', width - m.right + 12).attr('dy', '0.32em');
    val.append('tspan').text((r) => formatValue(r.b, unit));
    val.append('tspan').attr('class', 'muted').attr('dx', 6).text((r) => r.d?.text ?? '');

    bindItems(svg, row, rows, (px, py) => Math.floor((py - m.top) / rowH), (r) => ({
      x: x(Math.max(r.a, r.b)), y: m.top + rows.indexOf(r) * rowH + rowH, header: r.s.label,
      rows: [
        { color: color(0), value: formatValue(r.b, unit), label: monthLabel(to) },
        { color: 'var(--then)', value: formatValue(r.a, unit), label: monthLabel(from) },
        { value: r.d?.text ?? 'n/a', label: 'change' },
      ],
    }), tooltip);
  });
}

// Horizontal bars for a breakdown at one month; with a scalar metric, falls back to monthly columns.
function barChart(fig, series, attrs, until) {
  if (!attrs.breakdown) return timeChart(fig, series, attrs, until, 'bar');
  const month = attrs.to ?? until;
  const rows = series.map((s) => ({ s, v: valueAt(s, month) })).filter((r) => r.v != null).sort((a, b) => b.v - a.v);
  setTable(fig.table, ['', monthLabel(month)], rows.map((r) => [r.s.label, formatValue(r.v, 'share')]));
  const tooltip = makeTooltip(fig.plot);
  responsive(fig.plot, (width) => {
    const rowH = 30;
    const height = rows.length * rowH + 8;
    const svg = newSvg(fig.plot, width, height, `${series[0].description} in ${monthLabel(month)}`);
    const m = { top: 4, bottom: 4, left: textWidth(svg, rows.map((r) => r.s.label), 'row-label') + 16, right: 52 };
    const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.v)]).range([m.left, width - m.right]);
    const row = svg.append('g').selectAll('g').data(rows).join('g').attr('class', 'dot-row')
      .attr('transform', (r, k) => `translate(0,${m.top + k * rowH})`);
    row.append('text').attr('class', 'row-label').attr('x', m.left - 12).attr('y', rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'end').text((r) => r.s.label);
    row.append('path').attr('class', 'bar').attr('fill', color(0)).attr('d', (r) => roundedBar(m.left, (rowH - 16) / 2, x(r.v) - m.left, 16, 4, true));
    row.append('text').attr('class', 'row-value').attr('x', (r) => x(r.v) + 6).attr('y', rowH / 2).attr('dy', '0.32em').text((r) => formatValue(r.v, 'share'));
    svg.append('line').attr('class', 'axis-rule').attr('x1', m.left).attr('x2', m.left).attr('y1', 0).attr('y2', height);
    bindItems(svg, row, rows, (px, py) => Math.floor((py - m.top) / rowH), (r) => ({
      x: x(r.v), y: m.top + rows.indexOf(r) * rowH + rowH, header: r.s.label,
      rows: [{ value: formatValue(r.v, 'share'), label: monthLabel(month) }],
    }), tooltip);
  });
}

const RENDERERS = {
  line: (fig, s, a, u) => timeChart(fig, s, a, u, 'line'),
  'stacked-area': (fig, s, a, u) => timeChart(fig, s, a, u, 'area'),
  bar: barChart,
  'small-multiples': smallMultiples,
  slope: slopeChart,
  dot: dotChart,
};

