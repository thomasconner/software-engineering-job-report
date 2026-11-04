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

/** One number format per chart: a share chart uses one decimal everywhere if any value is under 10%. */
export function makeFormat(unit, values = []) {
  const small = values.some((v) => v > 0 && v < 0.1);
  return (v) => {
    if (v == null || Number.isNaN(v)) return 'n/a';
    switch (unit) {
      case 'share': return `${(v * 100).toFixed(small ? 1 : 0)}%`;
      case 'usd': return `$${int.format(Math.round(v / 1000))}K`;
      case 'count': return int.format(v);
      default: return v.toFixed(2);
    }
  };
}

// Shares move in percentage points; counts and dollars as percent change; ratios and scores as raw difference.
export function delta(now, then, unit) {
  if (now == null || then == null) return null;
  let diff;
  let text;
  if (unit === 'share') {
    diff = (now - then) * 100;
    text = `${Math.abs(diff).toFixed(1)} pts`;
  } else if (unit === 'count' || unit === 'usd') {
    if (!then) return null;
    diff = ((now - then) / then) * 100;
    text = `${Math.abs(diff).toFixed(0)}%`;
  } else {
    diff = now - then;
    text = Math.abs(diff).toFixed(2);
  }
  const sign = Number(text.replace(/[^0-9.]/g, '')) === 0 ? 0 : Math.sign(diff);
  return { sign, text: `${sign > 0 ? '+' : sign < 0 ? '−' : ''}${text}` };
}

// good / bad / flat for a change, given the measure's polarity from metrics.json.
export const tone = (sign, polarity) => ({ 1: 'good', '-1': 'bad' })[sign * (polarity ?? 0)] ?? 'flat';
export const TONE_WORD = { good: 'better', bad: 'worse', flat: '' };

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
      polarity: b.polarity ?? 0, sources: b.sources ?? ['hiring'],
      points: clip(b.series.map((s) => ({ month: s.month, value: s.values[c], n: s.n }))),
    };
  });
}

export const pointAt = (series, ym) => series.points.find((p) => p.month === ym);
export const valueAt = (series, ym) => pointAt(series, ym)?.value ?? null;

export function sourceLine(series) {
  const kinds = ['hiring', 'seeking'].filter((k) => series.some((s) => s.sources.includes(k)));
  const jev = series.some((s) => s.method === 'jev') ? ' Jev estimates are expected values, not counts of top answers.' : '';
  return `Source: HN ${kinds.map((k) => THREAD_NAME[k]).join(' and ')} threads, first 7 days.${jev}`;
}
