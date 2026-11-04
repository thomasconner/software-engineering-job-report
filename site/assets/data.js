// Month math, value formatting and series lookup over metrics.json.

export const WINDOWS = { '3m': 3, '1y': 12, '5y': 60 };
export const WINDOW_LABEL = { '3m': '3 months', '1y': '1 year', '5y': '5 years' };
const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

// A mistake in an article or directive. Shown loudly to authors, quietly to readers.
export class AuthoringError extends Error {}

const CATEGORY_LABELS = {
  remote: 'Remote', hybrid: 'Hybrid', onsite: 'Onsite', unclear: 'Unclear',
  junior: 'Junior', mid: 'Mid-level', senior: 'Senior', staff_plus: 'Staff and above', unspecified: 'Not stated',
  ai_ml: 'AI and ML', devtools_infra: 'Dev tools and infra', fintech: 'Fintech', health: 'Health',
  climate_energy: 'Climate and energy', security: 'Security', commerce: 'Commerce',
  media_consumer: 'Media and consumer', enterprise_saas: 'Enterprise SaaS', hardware_robotics: 'Hardware and robotics',
  other: 'Other', unstated: 'Not stated', bootstrapped: 'Bootstrapped', seed: 'Seed', series_a: 'Series A',
  series_b: 'Series B', series_c_plus: 'Series C+', public_or_large: 'Public or large',
  venture_unspecified: 'Venture, round not named', unknown: 'Unknown',
  python: 'Python', javascript: 'JavaScript', typescript: 'TypeScript', react: 'React', go: 'Go', rust: 'Rust',
  ruby: 'Ruby', rails: 'Rails', java: 'Java', php: 'PHP', kubernetes: 'Kubernetes', aws: 'AWS', llm: 'LLM',
  agents: 'Agents',
};
export const categoryLabel = (c) => CATEGORY_LABELS[c] ?? c.charAt(0).toUpperCase() + c.slice(1).replaceAll('_', ' ');

// Catch-all categories always sit at the end of a ranking or a stack, whatever their size.
const CATCH_ALL = ['other', 'unstated', 'unknown', 'unspecified', 'unclear'];
export const isCatchAll = (key) => CATCH_ALL.includes(key);

export const METHOD_LABEL = {
  count: 'Counted directly',
  regex: 'Pattern match in code',
  vocab: 'Fixed word list in code',
  join: 'Matched against earlier months in code',
  jev: 'Jev classifier, expected value',
};

const THREAD_NAME = { hiring: 'Who is hiring?', seeking: 'Who wants to be hired?' };

export function addMonths(ym, n) {
  const [y, m] = ym.split('-').map(Number);
  const i = y * 12 + (m - 1) + n;
  return `${Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}`;
}
export const monthDate = (ym) => new Date(Date.UTC(+ym.slice(0, 4), +ym.slice(5, 7) - 1, 1));
const monthFmt = {
  long: new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' }),
  short: new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' }),
};
export const monthLabel = (ym, style = 'short') => monthFmt[style].format(monthDate(ym));

// "3m" / "1y" / "5y" or an explicit YYYY-MM, resolved against `to`.
export function pastMonth(vs, to) {
  if (WINDOWS[vs]) return addMonths(to, -WINDOWS[vs]);
  if (MONTH.test(vs ?? '')) return vs;
  throw new AuthoringError(`vs="${vs}" must be 3m, 1y, 5y or a YYYY-MM month`);
}
export const isMonth = (s) => MONTH.test(s ?? '');

// Months after the latest complete one (the pending tail) never reach the page.
export function prepare(data) {
  const pending = new Set(data.pending ?? []);
  const complete = (data.months ?? []).filter((m) => !pending.has(m));
  return { ...data, pending, lastComplete: complete.at(-1) ?? data.latest_month };
}

const int = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

/**
 * Display precision follows the article's rounding: whole percents, ratios and scores to one decimal,
 * dollars to the nearest $1,000. `precise` adds one digit, for tooltips and tables.
 */
export function makeFormat(unit, { precise = false } = {}) {
  return (v) => {
    if (v == null || Number.isNaN(v)) return 'n/a';
    switch (unit) {
      case 'share': return `${(v * 100).toFixed(precise ? 1 : 0)}%`;
      case 'usd': return `$${int.format(Math.round(v / 1000) * 1000)}`;
      case 'count': return int.format(v);
      default: return v.toFixed(precise ? 2 : 1);
    }
  };
}

// How a change is printed. Share gaps come from the printed (whole) percents so they match the prose.
function deltaText(now, then, unit) {
  let diff;
  let text;
  if (unit === 'share') {
    diff = Math.round(now * 100) - Math.round(then * 100);
    text = `${Math.abs(diff)} pts`;
  } else if (unit === 'count' || unit === 'usd') {
    if (!then) return null;
    diff = ((now - then) / then) * 100;
    text = `${Math.abs(diff).toFixed(0)}%`;
  } else {
    diff = +now.toFixed(1) - +then.toFixed(1);
    text = Math.abs(diff).toFixed(1);
  }
  const sign = Number(text.replace(/[^0-9.]/g, '')) === 0 ? 0 : Math.sign(diff);
  return { sign, text: `${sign > 0 ? '+' : sign < 0 ? '−' : ''}${text}` };
}

const sum = (xs) => xs.reduce((t, x) => t + x, 0);

/**
 * The noise test behind "≈" (docs/style-guide.md, "The noise bar").
 * Returns 'noise' when the move is within the bar, 'thin' when too few posts back a median, else 'clear'.
 * 3m, 1y and 5y moves use the bar exported on the later point, which reflects the series' own
 * month-to-month wobble. Other month pairs fall back to the sampling-only floors below.
 */
function noiseTest(data, key, unit) {
  const value = (k, m) => data.metrics[k]?.series.find((p) => p.month === m)?.value;
  const absolute = unit === 'share' || unit === 'score';
  return (then, now) => {
    const a = then.value;
    const b = now.value;
    if (unit === 'usd' && (then.n < 30 || now.n < 30)) return 'thin';
    const win = Object.keys(WINDOWS).find((w) => addMonths(now.month, -WINDOWS[w]) === then.month);
    const bar = now.bar?.[win];
    if (bar != null) {
      // Counts, ratios and dollars carry their bar on the log scale: ln(now / then).
      if (!absolute && !(a > 0 && b > 0)) return 'clear';
      return (absolute ? Math.abs(b - a) : Math.abs(Math.log(b / a))) < bar ? 'noise' : 'clear';
    }
    if (unit === 'share') {
      if (!then.n || !now.n) return 'clear';
      const p = (a + b) / 2;
      return Math.abs(b - a) < 1.96 * Math.sqrt(p * (1 - p) * (1 / then.n + 1 / now.n)) ? 'noise' : 'clear';
    }
    if (unit === 'count') return a && Math.abs(b - a) < 1.96 * Math.sqrt(a + b) ? 'noise' : 'clear';
    if (key.startsWith('seekers_per_post')) {
      const counts = [then.month, now.month].flatMap((m) => [value('posts.seeking', m), value('posts.hiring', m)]);
      if (counts.some((c) => !c)) return 'clear';
      return Math.abs(b / a - 1) < 1.96 * Math.sqrt(sum(counts.map((c) => 1 / c))) ? 'noise' : 'clear';
    }
    if (unit === 'usd') return Math.abs(b / a - 1) < 0.05 ? 'noise' : 'clear';
    if (unit === 'score') return Math.abs(b - a) < 0.2 ? 'noise' : 'clear';
    return 'clear';
  };
}

const WORD = { good: 'better', bad: 'worse', noise: 'about the same', thin: 'too few posts' };

/**
 * A change from `thenMonth` to `nowMonth`, ready to print: {sign, text, mark, tone, word}.
 * Moves inside the noise bar are gray, marked "≈" and called "about the same", whatever their polarity.
 */
export function change(series, thenMonth, nowMonth) {
  const then = series.points.find((p) => p.month === thenMonth);
  const now = series.points.find((p) => p.month === nowMonth);
  if (!then || !now) return null;
  const d = deltaText(now.value, then.value, series.unit);
  if (!d) return null;
  const verdict = series.noise(then, now);
  if (verdict !== 'clear') return { ...d, mark: '≈', tone: 'flat', word: WORD[verdict] };
  const tone = ({ 1: 'good', '-1': 'bad' })[d.sign * (series.polarity ?? 0)] ?? 'flat';
  return { ...d, mark: d.sign > 0 ? '▲' : d.sign < 0 ? '▼' : '', tone, word: WORD[tone] ?? '' };
}

export const tickFormat = (unit) => {
  switch (unit) {
    case 'share': return (v) => `${Math.round(v * 100)}%`;
    case 'usd': return (v) => `$${Math.round(v / 1000)}K`;
    case 'count': return (v) => (v >= 1000 ? `${+(v / 1000).toFixed(1)}K` : int.format(v));
    default: return (v) => (Number.isInteger(v) ? String(v) : v.toFixed(1));
  }
};

/**
 * Resolve a directive's data reference into series:
 * {key, label, group, unit, method, polarity, sources, points: [{month, date, value, n}]}.
 * `group` is the metric label (or the breakdown label) used in subtitles.
 * Points after `until` and pending months are dropped.
 */
export function resolveSeries(data, { metric, metrics, breakdown, categories }, until) {
  const clip = (pts) => pts.filter((p) => p.month <= until && !data.pending.has(p.month))
    .map((p) => ({ ...p, date: monthDate(p.month) }));
  const keys = (metrics ?? metric)?.split(',').map((s) => s.trim()).filter(Boolean);
  if (keys?.length) {
    return keys.map((key) => {
      const m = data.metrics[key];
      if (!m) throw new AuthoringError(`Unknown metric "${key}"`);
      return {
        key, label: m.label, group: m.label, unit: m.unit, method: m.method, description: m.description,
        polarity: m.polarity ?? 0, sources: m.sources ?? [key.split('.')[1]], points: clip(m.series),
        confidence: m.confidence, noise: noiseTest(data, key, m.unit),
      };
    });
  }
  const b = data.breakdowns[breakdown];
  if (!b) throw new AuthoringError(`Unknown breakdown "${breakdown}"`);
  const cats = categories ? categories.split(',').map((s) => s.trim()) : b.categories;
  return cats.map((c) => {
    if (!b.categories.includes(c)) throw new AuthoringError(`Unknown category "${c}" in ${breakdown}`);
    return {
      key: c, label: categoryLabel(c), group: b.label, unit: 'share', method: b.method, description: b.label,
      polarity: b.polarity ?? 0, sources: b.sources ?? ['hiring'], confidence: b.confidence,
      noise: noiseTest(data, c, 'share'),
      points: clip(b.series.map((s) => ({
        month: s.month, value: s.values[c], n: s.n,
        bar: s.bar && Object.fromEntries(Object.entries(s.bar).map(([w, bars]) => [w, bars[c]])),
      }))),
    };
  });
}

export const pointAt = (series, ym) => series.points.find((p) => p.month === ym);
export const valueAt = (series, ym) => pointAt(series, ym)?.value ?? null;

export function sourceLine(series) {
  const kinds = ['hiring', 'seeking'].filter((k) => series.some((s) => s.sources.includes(k)));
  return `Source: HN ${kinds.map((k) => THREAD_NAME[k]).join(' and ')} threads, first 7 days.`;
}

// Said once per chart, and only when the author's note doesn't already say it.
export const MODEL_NOTE = 'Estimated by a language model reading each post; see How we measure this.';
export const needsModelNote = (series, note) => series.some((s) => s.method === 'jev') && !/model/i.test(note ?? '');
