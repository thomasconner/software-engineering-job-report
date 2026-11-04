// Checks data.js change() against exported bars. Run by tests/test_renderer.py.
import assert from 'node:assert/strict';

const data = await import(process.argv[2]);

const prepare = (metrics, breakdowns = {}) => data.prepare({ months: ['2025-10', '2026-10'], metrics, breakdowns });

// One scalar metric: `then` and `now` are [month, value, n?]; `bar` sits on the later point.
function scalar(unit, then, now, bar) {
  const point = ([month, value, n = 300]) => ({ month, value, n });
  const metrics = {
    'x.hiring': { label: 'x', unit, method: 'count', polarity: 1, series: [point(then), { ...point(now), bar }] },
  };
  return data.resolveSeries(prepare(metrics), { metric: 'x.hiring' }, now[0])[0];
}

function verdict(unit, a, b, bar, { from = '2025-10', to = '2026-10', n = 300 } = {}) {
  const c = data.change(scalar(unit, [from, a, n], [to, b, n], { '1y': bar }), from, to);
  return c && c.word;
}

// Relative units use ln(now/then): a 30% fall is ln 0.7 = -0.357, outside a 0.33 bar,
// and a 38% rise is ln 1.38 = 0.322, inside it.
assert.equal(verdict('count', 100, 70, 0.33), 'worse');
assert.equal(verdict('count', 100, 138, 0.33), 'about the same');
assert.equal(verdict('usd', 200000, 220000, 0.099), 'about the same');
assert.equal(verdict('usd', 200000, 222000, 0.099), 'better');
// Shares compare the difference in share units.
assert.equal(verdict('share', 0.2, 0.29, 0.1), 'about the same');
assert.equal(verdict('share', 0.2, 0.31, 0.1), 'better');

// Salary medians on fewer than 30 posts are "too few posts", whatever the bar says.
assert.equal(verdict('usd', 200000, 300000, 0.01, { n: 20 }), 'too few posts');

// A zero on either side can't be put on the log scale, so a ratio move is never called noise.
assert.equal(verdict('ratio', 0, 0.5, 10), 'better');
assert.equal(verdict('ratio', 0.5, 0, 10), 'worse');

// A pair that isn't 3m, 1y or 5y ignores the exported bars and uses the Poisson floor:
// 300 → 330 is inside 1.96 * sqrt(630) = 49 posts, 300 → 400 is outside 1.96 * sqrt(700) = 52.
const nineMonths = { from: '2026-01', to: '2026-10' };
assert.equal(verdict('count', 300, 330, 0.001, nineMonths), 'about the same');
assert.equal(verdict('count', 300, 400, 10, nineMonths), 'better');

// Breakdown categories read their own bar from bar[window][category].
const breakdowns = {
  work_mode: {
    label: 'Work mode', method: 'jev', categories: ['remote', 'hybrid'], polarity: 1,
    series: [
      { month: '2025-10', n: 300, values: { remote: 0.3, hybrid: 0.3 } },
      { month: '2026-10', n: 300, values: { remote: 0.4, hybrid: 0.4 }, bar: { '1y': { remote: 0.05, hybrid: 0.2 } } },
    ],
  },
};
const [remote, hybrid] = data.resolveSeries(prepare({}, breakdowns), { breakdown: 'work_mode' }, '2026-10');
assert.equal(data.change(remote, '2025-10', '2026-10').word, 'better');
assert.equal(data.change(hybrid, '2025-10', '2026-10').word, 'about the same');
