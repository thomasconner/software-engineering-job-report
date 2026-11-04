// Directive renderers: line, bar, stacked-area, small-multiples, slope, dot.
import d3 from './d3.js';
import {
  AuthoringError, WINDOWS, addMonths, monthDate, monthLabel, makeFormat, change, needsModelNote, tickFormat,
  resolveSeries, pointAt, valueAt, sourceLine, pastMonth, isCatchAll, resolveExternal, indexTo, periodLabel,
} from './data.js';
import { modelNote } from './compare.js';

const MAX_BANDS = 6; // a stack keeps its five largest categories and folds the rest into "Everything else"
const MARKER_LIMIT = 36; // fewer points than this get a dot on every month
const color = (i) => `var(--s${i + 1})`;
const DEEMPH = 'var(--deemph)';
const isPhone = (width) => width < 520;
const list = (s) => s?.split(',').map((x) => x.trim()).filter(Boolean);
let uid = 0;

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

export function renderChart(mount, attrs, data, until) {
  let series = resolveSeries(data, attrs, until);
  if (attrs.external) {
    if (attrs.base > until) throw new AuthoringError(`base="${attrs.base}" is after ${monthLabel(until)}`);
    series = [...series, resolveExternal(data, attrs.external, until)].map((s) => indexTo(s, attrs.base));
  }
  if (!series.some((s) => s.points.length)) throw new AuthoringError(`No data up to ${monthLabel(until)}`);
  const fig = figureShell(mount, attrs, series);
  RENDERERS[attrs.type](fig, series, attrs, until, data);
}

// ---------- shared chrome ----------

// What the chart is about, for the default subtitle: the metric label, the breakdown label, or several labels.
function subjectOf(series) {
  const groups = [...new Set(series.map((s) => s.group))];
  // Benchmark labels start with a publisher's name ("Indeed …"), which keeps its capital.
  const proper = new Set(series.filter((s) => s.external).map((s) => s.group));
  // "Hiring posts removed and seeker posts removed", but leave acronyms like REMOTE alone.
  const midSentence = (g) => (/^[A-Z][a-z]/.test(g) && !proper.has(g) ? g[0].toLowerCase() + g.slice(1) : g);
  return groups.map((g, i) => (i ? midSentence(g) : g)).join(' and ');
}

function figureShell(mount, attrs, series) {
  const id = `chart-${++uid}`;
  const figure = el('figure', `chart chart-${attrs.type}`);
  const head = el('figcaption', 'chart-head');
  const title = el('h3', 'chart-title', attrs.title);
  title.id = `${id}-title`;
  const sub = el('p', 'chart-sub', attrs.subtitle ?? '');
  sub.id = `${id}-sub`;
  head.append(title, sub);
  const legend = el('ul', 'legend');
  legend.hidden = true;
  const plot = el('div', 'chart-plot');
  const summary = el('p', 'sr-only');
  summary.id = `${id}-summary`;
  const live = el('p', 'sr-only');
  live.setAttribute('aria-live', 'polite');

  const foot = el('div', 'chart-foot');
  const presets = el('div', 'presets');
  const source = el('p', 'chart-source', sourceLine(series));
  if (needsModelNote(series, attrs.note)) source.append(' ', modelNote());
  if (series.some((s) => s.confidence === 'rough')) source.append(' ', el('span', 'chart-note', 'A rough measure: read it as a broad picture.'));
  if (attrs.note) source.append(' ', el('span', 'chart-note', attrs.note));
  // Outside benchmarks are credited by name and license, with what this report changed (CC BY asks for both).
  for (const s of series.filter((x) => x.credit)) {
    const credit = el('span', 'chart-credit', 'Benchmark: ');
    const link = (text, href) => {
      const a = el('a', null, text);
      a.href = href;
      return a;
    };
    credit.append(link(s.credit, s.url));
    if (s.license) credit.append(' (', s.licenseUrl ? link(s.license, s.licenseUrl) : s.license, ')');
    const changes = [attrs.base && `indexed to ${monthLabel(attrs.base)} = 100`, s.smoothed && '12-month average']
      .filter(Boolean).join(', ');
    credit.append(changes ? `; ${changes} by this report.` : '.');
    source.append(' ', credit);
  }
  const toggle = el('button', 'table-toggle', 'Show the numbers');
  toggle.type = 'button';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-controls', `${id}-table`);
  foot.append(presets, source, toggle);
  const tableBox = el('div', 'chart-table');
  tableBox.id = `${id}-table`;
  tableBox.hidden = true;

  figure.append(head, legend, plot, summary, live, foot, tableBox);
  mount.replaceChildren(figure);

  let buildTable = () => ({ columns: [], rows: [] });
  // Built on first open: the full table for a 15-year series is a few hundred rows nobody needs until asked.
  toggle.addEventListener('click', () => {
    const open = tableBox.hidden;
    tableBox.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    toggle.textContent = open ? 'Hide the numbers' : 'Show the numbers';
    if (open && !tableBox.firstChild) tableBox.append(renderTable(buildTable()));
  });

  return {
    figure, legend, plot, presets, ids: { title: title.id, sub: sub.id, summary: summary.id },
    setSubtitle(text) { if (!attrs.subtitle) sub.textContent = text; },
    setSummary(text) { summary.textContent = text; },
    announce(text) { live.textContent = text; },
    table(fn) { buildTable = fn; tableBox.replaceChildren(); },
    empty(message) {
      plot.replaceChildren(el('p', 'chart-empty', message));
    },
  };
}

function renderTable({ columns, rows }) {
  const wrap = el('div', 'table-scroll');
  const table = el('table');
  const head = table.createTHead().insertRow();
  for (const c of columns) head.append(el('th', null, c));
  const body = table.createTBody();
  for (const r of rows) {
    const tr = body.insertRow();
    r.forEach((v, i) => tr.append(el(i === 0 ? 'th' : 'td', null, v)));
  }
  wrap.append(table);
  return wrap;
}

function seriesTable(fig, series, fmt) {
  fig.table(() => {
    const months = [...new Set(series.flatMap((s) => s.points.map((p) => p.month)))].sort().reverse();
    return {
      columns: ['Month', ...series.map((s) => s.label), 'Posts'],
      rows: months.map((m) => [
        monthLabel(m), ...series.map((s) => fmt(valueAt(s, m))),
        (pointAt(series[0], m)?.n ?? '').toLocaleString('en-US'),
      ]),
    };
  });
}

function setLegend(legend, items, mark) {
  legend.hidden = !items.length;
  legend.replaceChildren(...items.map(({ label, color: c }) => {
    const li = el('li');
    const key = el('span', `key key-${mark}`);
    key.style.setProperty('--key', c);
    li.append(key, document.createTextNode(label));
    return li;
  }));
}

// Width of a label as it will render, so label columns are sized to their text instead of guessed.
function textWidth(svg, strings, cls) {
  const t = svg.append('text').attr('class', cls).attr('visibility', 'hidden');
  const widest = d3.max(strings, (str) => t.text(str).node().getComputedTextLength()) ?? 0;
  t.remove();
  return Math.ceil(widest);
}

function makeTooltip(plot) {
  const tip = el('div', 'tooltip');
  // Screen readers get the keyboard announcements instead; a tooltip chasing the mouse would be noise.
  tip.setAttribute('aria-hidden', 'true');
  tip.hidden = true;
  plot.append(tip);
  return {
    show(x, y, header, rows, foot) {
      tip.replaceChildren(el('div', 'tip-head', header), ...rows.map((r) => {
        const row = el('div', 'tip-row');
        if (r.color) {
          const key = el('span', 'key key-line');
          key.style.setProperty('--key', r.color);
          row.append(key);
        }
        row.append(el('strong', r.tone ? `d-${r.tone}` : null, r.value), el('span', null, r.label ?? ''));
        return row;
      }), ...(foot ? [el('div', 'tip-foot', foot)] : []));
      tip.hidden = false;
      const left = x + 14 + tip.offsetWidth > plot.clientWidth ? x - 14 - tip.offsetWidth : x + 14;
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

function newSvg(fig, width, height) {
  fig.plot.querySelector('svg, .chart-empty')?.remove();
  return d3.select(fig.plot).insert('svg', ':first-child')
    .attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`)
    .attr('role', 'img').attr('tabindex', 0)
    .attr('aria-labelledby', `${fig.ids.title} ${fig.ids.sub}`).attr('aria-describedby', fig.ids.summary);
}

// Spread labels so none sit closer than `gap`, staying inside [lo, hi]. Items keep their order.
function dodge(items, gap, lo, hi) {
  items.sort((a, b) => a.y - b.y);
  for (const it of items) it.ty = it.y;
  for (let k = 1; k < items.length; k++) items[k].ty = Math.max(items[k].ty, items[k - 1].ty + gap);
  const overflow = (items.at(-1)?.ty ?? 0) - hi;
  if (overflow > 0) for (const it of items) it.ty -= overflow;
  for (let k = items.length - 2; k >= 0; k--) items[k].ty = Math.min(items[k].ty, items[k + 1].ty - gap);
  if (items.length && items[0].ty < lo) {
    const shift = lo - items[0].ty;
    for (const it of items) it.ty += shift;
  }
  return items;
}

function rangePresets(container, first, to, initialFrom, onChange) {
  const options = [];
  if (initialFrom && initialFrom > first) {
    options.push({ label: `Since ${initialFrom.endsWith('-01') ? initialFrom.slice(0, 4) : monthLabel(initialFrom)}`, from: initialFrom });
  }
  for (const [label, n] of [['1Y', 12], ['5Y', 60]]) {
    const from = addMonths(to, -n);
    if (from > first && !options.some((o) => o.from === from)) options.push({ label, from });
  }
  options.push({ label: 'All', from: first });
  const initial = initialFrom && initialFrom > first ? options[0] : options.at(-1);
  const group = el('div', 'segmented');
  group.setAttribute('role', 'group');
  group.setAttribute('aria-label', 'Time range');
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

function drawYAxis(g, y, x0, x1, unit) {
  const fmt = tickFormat(unit);
  const ticks = y.ticks(5);
  const grid = g.append('g').attr('class', 'grid');
  grid.selectAll('line').data(ticks).join('line')
    .attr('x1', x0).attr('x2', x1).attr('y1', (d) => y(d)).attr('y2', (d) => y(d))
    .attr('class', (d) => (d === 0 || (unit === 'index' && d === 100) ? 'baseline' : null));
  grid.selectAll('text').data(ticks).join('text')
    .attr('x', x0 - 6).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('text-anchor', 'end').text(fmt);
}

function drawXAxis(g, x, y0, width, start, end) {
  const months = d3.utcMonth.count(start, end);
  const short = months <= 24;
  const maxTicks = Math.max(2, Math.floor(width / (short ? 80 : 60)));
  const every = short ? [1, 2, 3, 4, 6, 12].find((k) => months / k <= maxTicks) ?? 12 : Math.ceil(months / 12 / maxTicks);
  const ticks = x.ticks(short ? d3.utcMonth.every(every) : d3.utcYear.every(every));
  const axis = g.append('g').attr('class', 'xaxis');
  axis.selectAll('text').data(ticks).join('text')
    .attr('x', (d) => x(d)).attr('y', y0 + 18).attr('text-anchor', 'middle').text(d3.utcFormat(short ? '%b %Y' : '%Y'));
  axis.selectAll('line').data(ticks).join('line')
    .attr('x1', (d) => x(d)).attr('x2', (d) => x(d)).attr('y1', y0).attr('y2', y0 + 4);
}

function parseAnnotations(text) {
  return (text ?? '').split(';').map((s) => s.trim()).filter(Boolean)
    .map((s) => ({ month: s.slice(0, 7), label: s.slice(8).trim() }));
}

// Annotation labels sit in rows above the plot, each beside its own rule. A label may not cross another
// annotation's rule, so the rule it would cross starts on a lower row; when that can't be arranged the label is
// shortened instead. Row 0 is the top row.
function layoutAnnotations(annotations, x, start, end, left, right, measure) {
  const inRange = annotations.filter((a) => monthDate(a.month) >= start && monthDate(a.month) <= end);
  const rules = inRange.map((a) => x(monthDate(a.month)));
  const items = inRange.map((a, k) => {
    const ax = rules[k];
    const w = measure(a.label);
    // Each label goes on whichever side of its rule fits and crosses fewer other rules; right side on a tie.
    const sides = [
      { anchorEnd: false, span: [ax, ax + 4 + w], fits: ax + 4 + w <= right },
      { anchorEnd: true, span: [ax - 4 - w, ax], fits: ax - 4 - w >= left - 8 },
    ].map((o) => ({ ...o, crossed: rules.filter((r, j) => j !== k && r > o.span[0] - 3 && r < o.span[1] + 3).length }));
    const usable = sides.filter((o) => o.fits);
    const side = (usable.length ? usable : sides).sort((a1, b1) => a1.crossed - b1.crossed)[0];
    return { ...a, text: a.label, ax, anchorEnd: side.anchorEnd, span: side.span, row: 0 };
  });
  const crosses = (a, b) => b.ax > a.span[0] - 3 && b.ax < a.span[1] + 3;
  for (let pass = 0; pass <= items.length; pass++) {
    let moved = false;
    for (const a of items) {
      for (const b of items) {
        if (a === b) continue;
        const clash = crosses(a, b) || (a.row === b.row && a.span[0] < b.span[1] + 6 && b.span[0] < a.span[1] + 6 && a.ax < b.ax);
        if (clash && b.row <= a.row && !crosses(b, a)) {
          b.row = a.row + 1;
          moved = true;
        }
      }
    }
    if (!moved) break;
  }
  // Two labels that each cross the other's rule: shorten the one on the left to stop before the next rule.
  for (const a of items) {
    const blocker = items.find((b) => b !== a && crosses(a, b) && b.row <= a.row);
    if (!blocker) continue;
    const room = a.anchorEnd ? a.ax - blocker.ax - 10 : blocker.ax - a.ax - 10;
    let text = a.label;
    while (text.length > 1 && measure(`${text}…`) > room) text = text.slice(0, -1);
    a.text = `${text.trimEnd()}…`;
  }
  return items;
}

function drawAnnotations(g, placed, top, bottom) {
  const rows = d3.max(placed, (p) => p.row) ?? 0;
  for (const p of placed) {
    const ty = top - 10 - (rows - p.row) * 14;
    const ag = g.append('g').attr('class', 'annotation');
    ag.append('line').attr('x1', p.ax).attr('x2', p.ax).attr('y1', ty + 4).attr('y2', bottom);
    const t = ag.append('text').attr('x', p.anchorEnd ? p.ax - 4 : p.ax + 4).attr('y', ty)
      .attr('text-anchor', p.anchorEnd ? 'end' : 'start').text(p.text);
    if (p.text !== p.label) t.append('title').text(p.label);
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
  if (w <= 0 || h <= 0) return '';
  r = Math.min(r, horizontal ? h / 2 : w / 2, horizontal ? w : h);
  if (horizontal) {
    return `M${x},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${h - 2 * r}a${r},${r} 0 0 1 ${-r},${r}h${-(w - r)}Z`;
  }
  return `M${x},${y + h}v${-(h - r)}a${r},${r} 0 0 1 ${r},${-r}h${w - 2 * r}a${r},${r} 0 0 1 ${r},${r}v${h - r}Z`;
}

// Catch-all categories (Other, Not stated, Unknown) go last; everything else keeps its order.
const pinCatchAllLast = (items, keyOf = (s) => s.key) => [
  ...items.filter((s) => !isCatchAll(keyOf(s))), ...items.filter((s) => isCatchAll(keyOf(s))),
];

// The months this chart's "then" markers point at: 5 years, 1 year and 3 months before its last month.
const referenceMonths = (to) => Object.entries(WINDOWS).reverse().map(([key, n]) => ({ key, month: addMonths(to, -n) }));

// The end-label badge compares with a year earlier, the style guide's cleanest window, falling back to 5y then 3m.
function endDelta(s, to) {
  for (const key of ['1y', '5y', '3m']) {
    const c = change(s, addMonths(to, -WINDOWS[key]), to);
    if (c) return { ...c, key };
  }
  return null;
}

// ---------- time series: line, stacked-area, bar over time ----------

function stackSeries(series, attrs, data, until) {
  if (!attrs.breakdown) throw new AuthoringError('stacked-area needs a breakdown whose shares add up to 100%');
  const all = resolveSeries(data, { breakdown: attrs.breakdown }, until);
  const months = all[0].points.map((p) => p.month);
  const overfull = months.find((m) => d3.sum(all, (s) => valueAt(s, m)) > 1.05);
  if (overfull) {
    throw new AuthoringError(`stacked-area can't draw "${attrs.breakdown}": its shares don't add up to 100% (a post can count in several). Use small-multiples or dot.`);
  }
  const last = (s) => s.points.at(-1)?.value ?? 0;
  const keep = attrs.categories
    ? new Set(series.map((s) => s.key))
    : all.length > MAX_BANDS
      ? new Set([...all].filter((s) => !isCatchAll(s.key)).sort((a, b) => last(b) - last(a)).slice(0, MAX_BANDS - 1).map((s) => s.key))
      : new Set(all.map((s) => s.key));
  const kept = pinCatchAllLast(all.filter((s) => keep.has(s.key)));
  const rest = all.filter((s) => !keep.has(s.key));
  if (!rest.length) return kept;
  const other = {
    ...rest[0], key: '_rest', label: 'Everything else', folded: true,
    points: kept[0].points.map((p) => ({ ...p, value: d3.sum(rest, (s) => valueAt(s, p.month)) })),
  };
  return [...kept, other];
}

function timeChart(fig, series, attrs, until, data, mode) {
  const to = attrs.to && attrs.to < until ? attrs.to : until;
  series = series.map((s) => ({ ...s, points: s.points.filter((p) => p.month <= to) }));
  if (mode === 'area') series = stackSeries(series, attrs, data, to);
  const unit = series[0].unit;
  const highlight = list(attrs.highlight);
  const colorOf = (s, i) => {
    if (s.folded || (highlight && !highlight.includes(s.key))) return DEEMPH;
    return color(highlight ? highlight.indexOf(s.key) : i);
  };
  const first = d3.min(series, (s) => s.points[0]?.month);
  const annotations = parseAnnotations(attrs.annotate);
  const tooltip = makeTooltip(fig.plot);
  seriesTable(fig, series, makeFormat(unit, { precise: true }));

  let from = rangePresets(fig.presets, first, to, attrs.from ?? (mode === 'bar' ? addMonths(to, -23) : null), (f) => {
    from = f;
    redraw();
  });

  const redraw = responsive(fig.plot, (width) => {
    const visible = series.map((s) => ({ ...s, points: s.points.filter((p) => p.month >= from) }));
    const months = [...new Set(visible.flatMap((s) => s.points.map((p) => p.month)))].sort();
    if (!months.length) {
      fig.empty('No data for this range');
      return;
    }
    const startM = months[0];
    const endM = months.at(-1);
    const smoothed = series.some((s) => s.smoothed) ? '; the benchmark is a 12-month average, as it is not seasonally adjusted and swings with the seasons' : '';
    const indexed = attrs.base ? `, indexed to ${monthLabel(attrs.base)} = 100${smoothed}` : '';
    fig.setSubtitle(`${subjectOf(series)}${indexed}, ${monthLabel(startM, 'long')} to ${monthLabel(endM, 'long')}`);
    const fmt = makeFormat(unit);
    const tipFmt = makeFormat(unit, { precise: true });
    const phone = isPhone(width);
    const height = mode === 'bar' ? (phone ? 220 : 260) : phone ? 250 : 320;
    const start = monthDate(startM);
    const end = monthDate(endM);
    const svg = newSvg(fig, width, height);
    const g = svg.append('g');

    let stacked;
    let yDomain;
    if (mode === 'area') {
      const rows = months.map((m) => Object.fromEntries([['month', m], ...visible.map((s) => [s.key, valueAt(s, m) ?? 0])]));
      stacked = d3.stack().keys(visible.map((s) => s.key))(rows);
      yDomain = [0, Math.min(1, d3.max(stacked.at(-1), (d) => d[1]))];
    } else {
      const values = visible.flatMap((s) => s.points.map((p) => p.value));
      const max = d3.max(values);
      // Bars and counts start at zero; dollar medians would be a flat line pressed to the top if they did.
      yDomain = unit === 'score' ? [0, 4] : unit === 'usd' && mode !== 'bar' ? [d3.min(values) * 0.85, max * 1.05] : [0, unit === 'share' ? Math.min(1, max * 1.08) : max * 1.08];
    }
    const y = d3.scaleLinear().domain(yDomain).nice();
    const margin = { top: 22, bottom: 28, right: 12, left: textWidth(svg, y.ticks(5).map(tickFormat(unit)), 'tick') + 10 };

    // Direct labels at the right edge, spread apart with leader lines when lines end close together.
    const yEnd = (s, i) => (mode === 'area' ? y((stacked[i].at(-1)[0] + stacked[i].at(-1)[1]) / 2) : y(s.points.at(-1)?.value));
    const single = visible.length === 1;
    let labels = mode === 'bar' ? [] : visible.map((s, i) => {
      if (!s.points.length || s.points.at(-1).month !== endM) return null;
      const d = single ? endDelta(s, endM) : null;
      const lines = [{ text: fmt(s.points.at(-1).value), cls: 'end-value' }];
      if (d) lines.push({ text: `${d.mark} ${d.text.replace(/^[+−]/, '')} vs ${d.key}`, cls: `end-delta d-${d.tone}`, title: d.word });
      if (!single) lines.push({ text: s.label, cls: 'end-name' });
      return { s, i, lines };
    }).filter(Boolean);
    const labelWidth = (ls) => textWidth(svg, ls.flatMap((l) => l.lines.map((x) => x.text)), 'end-label');
    let right = labels.length ? labelWidth(labels) + 22 : 12;
    // On a narrow screen names make the label column too wide: keep values only and fall back to the legend.
    const namesDropped = !single && right > width * 0.36;
    if (namesDropped) {
      labels = labels.map((l) => ({ ...l, lines: l.lines.filter((x) => x.cls !== 'end-name') }));
      right = labelWidth(labels) + 22;
    }
    margin.right = Math.max(12, right);
    setLegend(fig.legend, single || !namesDropped ? [] : visible.map((s, i) => ({ label: s.label, color: colorOf(s, i) })), mode === 'line' ? 'line' : 'rect');

    const x = d3.scaleUtc().domain([start, end]).range([margin.left, width - margin.right]);
    const band = d3.scaleBand().domain(months).range([margin.left, width - margin.right]).paddingInner(0.2);
    if (mode === 'bar') x.range([margin.left + band.bandwidth() / 2, width - margin.right - band.bandwidth() / 2]);
    const placedNotes = layoutAnnotations(annotations, x, start, end, margin.left, width - margin.right,
      (text) => textWidth(svg, [text], 'annotation-label'));
    if (placedNotes.length) margin.top = 34 + (d3.max(placedNotes, (p) => p.row) + 1) * 14;
    y.range([height - margin.bottom, margin.top]);
    for (const l of labels) l.y = yEnd(l.s, l.i);

    drawYAxis(g, y, margin.left, width - margin.right, unit);
    drawXAxis(g, x, height - margin.bottom, width, start, end);

    const marks = g.append('g').attr('class', 'marks');
    const line = d3.line().defined((p) => p.value != null).x((p) => x(p.date)).y((p) => y(p.value));
    if (mode === 'area') {
      marks.selectAll('path').data(stacked).join('path')
        .attr('class', (d, i) => (visible[i].folded ? 'band band-other' : 'band'))
        .attr('fill', (d, i) => colorOf(visible[i], i))
        .attr('d', d3.area().x((d) => x(monthDate(d.data.month))).y0((d) => y(d[0])).y1((d) => y(d[1])));
    } else if (mode === 'bar') {
      const bw = Math.min(24, Math.max(1, band.bandwidth()));
      marks.selectAll('path').data(visible[0].points).join('path')
        .attr('class', (p) => (p.month === endM ? 'bar' : 'bar bar-context'))
        .attr('d', (p) => roundedBar(band(p.month) + (band.bandwidth() - bw) / 2, y(p.value), bw, y(0) - y(p.value), bw > 6 ? 4 : 0));
      const pts = visible[0].points;
      const last = pts.at(-1);
      if (last.month === endM) {
        // Sit above the taller of this bar and its neighbors so the label never overlaps one of them.
        const top = d3.max(pts.slice(-3), (p) => p.value);
        marks.append('text').attr('class', 'bar-value').attr('x', x(last.date)).attr('y', y(top) - 6)
          .attr('text-anchor', 'middle').text(fmt(last.value));
      }
    } else {
      if (single) {
        marks.append('path').attr('class', 'wash').attr('fill', color(0))
          .attr('d', d3.area().defined((p) => p.value != null).x((p) => x(p.date)).y0(y(y.domain()[0])).y1((p) => y(p.value))(withGaps(visible[0].points)));
      }
      // De-emphasized series first so the story series sit on top.
      const order = visible.map((s, i) => [s, i]).sort(([a, ai], [b, bi]) => (colorOf(b, bi) === DEEMPH) - (colorOf(a, ai) === DEEMPH));
      for (const [s, i] of order) {
        marks.append('path').attr('class', 'line').attr('stroke', colorOf(s, i)).attr('d', line(withGaps(s.points)));
        if (s.points.length < MARKER_LIMIT) {
          marks.append('g').selectAll('circle').data(s.points).join('circle').attr('class', 'point')
            .attr('cx', (p) => x(p.date)).attr('cy', (p) => y(p.value)).attr('r', 2.5).attr('fill', colorOf(s, i));
        }
      }
    }

    drawAnnotations(g, placedNotes, margin.top, height - margin.bottom);
    drawReferences(g, svg, visible, mode, { x, y, stacked, colorOf, endM, startM, top: margin.top });

    if (labels.length) {
      const lineH = 14;
      const lg = g.append('g').attr('class', 'end-labels');
      const placed = dodge(labels, d3.max(labels, (l) => l.lines.length) * lineH + 4, margin.top, height - margin.bottom);
      const lx = width - margin.right + 14;
      for (const l of placed) {
        const ex = x(monthDate(endM));
        if (mode === 'line') lg.append('circle').attr('class', 'end-dot').attr('cx', ex).attr('cy', l.y).attr('r', 4).attr('fill', colorOf(l.s, l.i));
        if (Math.abs(l.ty - l.y) > 2) lg.append('path').attr('class', 'leader').attr('d', `M${ex + 5},${l.y}L${lx - 3},${l.ty}`);
        const top = l.ty - ((l.lines.length - 1) * lineH) / 2;
        const t = lg.append('text').attr('x', lx).attr('y', top).attr('dy', '0.32em');
        l.lines.forEach((ln, k) => {
          const span = t.append('tspan').attr('x', lx).attr('dy', k ? lineH : '0.32em').attr('class', ln.cls).text(ln.text);
          if (ln.title) span.append('title').text(ln.title);
        });
      }
    }

    const head = visible[0];
    const lastValue = valueAt(head, endM);
    const d1 = endDelta(head, endM);
    fig.setSummary(`${head.label}: ${fmt(lastValue)} in ${monthLabel(endM, 'long')}${d1 ? `, ${d1.text} against ${d1.key} earlier (${d1.word || 'no verdict'})` : ''}. Use the left and right arrow keys to read each month.`);

    // Hover / keyboard layer: the crosshair snaps to the nearest month.
    const cross = g.append('g').attr('class', 'crosshair').style('display', 'none');
    cross.append('line').attr('y1', margin.top).attr('y2', height - margin.bottom);
    const dots = cross.selectAll('circle').data(visible).join('circle').attr('r', 4).attr('fill', (s, i) => colorOf(s, i));
    const readout = (m) => {
      // A benchmark names the period its number describes, which usually trails the HN month.
      const labelOf = (s) => {
        const ref = s.external && pointAt(s, m)?.ref_period;
        if (!ref) return s.label;
        return s.smoothed ? `${s.label} (12 months to ${periodLabel(ref)})` : `${s.label} (${periodLabel(ref)} data)`;
      };
      const rows = visible.map((s, i) => ({ color: colorOf(s, i), value: tipFmt(valueAt(s, m)), label: visible.length > 1 ? labelOf(s) : '', v: valueAt(s, m) ?? -1 }));
      if (mode === 'area') rows.reverse();
      else rows.sort((a, b) => b.v - a.v);
      // A post count is redundant beside a count metric, but tells the reader how solid a share or median is.
      const n = unit === 'count' ? null : pointAt(head, m)?.n;
      return { rows, foot: n ? `Based on ${n.toLocaleString('en-US')} posts` : '' };
    };
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
      const { rows, foot } = readout(m);
      tooltip.show(cx, margin.top, monthLabel(m, 'long'), rows, foot);
      return `${monthLabel(m, 'long')}: ${rows.map((r) => `${r.label} ${r.value}`.trim()).join(', ')}`;
    };
    const hide = () => { cross.style('display', 'none'); tooltip.hide(); };
    let idx = months.length - 1;
    g.append('rect').attr('class', 'hit')
      .attr('x', margin.left).attr('y', margin.top).attr('width', width - margin.left - margin.right).attr('height', height - margin.top - margin.bottom)
      .on('pointermove', (ev) => {
        const date = x.invert(d3.pointer(ev)[0]);
        show(d3.minIndex(months, (m) => Math.abs(monthDate(m) - date)));
      })
      .on('pointerleave', hide);
    keyboardMonths(svg, months.length, () => idx, (i) => { idx = i; fig.announce(show(i)); }, () => { hide(); idx = months.length - 1; });
  });
}

// Then-vs-now inside the chart: hollow markers 5 years, 1 year and 3 months before the last month, with small labels.
function drawReferences(g, svg, visible, mode, { x, y, stacked, colorOf, endM, startM, top }) {
  const refs = referenceMonths(endM).filter((r) => r.month >= startM);
  if (!refs.length) return;
  const targets = mode === 'line' ? visible.slice(0, 2).map((s, i) => ({ s, i })) : [{ s: visible[0], i: 0 }];
  const rg = g.append('g').attr('class', 'refs');
  const placed = [];
  for (const r of refs) {
    let labelY = Infinity;
    for (const { s, i } of targets) {
      const v = valueAt(s, r.month);
      if (v == null) continue;
      const cy = mode === 'area' ? y(stacked[i].find((d) => d.data.month === r.month)[1]) : mode === 'bar' ? y(v) - 8 : y(v);
      rg.append('circle').attr('class', 'ref-dot').attr('cx', x(monthDate(r.month))).attr('cy', cy).attr('r', 4)
        .attr('stroke', mode === 'bar' ? 'var(--ink-2)' : colorOf(s, i));
      labelY = Math.min(labelY, cy);
    }
    if (labelY === Infinity) continue;
    const cx = x(monthDate(r.month));
    const text = `${r.key} ago`;
    const w = textWidth(svg, [text], 'ref-label');
    const box = [cx - w / 2, cx + w / 2];
    const endX = x(monthDate(endM));
    if (box[1] > endX - 6 || placed.some(([a, b]) => box[0] < b + 6 && box[1] > a - 6)) continue;
    placed.push(box);
    rg.append('text').attr('class', 'ref-label').attr('x', cx).attr('y', Math.max(top + 4, labelY - 10)).attr('text-anchor', 'middle').text(text);
  }
}

function keyboardMonths(svg, count, getIdx, show, reset) {
  svg.on('focus', () => show(getIdx())).on('blur', reset).on('keydown', (ev) => {
    const step = { ArrowLeft: -1, ArrowRight: 1, Home: -Infinity, End: Infinity }[ev.key];
    if (step != null) {
      show(Math.max(0, Math.min(count - 1, getIdx() + step)));
      ev.preventDefault();
    } else if (ev.key === 'Escape') reset();
  });
}

// ---------- small multiples: one panel per series, shared scales, synced crosshair ----------

function smallMultiples(fig, series, attrs, until) {
  const to = attrs.to && attrs.to < until ? attrs.to : until;
  const highlight = list(attrs.highlight);
  series = series.map((s) => ({ ...s, points: s.points.filter((p) => p.month <= to) }));
  if (highlight) series = [...series.filter((s) => highlight.includes(s.key)), ...series.filter((s) => !highlight.includes(s.key))];
  const colorOf = (s) => (highlight && !highlight.includes(s.key) ? DEEMPH : color(0));
  const sharedY = new Set(series.map((s) => s.unit)).size === 1;
  const first = d3.min(series, (s) => s.points[0]?.month);
  const annotations = parseAnnotations(attrs.annotate);
  seriesTable(fig, series, makeFormat(series[0].unit, { precise: true }));
  const grid = el('div', 'multiples');
  grid.tabIndex = 0;
  grid.setAttribute('role', 'group');
  grid.setAttribute('aria-labelledby', `${fig.ids.title} ${fig.ids.sub}`);
  grid.setAttribute('aria-describedby', fig.ids.summary);
  fig.plot.append(grid);
  const tooltip = makeTooltip(fig.plot);

  let from = rangePresets(fig.presets, first, to, attrs.from, (f) => { from = f; redraw(); });
  const redraw = responsive(fig.plot, (width) => {
    const visible = series.map((s) => ({ ...s, points: s.points.filter((p) => p.month >= from) }));
    const months = [...new Set(visible.flatMap((s) => s.points.map((p) => p.month)))].sort();
    if (!months.length) {
      grid.replaceChildren(el('p', 'chart-empty', 'No data for this range'));
      return;
    }
    fig.setSubtitle(`${subjectOf(series)}, ${monthLabel(months[0], 'long')} to ${monthLabel(months.at(-1), 'long')}`);
    const fmtFor = (s) => makeFormat(s.unit);
    const cols = width < 420 ? 2 : width < 640 ? 3 : 4;
    const gap = 16;
    const pw = Math.floor((width - gap * (cols - 1)) / cols);
    const top = annotations.length ? 18 : 6;
    const ph = 104 + top;
    const start = monthDate(months[0]);
    const end = monthDate(months.at(-1));
    const x = d3.scaleUtc().domain([start, end]).range([4, pw - 6]);
    const all = visible.flatMap((s) => s.points.map((p) => p.value));
    const yFor = (s) => d3.scaleLinear().domain([0, d3.max(sharedY ? all : s.points.map((p) => p.value)) * 1.05]).nice().range([ph - 18, top]);
    const yearFmt = d3.utcFormat('%Y');
    const refs = referenceMonths(months.at(-1)).filter((r) => r.month >= months[0]);

    const panels = visible.map((s, k) => {
      const y = yFor(s);
      const fmt = fmtFor(s);
      const panel = el('div', 'panel');
      const head = el('div', 'panel-head');
      const val = el('span', 'panel-value', fmt(s.points.at(-1)?.value));
      head.append(el('span', 'panel-name', s.label), val);
      panel.append(head);
      const svg = d3.select(panel).append('svg').attr('width', pw).attr('height', ph).attr('viewBox', `0 0 ${pw} ${ph}`).attr('aria-hidden', 'true');
      const ticks = y.ticks(3);
      svg.append('g').attr('class', 'grid').selectAll('line').data(ticks).join('line')
        .attr('x1', 0).attr('x2', pw).attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).attr('class', (d) => (d === 0 ? 'baseline' : null));
      for (const a of annotations) {
        const d = monthDate(a.month);
        if (d < start || d > end) continue;
        svg.append('line').attr('class', 'annotation-line').attr('x1', x(d)).attr('x2', x(d)).attr('y1', top).attr('y2', ph - 18);
        // Only the first panel carries the label; the same line in every other panel means the same event.
        if (k === 0) {
          const anchorEnd = x(d) > pw * 0.55;
          svg.append('text').attr('class', 'annotation-text').attr('x', x(d) + (anchorEnd ? -3 : 3)).attr('y', top - 6)
            .attr('text-anchor', anchorEnd ? 'end' : 'start').text(a.label);
        }
      }
      svg.append('path').attr('class', 'wash').attr('fill', colorOf(s))
        .attr('d', d3.area().defined((p) => p.value != null).x((p) => x(p.date)).y0(y(0)).y1((p) => y(p.value))(withGaps(s.points)));
      svg.append('path').attr('class', 'line').attr('stroke', colorOf(s))
        .attr('d', d3.line().defined((p) => p.value != null).x((p) => x(p.date)).y((p) => y(p.value))(withGaps(s.points)));
      for (const r of refs) {
        const v = valueAt(s, r.month);
        if (v != null) svg.append('circle').attr('class', 'ref-dot').attr('stroke', colorOf(s)).attr('cx', x(monthDate(r.month))).attr('cy', y(v)).attr('r', 3);
      }
      // Tick labels go on top of the line (with a paper halo); the topmost is skipped so it never crowds the panel title.
      svg.append('g').attr('class', 'grid').selectAll('text').data(ticks.filter((d) => d !== 0 && y(d) > top + 12)).join('text')
        .attr('x', 0).attr('y', (d) => y(d) - 3).text(tickFormat(s.unit));
      const ax = svg.append('g').attr('class', 'xaxis');
      ax.append('text').attr('x', 4).attr('y', ph - 4).text(yearFmt(start));
      ax.append('text').attr('x', pw - 4).attr('y', ph - 4).attr('text-anchor', 'end').text(yearFmt(end));
      const cross = svg.append('g').attr('class', 'crosshair').style('display', 'none');
      cross.append('line').attr('y1', top).attr('y2', ph - 18);
      cross.append('circle').attr('r', 4).attr('fill', colorOf(s));
      return { s, y, svg, cross, val, panel, fmt };
    });
    grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
    grid.replaceChildren(...panels.map((p) => p.panel));
    const lastM = months.at(-1);
    fig.setSummary(`${panels.map((p) => `${p.s.label} ${p.fmt(valueAt(p.s, lastM))}`).join(', ')} in ${monthLabel(lastM, 'long')}. Use the left and right arrow keys to read each month.`);

    const show = (m, hovered) => {
      const cx = x(monthDate(m));
      for (const p of panels) {
        const v = valueAt(p.s, m);
        p.val.textContent = p.fmt(v);
        p.cross.style('display', v == null ? 'none' : null);
        p.cross.select('line').attr('x1', cx).attr('x2', cx);
        p.cross.select('circle').attr('cx', cx).attr('cy', v == null ? -99 : p.y(v));
      }
      if (hovered) {
        const box = hovered.panel.getBoundingClientRect();
        const host = fig.plot.getBoundingClientRect();
        const n = pointAt(hovered.s, m)?.n;
        tooltip.show(box.left - host.left + cx, box.top - host.top + 24, monthLabel(m, 'long'),
          [{ color: colorOf(hovered.s), value: makeFormat(hovered.s.unit, { precise: true })(valueAt(hovered.s, m)), label: hovered.s.label }],
          n ? `Based on ${n.toLocaleString('en-US')} posts` : '');
      }
      return `${monthLabel(m, 'long')}: ${panels.map((p) => `${p.s.label} ${p.fmt(valueAt(p.s, m))}`).join(', ')}`;
    };
    let idx = months.length - 1;
    const reset = () => {
      tooltip.hide();
      idx = months.length - 1;
      for (const p of panels) {
        p.cross.style('display', 'none');
        p.val.textContent = p.fmt(p.s.points.at(-1)?.value);
      }
    };
    for (const p of panels) {
      p.svg.on('pointermove', (ev) => {
        const date = x.invert(d3.pointer(ev)[0]);
        show(months[d3.minIndex(months, (m) => Math.abs(monthDate(m) - date))], p);
      }).on('pointerleave', reset);
    }
    keyboardMonths(d3.select(grid), months.length, () => idx, (i) => { idx = i; fig.announce(show(months[i])); }, reset);
  });
}

// ---------- two-month comparisons: slope and dot ----------

function comparisonRows(series, from, to) {
  return series.map((s, i) => {
    const a = valueAt(s, from);
    const b = valueAt(s, to);
    const d = change(s, from, to);
    return { s, i, a, b, d, tone: d?.tone ?? 'flat' };
  }).filter((r) => r.a != null && r.b != null);
}

const changeRow = (c) => ({
  value: c ? `${c.mark} ${c.text}`.trim() : 'n/a', label: c?.word || 'change', tone: c?.tone,
});

function comparisonTable(fig, rows, from, to, fmt) {
  fig.table(() => ({
    columns: ['', monthLabel(from), monthLabel(to), 'Change'],
    rows: rows.map((r) => [r.s.label, fmt(r.a), fmt(r.b), r.d?.text ?? 'n/a']),
  }));
}

function checkComparable(rows, from, to) {
  if (!rows.length) throw new AuthoringError(`No data for both ${monthLabel(from)} and ${monthLabel(to)}`);
}

// Hover and arrow-key focus for charts made of discrete items (slope lines, dot rows, bars).
// The tooltip anchors to the item, so keyboard and pointer readers see the same thing in the same place.
function bindItems(fig, svg, marks, items, pickIndex, describe, tooltip) {
  let idx = -1;
  const show = (i, keyboard) => {
    idx = i;
    marks.classed('dim', (d) => d !== items[i]);
    const { x, y, header, rows } = describe(items[i]);
    tooltip.show(x, y, header, rows);
    if (keyboard) fig.announce(`${header}: ${rows.map((r) => `${r.label} ${r.value}`).join(', ')}`);
  };
  const hide = () => { marks.classed('dim', false); tooltip.hide(); };
  svg.on('pointermove', (ev) => {
    const i = pickIndex(...d3.pointer(ev));
    if (i == null || i < 0 || i >= items.length) hide();
    else show(i);
  }).on('pointerleave', hide)
    .on('focus', () => show(Math.max(0, idx), true))
    .on('blur', () => { hide(); idx = -1; })
    .on('keydown', (ev) => {
      const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[ev.key];
      if (step) {
        show((Math.max(0, idx) + step + items.length) % items.length, true);
        ev.preventDefault();
      } else if (ev.key === 'Escape') hide();
    });
}

function slopeChart(fig, series, attrs, until) {
  const [from, to] = attrs.months ? list(attrs.months) : [pastMonth(attrs.vs ?? '5y', until), until];
  if (to > until) throw new AuthoringError(`months="${attrs.months}" goes past this issue (${until})`);
  const rows = comparisonRows(series, from, to);
  checkComparable(rows, from, to);
  const fmt = makeFormat(series[0].unit);
  const tipFmt = makeFormat(series[0].unit, { precise: true });
  const highlight = list(attrs.highlight) ?? [d3.greatest(rows, (r) => Math.abs(r.b - r.a)).s.key];
  const colorOf = (r) => (highlight.includes(r.s.key) ? color(highlight.indexOf(r.s.key)) : DEEMPH);
  comparisonTable(fig, rows, from, to, tipFmt);
  fig.setSubtitle(`${subjectOf(series)}, ${monthLabel(from, 'long')} and ${monthLabel(to, 'long')}`);
  fig.setSummary(rows.map((r) => `${r.s.label}: ${fmt(r.a)} to ${fmt(r.b)}`).join('; '));
  const tooltip = makeTooltip(fig.plot);

  responsive(fig.plot, (width) => {
    const phone = isPhone(width);
    const height = Math.max(240, rows.length * 24 + 70);
    const svg = newSvg(fig, width, height);
    const leftText = rows.map((r) => (phone ? fmt(r.a) : `${r.s.label} ${fmt(r.a)}`));
    const rightText = rows.map((r) => `${fmt(r.b)} ${r.s.label}`);
    const m = {
      top: 34, bottom: 16,
      left: Math.max(36, textWidth(svg, leftText, 'slope-label') + 14),
      right: Math.max(36, textWidth(svg, rightText, 'slope-label') + 14),
    };
    const y = d3.scaleLinear().domain([0, d3.max(rows, (r) => Math.max(r.a, r.b)) * 1.05]).range([height - m.bottom, m.top]);
    const x0 = m.left;
    const x1 = width - m.right;
    const g = svg.append('g');
    g.append('text').attr('class', 'col-head').attr('x', x0).attr('y', 14).attr('text-anchor', 'middle').text(monthLabel(from));
    g.append('text').attr('class', 'col-head').attr('x', x1).attr('y', 14).attr('text-anchor', 'middle').text(monthLabel(to));
    for (const xx of [x0, x1]) g.append('line').attr('class', 'axis-rule').attr('x1', xx).attr('x2', xx).attr('y1', m.top - 8).attr('y2', height - m.bottom);

    const ordered = [...rows].sort((a, b) => (colorOf(b) === DEEMPH) - (colorOf(a) === DEEMPH));
    const lines = g.append('g').selectAll('g').data(ordered).join('g').attr('class', 'slope');
    lines.append('line').attr('x1', x0).attr('x2', x1).attr('y1', (r) => y(r.a)).attr('y2', (r) => y(r.b)).attr('stroke', colorOf);
    lines.append('circle').attr('class', 'slope-then').attr('cx', x0).attr('cy', (r) => y(r.a)).attr('r', 4).attr('stroke', colorOf);
    lines.append('circle').attr('cx', x1).attr('cy', (r) => y(r.b)).attr('r', 4).attr('fill', colorOf);

    const labels = (side) => dodge(rows.map((r) => ({ r, y: y(side === 'a' ? r.a : r.b) })), 15, m.top, height - m.bottom);
    g.append('g').attr('class', 'slope-labels').selectAll('text').data(labels('a')).join('text')
      .attr('x', x0 - 10).attr('y', (d) => d.ty).attr('dy', '0.32em').attr('text-anchor', 'end')
      .attr('class', (d) => (colorOf(d.r) === DEEMPH ? 'muted' : null))
      .text((d) => (phone ? fmt(d.r.a) : `${d.r.s.label} ${fmt(d.r.a)}`));
    g.append('g').attr('class', 'slope-labels').selectAll('text').data(labels('b')).join('text')
      .attr('x', x1 + 10).attr('y', (d) => d.ty).attr('dy', '0.32em')
      .attr('class', (d) => (colorOf(d.r) === DEEMPH ? 'muted' : null))
      .text((d) => `${fmt(d.r.b)} ${d.r.s.label}`);

    const yAt = (r, px) => {
      const t = Math.max(0, Math.min(1, (px - x0) / (x1 - x0)));
      return y(r.a) + (y(r.b) - y(r.a)) * t;
    };
    bindItems(fig, svg, lines, ordered, (px, py) => {
      if (px < x0 - 24 || px > x1 + 24) return null;
      const i = d3.minIndex(ordered, (r) => Math.abs(yAt(r, px) - py));
      return Math.abs(yAt(ordered[i], px) - py) < 24 ? i : null;
    }, (r) => ({
      x: (x0 + x1) / 2, y: (y(r.a) + y(r.b)) / 2 + 12, header: r.s.label,
      rows: [
        { value: tipFmt(r.a), label: monthLabel(from) },
        { value: tipFmt(r.b), label: monthLabel(to) },
        changeRow(r.d),
      ],
    }), tooltip);
  });
}

function dotChart(fig, series, attrs, until) {
  const from = pastMonth(attrs.vs ?? '1y', until);
  const to = until;
  const rows = pinCatchAllLast(comparisonRows(series, from, to).sort((a, b) => b.b - a.b), (r) => r.s.key);
  checkComparable(rows, from, to);
  const fmt = makeFormat(series[0].unit);
  const tipFmt = makeFormat(series[0].unit, { precise: true });
  comparisonTable(fig, rows, from, to, tipFmt);
  fig.setSubtitle(`${subjectOf(series)}, ${monthLabel(to, 'long')} compared with ${monthLabel(from, 'long')}`);
  fig.setSummary(rows.map((r) => `${r.s.label}: ${fmt(r.b)}, ${r.d?.text ?? 'no change'} since ${monthLabel(from)}`).join('; '));
  const tooltip = makeTooltip(fig.plot);

  responsive(fig.plot, (width) => {
    // On a phone each label sits above its dots and the change column is dropped, so the dots get the full
    // width; the tooltip and table still carry the change.
    const phone = isPhone(width);
    const rowH = phone ? 44 : 30;
    const svg = newSvg(fig, width, 0);
    const m = {
      top: 30, bottom: 26,
      left: phone ? 8 : textWidth(svg, rows.map((r) => r.s.label), 'row-label') + 16,
      right: textWidth(svg, rows.map((r) => (phone ? fmt(r.b) : `${fmt(r.b)} ${r.d?.text ?? ''}`)), 'row-value') + 24,
    };
    const height = rows.length * rowH + m.top + m.bottom;
    svg.attr('height', height).attr('viewBox', `0 0 ${width} ${height}`);
    const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => Math.max(r.a, r.b)) * 1.05]).nice().range([m.left, width - m.right]);
    const g = svg.append('g');
    const ticks = x.ticks(phone ? 3 : 5);
    const grid = g.append('g').attr('class', 'grid');
    grid.selectAll('line').data(ticks).join('line').attr('x1', (d) => x(d)).attr('x2', (d) => x(d)).attr('y1', m.top).attr('y2', height - m.bottom)
      .attr('class', (d) => (d === 0 ? 'baseline' : null));
    grid.selectAll('text').data(ticks).join('text').attr('x', (d) => x(d)).attr('y', height - 8).attr('text-anchor', 'middle').text(tickFormat('share'));

    // Label the two dots of the first row directly; fall back to a legend when they sit too close to share a line.
    const r0 = rows[0];
    const nowText = monthLabel(to);
    const thenText = monthLabel(from);
    const keyGap = Math.abs(x(r0.b) - x(r0.a));
    const fits = keyGap > (textWidth(svg, [nowText], 'key-label') + textWidth(svg, [thenText], 'key-label')) / 2 + 10;
    if (fits) {
      g.append('text').attr('class', 'key-label').attr('x', x(r0.b)).attr('y', m.top - 6).attr('text-anchor', 'middle').text(nowText);
      g.append('text').attr('class', 'key-label muted').attr('x', x(r0.a)).attr('y', m.top - 6).attr('text-anchor', 'middle').text(thenText);
    }
    setLegend(fig.legend, fits ? [] : [{ label: nowText, color: color(0) }, { label: thenText, color: 'var(--then)' }], 'dot');

    const row = g.append('g').selectAll('g').data(rows).join('g').attr('class', 'dot-row')
      .attr('transform', (r, k) => `translate(0,${m.top + k * rowH + rowH / 2})`);
    const dotY = phone ? 8 : 0;
    row.append('text').attr('class', 'row-label').text((r) => r.s.label)
      .attr('x', phone ? 0 : m.left - 12).attr('y', phone ? -10 : 0).attr('dy', '0.32em').attr('text-anchor', phone ? 'start' : 'end');
    row.append('line').attr('class', 'connector').attr('y1', dotY).attr('y2', dotY).attr('x1', (r) => x(r.a)).attr('x2', (r) => x(r.b));
    row.append('circle').attr('class', 'then-dot').attr('cx', (r) => x(r.a)).attr('cy', dotY).attr('r', 5);
    row.append('circle').attr('class', 'now-dot').attr('cx', (r) => x(r.b)).attr('cy', dotY).attr('r', 5).attr('fill', color(0));
    const val = row.append('text').attr('class', 'row-value').attr('x', width - m.right + 12).attr('y', dotY).attr('dy', '0.32em');
    val.append('tspan').text((r) => fmt(r.b));
    if (!phone) val.append('tspan').attr('class', 'muted').attr('dx', 6).text((r) => r.d?.text ?? '');

    bindItems(fig, svg, row, rows, (px, py) => Math.floor((py - m.top) / rowH), (r) => ({
      x: x(Math.max(r.a, r.b)), y: m.top + rows.indexOf(r) * rowH + rowH, header: r.s.label,
      rows: [
        { color: color(0), value: tipFmt(r.b), label: monthLabel(to) },
        { color: 'var(--then)', value: tipFmt(r.a), label: monthLabel(from) },
        changeRow(r.d),
      ],
    }), tooltip);
  });
}

// Horizontal bars for a breakdown at one month; with a scalar metric, monthly columns.
function barChart(fig, series, attrs, until, data) {
  if (!attrs.breakdown) return timeChart(fig, series, attrs, until, data, 'bar');
  const month = attrs.to && attrs.to < until ? attrs.to : until;
  const rows = pinCatchAllLast(series.map((s) => ({ s, v: valueAt(s, month) })).filter((r) => r.v != null).sort((a, b) => b.v - a.v), (r) => r.s.key);
  if (!rows.length) throw new AuthoringError(`No data for ${monthLabel(month)}`);
  const fmt = makeFormat('share');
  const tipFmt = makeFormat('share', { precise: true });
  fig.table(() => ({ columns: ['', monthLabel(month)], rows: rows.map((r) => [r.s.label, tipFmt(r.v)]) }));
  fig.setSubtitle(`${subjectOf(series)}, ${monthLabel(month, 'long')}`);
  fig.setSummary(rows.map((r) => `${r.s.label} ${fmt(r.v)}`).join(', '));
  const tooltip = makeTooltip(fig.plot);
  responsive(fig.plot, (width) => {
    const rowH = 30;
    const height = rows.length * rowH + 8;
    const svg = newSvg(fig, width, height);
    const m = { top: 4, left: textWidth(svg, rows.map((r) => r.s.label), 'row-label') + 16, right: 56 };
    const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.v)]).range([m.left, width - m.right]);
    const row = svg.append('g').selectAll('g').data(rows).join('g').attr('class', 'dot-row')
      .attr('transform', (r, k) => `translate(0,${m.top + k * rowH})`);
    row.append('text').attr('class', 'row-label').attr('x', m.left - 12).attr('y', rowH / 2).attr('dy', '0.32em').attr('text-anchor', 'end').text((r) => r.s.label);
    row.append('path').attr('class', 'bar').attr('d', (r) => roundedBar(m.left, (rowH - 16) / 2, x(r.v) - m.left, 16, 4, true));
    row.append('text').attr('class', 'row-value').attr('x', (r) => x(r.v) + 6).attr('y', rowH / 2).attr('dy', '0.32em').text((r) => fmt(r.v));
    svg.append('line').attr('class', 'axis-rule').attr('x1', m.left).attr('x2', m.left).attr('y1', 0).attr('y2', height);
    bindItems(fig, svg, row, rows, (px, py) => Math.floor((py - m.top) / rowH), (r) => ({
      x: x(r.v), y: m.top + rows.indexOf(r) * rowH + rowH, header: r.s.label,
      rows: [{ value: tipFmt(r.v), label: monthLabel(month) }],
    }), tooltip);
  });
}

const RENDERERS = {
  line: (fig, s, a, u, d) => timeChart(fig, s, a, u, d, 'line'),
  'stacked-area': (fig, s, a, u, d) => timeChart(fig, s, a, u, d, 'area'),
  bar: barChart,
  'small-multiples': smallMultiples,
  slope: slopeChart,
  dot: dotChart,
};
