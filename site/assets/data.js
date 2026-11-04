// Month math, value formatting and series lookup over metrics.json.

export const AGAINST_MONTHS = { '3m': 3, '6m': 6, '1y': 12, '2y': 24, '5y': 60, '10y': 120 };
export const AGAINST_LABEL = { '3m': '3 months', '6m': '6 months', '1y': '1 year', '2y': '2 years', '5y': '5 years', '10y': '10 years' };

// +1 when a rise is good news for people looking for engineering work, -1 when it is bad, 0 when it is neither.
const POLARITY = {
  'posts.hiring': 1,
  'seekers_per_post.hiring': -1,
  'salary_disclosed_share.hiring': 1,
  'salary_min_median_usd.hiring': 1,
  'salary_max_median_usd.hiring': 1,
  'visa_share.hiring': 1,
  'new_company_share.hiring': 1,
  'new_grad_share.hiring': 1,
  'seeker_mood.seeking': 1,
};
export const polarity = (key) => POLARITY[key] ?? 0;

const CATEGORY_LABELS = {
  remote: 'Remote', hybrid: 'Hybrid', onsite: 'Onsite', unclear: 'Unclear',
  junior: 'Junior', mid: 'Mid-level', senior: 'Senior', staff_plus: 'Staff and above', unspecified: 'Not stated',
  ai_ml: 'AI and ML', devtools_infra: 'Dev tools and infra', fintech: 'Fintech', health: 'Health',
  climate_energy: 'Climate and energy', security: 'Security', commerce: 'Commerce',
  media_consumer: 'Media and consumer', enterprise_saas: 'Enterprise SaaS', hardware_robotics: 'Hardware and robotics',
  other: 'Other', bootstrapped: 'Bootstrapped', seed: 'Seed', series_a: 'Series A', series_b: 'Series B',
  series_c_plus: 'Series C+', public_or_large: 'Public or large', unknown: 'Unknown',
  python: 'Python', javascript: 'JavaScript', typescript: 'TypeScript', react: 'React', go: 'Go', rust: 'Rust',
  ruby: 'Ruby', rails: 'Rails', java: 'Java', php: 'PHP', kubernetes: 'Kubernetes', aws: 'AWS', llm: 'LLM',
  agents: 'Agents',
};
export const categoryLabel = (c) => CATEGORY_LABELS[c] ?? c.charAt(0).toUpperCase() + c.slice(1).replaceAll('_', ' ');

export const METHOD_LABEL = {
  count: 'Counted directly',
  regex: 'Pattern match in code',
  vocab: 'Fixed word list in code',
  join: 'Matched against earlier months in code',
  jev: 'Jev classifier, expected value',
};

const THREAD_NAME = { hiring: 'Who is hiring?', seeking: 'Who wants to be hired?' };

// Months are "YYYY-MM" strings everywhere; they sort and compare as plain strings.
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

const int = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

export function formatValue(v, unit) {
  if (v == null || Number.isNaN(v)) return 'n/a';
  switch (unit) {
    case 'share': return `${(v * 100).toFixed(v < 0.1 && v > 0 ? 1 : 0)}%`;
    case 'usd': return `$${int.format(Math.round(v / 1000))}K`;
    case 'count': return int.format(v);
    default: return v.toFixed(2);
  }
}

// Shares move in percentage points; counts and dollars as percent change; ratios and scores as raw difference.
export function delta(now, then, unit) {
  if (now == null || then == null) return null;
  let diff, text;
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
  const rounded = Number(text.replace(/[^0-9.]/g, ''));
  const sign = rounded === 0 ? 0 : Math.sign(diff);
  return { sign, text: `${sign > 0 ? '+' : sign < 0 ? '−' : ''}${text}` };
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
 * {key, label, unit, kind, method, description, points: [{month, date, value, n}]}.
 * Points after `until` are dropped so a back issue never shows later months.
 */
export function resolveSeries(data, { metric, metrics, breakdown, categories }, until) {
  const clip = (pts) => pts.filter((p) => p.month <= until).map((p) => ({ ...p, date: monthDate(p.month) }));
  const keys = (metrics ?? metric)?.split(',').map((s) => s.trim()).filter(Boolean);
  if (keys?.length) {
    return keys.map((key) => {
      const m = data.metrics[key];
      if (!m) throw new Error(`Unknown metric "${key}"`);
      return {
        key, label: m.label, unit: m.unit, kind: key.split('.')[1], method: m.method,
        description: m.description, points: clip(m.series),
      };
    });
  }
  const b = data.breakdowns[breakdown];
  if (!b) throw new Error(`Unknown breakdown "${breakdown}"`);
  const cats = categories ? categories.split(',').map((s) => s.trim()) : b.categories;
  return cats.map((c) => {
    if (!b.categories.includes(c)) throw new Error(`Unknown category "${c}" in ${breakdown}`);
    return {
      key: c, label: categoryLabel(c), unit: 'share', kind: 'hiring', method: b.method,
      description: b.label, points: clip(b.series.map((s) => ({ month: s.month, value: s.values[c], n: s.n }))),
    };
  });
}

export const valueAt = (series, ym) => series.points.find((p) => p.month === ym)?.value ?? null;

export function sourceLine(series) {
  const kinds = [...new Set(series.map((s) => s.kind))].map((k) => THREAD_NAME[k] ?? THREAD_NAME.hiring);
  const jev = series.some((s) => s.method === 'jev') ? ' Jev estimates are expected values, not counts of top answers.' : '';
  return `Source: HN ${kinds.join(' and ')} threads, first 7 days.${jev}`;
}
